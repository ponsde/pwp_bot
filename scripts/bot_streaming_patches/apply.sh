#!/usr/bin/env bash
# Apply streaming patches to the installed openviking/vikingbot packages.
# PR13 + PR23 from Ferry-200/OpenViking were merged into the new-frontend
# branch, not main — so PyPI releases (incl. 0.3.9) don't include them.
#
# We apply them directly to the installed site-packages so the bot gateway
# emits content_delta / reasoning_delta events (token-level streaming) and
# the openviking-server proxy preserves SSE event framing.
#
# Idempotent: checks via `patch --dry-run` before applying.
#
# Usage:
#   scripts/bot_streaming_patches/apply.sh
#
# Reverse: run each patch with `patch -R -p1`.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SITE="$ROOT/.venv/lib/python3.12/site-packages"

if [ ! -d "$SITE/vikingbot" ]; then
    echo "error: $SITE/vikingbot not found. Is the venv set up?" >&2
    exit 1
fi

# Extra manual fix to cli/commands.py: read API key from ov.conf (0.3.9 hard-fails without it).
MANUAL_FIX_MARKER="Read API key from ov.conf bot.channels"
if ! grep -q "$MANUAL_FIX_MARKER" "$SITE/vikingbot/cli/commands.py"; then
    python3 - <<'PY'
import pathlib, re
p = pathlib.Path("/home/ponsde/taidi_bei/.venv/lib/python3.12/site-packages/vikingbot/cli/commands.py")
src = p.read_text()
old = (
    '        openapi_config = OpenAPIChannelConfig(\n'
    '            enabled=True,\n'
    '            port=openapi_port,\n'
    '            api_key="",\n'
    '        )\n'
)
new = (
    '        # Read API key from ov.conf bot.channels[] where type == "openapi" or "cli".\n'
    '        # 0.3.9 hard-fails the chat endpoint without a configured key.\n'
    '        _openapi_api_key = ""\n'
    '        try:\n'
    '            for ch in config.channels_config.get_all_channels():\n'
    '                ch_type = getattr(ch, "type", None) or (ch.get("type") if isinstance(ch, dict) else None)\n'
    '                if ch_type in ("openapi", "cli"):\n'
    '                    _openapi_api_key = (\n'
    '                        getattr(ch, "api_key", "") or (ch.get("api_key") if isinstance(ch, dict) else "")\n'
    '                    )\n'
    '                    if _openapi_api_key:\n'
    '                        break\n'
    '        except Exception as _exc:  # noqa: BLE001\n'
    '            logger.warning(f"could not resolve OpenAPI api_key from config: {_exc}")\n'
    '        openapi_config = OpenAPIChannelConfig(\n'
    '            enabled=True,\n'
    '            port=openapi_port,\n'
    '            api_key=_openapi_api_key,\n'
    '        )\n'
)
if old in src:
    p.write_text(src.replace(old, new))
    print(f"[manual-fix] patched {p.name}")
else:
    print(f"[manual-fix] already patched or unexpected layout in {p.name}")
PY
fi

apply_patch () {
    local patch_file="$1"
    local strip="$2"
    echo "applying $(basename "$patch_file")..."
    if (cd "$SITE" && patch -p"$strip" --dry-run -f < "$patch_file" > /dev/null 2>&1); then
        (cd "$SITE" && patch -p"$strip" < "$patch_file")
    elif (cd "$SITE" && patch -p"$strip" -R --dry-run -f < "$patch_file" > /dev/null 2>&1); then
        echo "  (already applied — skipping)"
    else
        echo "  warning: hunks may not match exactly; attempting forward apply..."
        (cd "$SITE" && patch -p"$strip" -f < "$patch_file" || true)
    fi
}

# PR13 diff has bot/vikingbot paths; strip that prefix on the fly.
PR13="$(dirname "$0")/01-pr13-content-deltas.patch"
PR13_REWROTE="$(mktemp)"
sed 's|a/bot/vikingbot|a/vikingbot|g; s|b/bot/vikingbot|b/vikingbot|g' "$PR13" > "$PR13_REWROTE"
apply_patch "$PR13_REWROTE" 1
rm -f "$PR13_REWROTE"

PR23="$(dirname "$0")/02-pr23-aiter-bytes.patch"
apply_patch "$PR23" 1

# Finally: loop.py hunk1 from PR13 fails (version drift on get_definitions signature).
# Apply the behavior manually: inject on_content_delta / on_reasoning_delta hooks
# around the provider.chat call.
LOOP="$SITE/vikingbot/agent/loop.py"
if ! grep -q "on_content_delta=on_content_delta" "$LOOP"; then
    python3 - <<'PY'
import pathlib
p = pathlib.Path("/home/ponsde/taidi_bei/.venv/lib/python3.12/site-packages/vikingbot/agent/loop.py")
src = p.read_text()
old = (
    '            response = await self.provider.chat(\n'
    '                messages=messages,\n'
    '                tools=self.tools.get_definitions(ov_tools_enable=ov_tools_enable),\n'
    '                model=self.model,\n'
    '                session_id=session_key.safe_name(),\n'
    '            )\n'
)
new = (
    '            on_content_delta = None\n'
    '            on_reasoning_delta = None\n'
    '            if publish_events:\n\n'
    '                async def on_content_delta(piece: str) -> None:\n'
    '                    await self.bus.publish_outbound(\n'
    '                        OutboundMessage(\n'
    '                            session_key=session_key,\n'
    '                            content=piece,\n'
    '                            event_type=OutboundEventType.CONTENT_DELTA,\n'
    '                        )\n'
    '                    )\n\n'
    '                async def on_reasoning_delta(piece: str) -> None:\n'
    '                    await self.bus.publish_outbound(\n'
    '                        OutboundMessage(\n'
    '                            session_key=session_key,\n'
    '                            content=piece,\n'
    '                            event_type=OutboundEventType.REASONING_DELTA,\n'
    '                        )\n'
    '                    )\n\n'
    '            response = await self.provider.chat(\n'
    '                messages=messages,\n'
    '                tools=self.tools.get_definitions(ov_tools_enable=ov_tools_enable),\n'
    '                model=self.model,\n'
    '                session_id=session_key.safe_name(),\n'
    '                on_content_delta=on_content_delta,\n'
    '                on_reasoning_delta=on_reasoning_delta,\n'
    '            )\n'
)
if old in src:
    p.write_text(src.replace(old, new))
    print(f"[loop.py manual-fix] patched")
else:
    print(f"[loop.py manual-fix] already patched or layout drifted")
PY
fi

echo ""
echo "done. restart the bot gateway for changes to take effect."
