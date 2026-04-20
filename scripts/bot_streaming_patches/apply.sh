#!/usr/bin/env bash
# Apply streaming + api_key fixes to the installed openviking/vikingbot packages.
#
# PR13 + PR23 from Ferry-200/OpenViking were merged into the new-frontend branch,
# not main — so PyPI 0.3.9 doesn't include them. Instead of running `patch`
# (which silently drops hunks when context drifts and was unreliable on Railway),
# we ship the already-patched files in ./patched_files/ and copy them over.
#
# This requires openviking==0.3.9 (pinned in requirements.txt). If a different
# version is installed the script aborts rather than overwriting with files
# from a different release.
#
# Usage:
#   scripts/bot_streaming_patches/apply.sh
#
# SITE env var points at the Python site-packages root.
# Defaults to the project's .venv for local dev.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SITE="${SITE:-$ROOT/.venv/lib/python3.12/site-packages}"
PATCHED="$(cd "$(dirname "$0")" && pwd)/patched_files"

if [ ! -d "$SITE/vikingbot" ]; then
    echo "error: $SITE/vikingbot not found. Point SITE= at the Python site-packages root." >&2
    exit 1
fi

if [ ! -d "$PATCHED" ]; then
    echo "error: $PATCHED not found." >&2
    exit 1
fi

# Verify installed openviking version matches what the patched files were
# captured against. We embed this so wheel drift surfaces as a loud error
# instead of a silent runtime crash.
EXPECTED_VERSION="0.3.9"
ACTUAL_VERSION="$(python3 -c 'import openviking, sys; sys.stdout.write(getattr(openviking, "__version__", "unknown"))' 2>/dev/null || echo unknown)"
if [ "$ACTUAL_VERSION" != "$EXPECTED_VERSION" ]; then
    # Fall back to pip metadata if the package doesn't expose __version__.
    ACTUAL_VERSION="$(python3 -c 'from importlib.metadata import version; print(version("openviking"))' 2>/dev/null || echo unknown)"
fi
if [ "$ACTUAL_VERSION" != "$EXPECTED_VERSION" ]; then
    echo "error: installed openviking version is $ACTUAL_VERSION but patched_files were captured against $EXPECTED_VERSION." >&2
    echo "       pin openviking==$EXPECTED_VERSION in requirements.txt or refresh patched_files." >&2
    exit 1
fi

copy_file () {
    local rel="$1"
    local src="$PATCHED/$rel"
    local dst="$SITE/$rel"
    if [ ! -f "$src" ]; then
        echo "error: missing patched source $src" >&2
        exit 1
    fi
    if [ ! -f "$dst" ]; then
        echo "error: target $dst does not exist in the installed package" >&2
        exit 1
    fi
    cp "$src" "$dst"
    echo "  patched $rel"
}

echo "applying bundled patches to $SITE ..."
copy_file "vikingbot/agent/loop.py"
copy_file "vikingbot/bus/events.py"
copy_file "vikingbot/channels/openapi.py"
copy_file "vikingbot/channels/openapi_models.py"
copy_file "vikingbot/cli/commands.py"
copy_file "vikingbot/providers/base.py"
copy_file "vikingbot/providers/litellm_provider.py"
copy_file "vikingbot/providers/openai_compatible_provider.py"
copy_file "openviking/server/routers/bot.py"

# Sanity: the key streaming markers must be present after copy.
for needle_file in \
    "on_content_delta: DeltaCallback|$SITE/vikingbot/providers/litellm_provider.py" \
    "on_content_delta: DeltaCallback|$SITE/vikingbot/providers/openai_compatible_provider.py" \
    "on_content_delta=on_content_delta|$SITE/vikingbot/agent/loop.py" \
    "Read API key from ov.conf bot.channels|$SITE/vikingbot/cli/commands.py"; do
    needle="${needle_file%%|*}"
    file="${needle_file##*|}"
    if ! grep -q "$needle" "$file"; then
        echo "error: expected marker \"$needle\" missing from $file after copy" >&2
        exit 1
    fi
done

echo ""
echo "done. restart the bot gateway for changes to take effect."
