#!/usr/bin/env bash
# Renders the Open Graph cards in assets/og/ from the HTML next to this script.
#
# They are checked in as PNGs because the deploy only uploads files, but the
# source is kept so the cards can be changed rather than redrawn. The fonts are
# loaded from assets/fonts/src (the untrimmed originals) — the subset copies
# next to them are missing glyphs that only appear here.
#
# Needs a Chrome or Chromium binary; pass one as $CHROME if it is not on PATH.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
out="$here/../../assets/og"
chrome="${CHROME:-$(command -v chromium || command -v chromium-browser || command -v google-chrome || true)}"
[ -n "$chrome" ] || { echo "no chrome found; set CHROME=/path/to/chrome" >&2; exit 1; }

mkdir -p "$out"
for card in cover apps; do
  "$chrome" --headless --disable-gpu --no-sandbox --hide-scrollbars \
    --force-device-scale-factor=1 --window-size=1200,630 \
    --screenshot="$out/$card.png" --allow-file-access-from-files \
    "file://$here/$card.html" 2>/dev/null
  echo "$out/$card.png"
done
