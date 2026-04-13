"""Thin OpenViking adapter used by research RAG modules only.

Compatible with OpenViking 0.3.x. Key differences vs 0.2.x:
- ``add_resource`` now returns ``{"root_uri": ...}`` (no ``uri`` / ``target_uri`` key).
- ``MatchedContext`` no longer exposes a ``context`` attr; text lives in
  ``overview`` (detailed) and ``abstract`` (short).
- Prefer ``client.find`` over ``client.search`` for lightweight semantic
  retrieval — ``search`` now runs intent analysis and hierarchical planning.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from config import OV_CONFIG_PATH, OV_DATA_DIR


class OpenVikingAdapterError(RuntimeError):
    """Raised when OpenViking cannot be initialized or queried."""


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _synthesize_config_from_env() -> dict[str, Any]:
    """Build an ov.conf dict from env vars (for container / serverless deploys).

    OpenViking's own model stack lives in its own namespace so it doesn't get
    confused with the assistant's own LLM/embedding/VLM:

    - ``OV_EMBEDDING_API_{KEY,BASE,MODEL}`` — required for OV retrieval.
    - ``OV_VLM_API_{KEY,BASE,MODEL}``      — required for L0/L1 summary
      generation AND image / scanned-PDF parsing. Must be vision-capable;
      a text-only LLM will fail on OV's image_summary pipeline."""
    embedding_base = _env("OV_EMBEDDING_API_BASE")
    embedding_key = _env("OV_EMBEDDING_API_KEY")
    embedding_model = _env("OV_EMBEDDING_MODEL")
    if not embedding_base or not embedding_key or not embedding_model:
        raise OpenVikingAdapterError(
            "ov.conf missing and OV_EMBEDDING_API_{BASE,KEY,MODEL} not all set; "
            "cannot bootstrap OpenViking config from env."
        )
    conf: dict[str, Any] = {
        "storage": {"agfs": {"port": int(_env("OV_AGFS_PORT", "1834"))}},
        "embedding": {
            "dense": {
                "api_base": embedding_base,
                "api_key": embedding_key,
                "provider": "openai",
                "dimension": int(_env("OV_EMBEDDING_DIMENSION", "1024")),
                "model": embedding_model,
            }
        },
    }
    vlm_base = _env("OV_VLM_API_BASE")
    vlm_model = _env("OV_VLM_MODEL")
    vlm_key = _env("OV_VLM_API_KEY")
    if vlm_base and vlm_model and vlm_key:
        conf["vlm"] = {
            "api_base": vlm_base,
            "api_key": vlm_key,
            "provider": "openai",
            "model": vlm_model,
        }
    return conf


def _resolve_config_path(config_path: Path) -> Path:
    """Return an existing config file path, synthesizing one from env if needed.

    Prefers an existing ov.conf on disk. Falls back to writing
    ``/tmp/ov.conf`` from env vars so containers don't need to ship secrets."""
    if config_path.exists():
        return config_path
    import json
    conf = _synthesize_config_from_env()
    fallback = Path("/tmp/ov.conf")
    fallback.write_text(json.dumps(conf, indent=2), encoding="utf-8")
    return fallback


def init_client(data_path: str | Path | None = None, config_path: str | Path | None = None) -> Any:
    target_data_path = Path(data_path or OV_DATA_DIR)
    target_config_path = _resolve_config_path(Path(config_path or OV_CONFIG_PATH))

    target_data_path.mkdir(parents=True, exist_ok=True)
    os.environ["OPENVIKING_CONFIG_FILE"] = str(target_config_path)
    try:
        # ``OpenViking`` is the preferred public name in 0.3.x; ``SyncOpenViking``
        # remains for back-compat. Fall back if older installs only expose the latter.
        try:
            from openviking import OpenViking as _Client
        except ImportError:
            from openviking import SyncOpenViking as _Client
    except ImportError as exc:  # pragma: no cover
        raise OpenVikingAdapterError("OpenViking is not installed.") from exc

    try:
        client = _Client(path=str(target_data_path))
        client.initialize()
        return client
    except Exception as exc:  # pragma: no cover
        raise OpenVikingAdapterError(f"Failed to initialize OpenViking: {exc}") from exc


def store_resource(client: Any, pdf_path: str | Path) -> str:
    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"Research file not found: {path}")
    try:
        result = client.add_resource(str(path), wait=True, build_index=True)
    except Exception as exc:
        raise OpenVikingAdapterError(f"Failed to store resource {path}: {exc}") from exc
    # 0.3.x uses "root_uri"; 0.2.x used "uri"/"target_uri". Try all, fall back to path.
    uri = (
        result.get("root_uri")
        or result.get("uri")
        or result.get("target_uri")
        or str(path)
    )
    return str(uri)


def _extract_matched_contexts(raw: Any) -> list[Any]:
    """Extract MatchedContext items from FindResult (0.3.x) or legacy shapes."""
    # 0.3.x FindResult: has memories / resources / skills. Our RAG stores PDFs
    # as resources; memories/skills are empty. But merge all three to be safe.
    collected: list[Any] = []
    for attr in ("resources", "memories", "skills"):
        bucket = getattr(raw, attr, None)
        if isinstance(bucket, list):
            collected.extend(bucket)
    if collected:
        return collected
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        for key in ("resources", "memories", "skills", "items", "results", "hits", "data"):
            if isinstance(raw.get(key), list):
                return raw[key]
        return [raw]
    if raw is None:
        return []
    return [raw]


def _normalize_item(item: Any) -> dict[str, Any]:
    """Normalize a single search result item (MatchedContext or dict)."""
    uri = getattr(item, "uri", None)
    if uri is not None:
        # 0.3.x: overview is the long form, abstract is short. Prefer overview.
        # Keep 0.2.x "context" in the fallback chain for older installs.
        text = (
            getattr(item, "overview", None)
            or getattr(item, "abstract", None)
            or getattr(item, "context", None)
            or ""
        )
        score = getattr(item, "score", 0.0)
        return {"text": str(text), "source": str(uri), "score": float(score or 0.0), "raw": item}
    if isinstance(item, dict):
        text = (
            item.get("overview")
            or item.get("abstract")
            or item.get("text")
            or item.get("content")
            or item.get("chunk")
            or ""
        )
        source = item.get("source") or item.get("uri") or item.get("path") or ""
        score = item.get("score") or item.get("similarity") or 0.0
        return {"text": str(text), "source": str(source), "score": float(score or 0.0), "raw": item}
    return {"text": str(item), "source": "", "score": 0.0, "raw": item}


def _extract_snippet(text: str, query: str, min_len: int = 200, max_len: int = 500) -> str:
    normalized = re.sub(r"\s+", " ", str(text or "")).strip()
    if not normalized:
        return ""
    if len(normalized) <= max_len:
        return normalized

    tokens = [token for token in re.split(r"[^\w\u4e00-\u9fff]+", query) if len(token) >= 2]
    hit = -1
    for token in tokens:
        hit = normalized.find(token)
        if hit >= 0:
            break
    if hit < 0:
        hit = 0

    start = max(0, hit - max_len // 3)
    end = min(len(normalized), start + max_len)
    snippet = normalized[start:end]

    if start > 0:
        left_boundary = max((snippet.find(sep) for sep in ("。", "；", "\n") if snippet.find(sep) >= 0), default=-1)
        if left_boundary > 0:
            snippet = snippet[left_boundary + 1 :]
    if len(snippet) < min_len and end < len(normalized):
        snippet = normalized[start : min(len(normalized), start + min_len)]
    return snippet.strip()[:max_len]


def _chinese_char_ratio(text: str) -> float:
    """Return the ratio of Chinese characters in *text* (0.0–1.0)."""
    if not text:
        return 0.0
    chinese_count = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
    return chinese_count / len(text)


def search(client: Any, query: str, top_k: int = 5, target_uri: str = "") -> list[dict[str, Any]]:
    if not query.strip():
        return []
    # Prefer ``find`` (lightweight semantic retrieval) as shown in the 0.3.x
    # example. Fall back to ``search`` (heavier: intent analysis + hierarchical
    # planning) if find is unavailable on older installs.
    try:
        method = getattr(client, "find", None) or client.search
        raw = method(query, target_uri=target_uri, limit=top_k) if target_uri else method(query, limit=top_k)
    except TypeError:
        # Older 0.2.x signature didn't accept target_uri.
        raw = client.search(query, limit=top_k)
    except Exception as exc:
        raise OpenVikingAdapterError(f"OpenViking search failed: {exc}") from exc

    items = _extract_matched_contexts(raw)
    candidates: list[dict[str, Any]] = []
    for item in items[:top_k]:
        normalized = _normalize_item(item)
        normalized["text"] = _extract_snippet(normalized.get("text", ""), query)
        candidates.append(normalized)
    # Filter out predominantly non-Chinese results, but keep at least 1.
    results: list[dict[str, Any]] = [c for c in candidates if _chinese_char_ratio(c.get("text", "")) >= 0.3]
    if not results and candidates:
        best = max(candidates, key=lambda c: c.get("score", 0.0))
        results = [best]
    return results
