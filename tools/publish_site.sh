#!/usr/bin/env bash
# Rebuild the static site and publish it to the gh-pages branch (GitHub Pages: https://vishalbanwari.tech/ai-ledger/).
# Usage: ./tools/publish_site.sh        (run from anywhere; needs the project venv and push access)
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
.venv/bin/python tools/build_site.py >/dev/null
TMP="$(mktemp -d)"
cp -R site/. "$TMP"/
cd "$TMP"
git init -q -b gh-pages
git remote add origin "$(git -C "$ROOT" remote get-url origin)"
git add -A
git commit -q -m "Publish the static demo (built from main $(git -C "$ROOT" rev-parse --short HEAD))"
git push -q -f origin gh-pages
echo "published: https://vishalbanwari.tech/ai-ledger/  (Pages takes about a minute to rebuild)"
