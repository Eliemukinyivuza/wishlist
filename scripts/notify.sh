#!/usr/bin/env bash
# Open an issue that mentions the owner, so GitHub emails them the alerts.
# Usage: scripts/notify.sh "Title prefix"   (reads alerts.txt)
set -euo pipefail
[ -s alerts.txt ] || exit 0
{
  echo "@$OWNER, there is news on your wishlist:"
  echo
  sed 's/^/- /' alerts.txt
  echo
  echo "See the full list: https://$OWNER.github.io/${REPO#*/}/"
} > issue.md
gh issue create --repo "$REPO" \
  --title "$1: $(head -n 1 alerts.txt | cut -c1-70)" \
  --body-file issue.md
