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

- `patched_files/` — the 9 already-patched source files (captured against
  `openviking==0.3.9`). `apply.sh` copies them over the pip-installed
  versions. Much more reliable than running `patch` (which drifts
  silently when the unified-diff context doesn't match exactly — bit us
  on Railway's fresh Docker builds).
- `01-pr13-content-deltas.patch` / `02-pr23-aiter-bytes.patch` — kept
  for reference / audit. Not used by `apply.sh` anymore.
- `apply.sh` — verifies `openviking==0.3.9` is installed, then `cp`s the
  bundled files over site-packages. Fails loudly if the version drifts
  or any expected marker is missing after copy.

## Verifying

```bash
curl -N http://localhost:18790/bot/v1/chat/stream \
    -H 'X-API-Key: taidi-bot-key-2026' \
    -d '{"message":"给我三个关于中药的事实","stream":true}'
```

You should see multiple `data: {"event":"content_delta",...}` lines with
increasing timestamps, not a single final `response` event.
