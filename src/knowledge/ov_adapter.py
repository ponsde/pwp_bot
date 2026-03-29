"""Thin OpenViking adapter used by research RAG modules only."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from config import OV_CONFIG_PATH, OV_DATA_DIR


class OpenVikingAdapterError(RuntimeError):
    """Raised when OpenViking cannot be initialized or queried."""


def init_client(data_path: str | Path | None = None, config_path: str | Path | None = None) -> Any:
    target_data_path = Path(data_path or OV_DATA_DIR)
    target_config_path = Path(config_path or OV_CONFIG_PATH)
    if not target_config_path.exists():
        raise OpenVikingAdapterError(
            f"OpenViking 配置文件不存在：{target_config_path}\n"
            "请复制 ov.conf.example 到该路径并填写 API 密钥。"
        )

    target_data_path.mkdir(parents=True, exist_ok=True)
    os.environ["OPENVIKING_CONFIG_FILE"] = str(target_config_path)
    try:
        from openviking import SyncOpenViking
    except ImportError as exc:  # pragma: no cover
        raise OpenVikingAdapterError("OpenViking is not installed.") from exc

    try:
        client = SyncOpenViking(path=str(target_data_path))
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
    uri = result.get("uri") or result.get("target_uri") or str(path)
    return str(uri)


def _extract_matched_contexts(raw: Any) -> list[Any]:
    """Extract MatchedContext items from OV FindResult or fallback to raw."""
    # OV FindResult has .resources (research content) and .memories (system)
    resources = getattr(raw, "resources", None)
    if isinstance(resources, list) and resources:
        return resources
    # Fallback: plain list or dict
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        for key in ("items", "results", "hits", "data"):
            if isinstance(raw.get(key), list):
                return raw[key]
        return [raw]
    if raw is None:
        return []
    return [raw]


def _normalize_item(item: Any) -> dict[str, Any]:
    """Normalize a single search result item (MatchedContext or dict)."""
    # OV MatchedContext: has .uri, .score, .context/.abstract/.overview
    uri = getattr(item, "uri", None)
    if uri is not None:
        text = getattr(item, "context", None) or getattr(item, "abstract", None) or getattr(item, "overview", None) or ""
        score = getattr(item, "score", 0.0)
        return {"text": str(text), "source": str(uri), "score": float(score or 0.0), "raw": item}
    # Plain dict
    if isinstance(item, dict):
        text = item.get("text") or item.get("content") or item.get("chunk") or ""
        source = item.get("source") or item.get("uri") or item.get("path") or ""
        score = item.get("score") or item.get("similarity") or 0.0
        return {"text": str(text), "source": str(source), "score": float(score or 0.0), "raw": item}
    return {"text": str(item), "source": "", "score": 0.0, "raw": item}


def search(client: Any, query: str, top_k: int = 5) -> list[dict[str, Any]]:
    if not query.strip():
        return []
    try:
        raw = client.search(query, limit=top_k)
    except Exception as exc:
        raise OpenVikingAdapterError(f"OpenViking search failed: {exc}") from exc
    items = _extract_matched_contexts(raw)
    results: list[dict[str, Any]] = []
    for item in items[:top_k]:
        normalized = _normalize_item(item)
        # OV MatchedContext.context is a VLM summary; read actual content
        uri = getattr(item, "uri", None)
        if uri:
            try:
                content = client.read(str(uri))
                if content and isinstance(content, str):
                    normalized["text"] = content.strip()
            except Exception:
                pass
        results.append(normalized)
    return results
