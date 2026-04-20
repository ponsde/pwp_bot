# Bot streaming patches

PRs [#13](https://github.com/Ferry-200/OpenViking/pull/13) (token-level
`content_delta` / `reasoning_delta` events) and
[#23](https://github.com/Ferry-200/OpenViking/pull/23) (aiter_bytes SSE
proxy) were merged to the `new-frontend` branch — NOT `main` — so they
are NOT in any PyPI release of `openviking` (including 0.3.9).

Without these, `/bot/v1/chat/stream` emits a single `response` event at
the end; the chat UI's streaming renderer has nothing to animate.

## Usage

```bash
# After `pip install -r requirements.txt`:
scripts/bot_streaming_patches/apply.sh
```

Idempotent — safe to re-run.

## What's in here

- `01-pr13-content-deltas.patch` — adds CONTENT_DELTA / REASONING_DELTA
  events, `stream=True` in LLM providers, SSE routing in openapi channel.
- `02-pr23-aiter-bytes.patch` — openviking-server proxy preserves SSE
  framing by forwarding bytes instead of buffered lines.
- `apply.sh` — patches the installed site-packages, plus a manual fix in
  `cli/commands.py` to read the OpenAPI api_key from `ov.conf` (0.3.9
  regressed this, hard-failing the endpoint without a key).

## Verifying

```bash
curl -N http://localhost:18790/bot/v1/chat/stream \
    -H 'X-API-Key: taidi-bot-key-2026' \
    -d '{"message":"给我三个关于中药的事实","stream":true}'
```

You should see multiple `data: {"event":"content_delta",...}` lines with
increasing timestamps, not a single final `response` event.
