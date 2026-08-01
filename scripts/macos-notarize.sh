#!/usr/bin/env bash
# Submit a file to Apple notarization and poll until a verdict.
#   scripts/macos-notarize.sh <file> [poll-deadline-minutes]
# Env: APPLE_NOTARY_KEY_P8, APPLE_NOTARY_KEY_ID, APPLE_NOTARY_ISSUER_ID.
#
# Submits without --wait and polls ourselves: notarytool's built-in wait
# aborts on the first transient network error (a runner blip 53 minutes in
# cost a whole run), while each poll below is an independent request.
set -euo pipefail

target="$1"
deadline_min="${2:-330}"

key_dir="$(mktemp -d)"
key_file="$key_dir/notary-key.p8"
trap 'rm -rf "$key_dir"' EXIT
printf '%s' "$APPLE_NOTARY_KEY_P8" > "$key_file"

sub_id="$(xcrun notarytool submit "$target" \
  --key "$key_file" \
  --key-id "$APPLE_NOTARY_KEY_ID" \
  --issuer "$APPLE_NOTARY_ISSUER_ID" \
  --output-format json \
  | /usr/bin/python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')"
echo "Submission id: $sub_id"

deadline=$((SECONDS + deadline_min * 60))
status="In Progress"
while [ "$SECONDS" -lt "$deadline" ]; do
  sleep 60
  if ! out="$(xcrun notarytool info "$sub_id" \
      --key "$key_file" \
      --key-id "$APPLE_NOTARY_KEY_ID" \
      --issuer "$APPLE_NOTARY_ISSUER_ID" 2>&1)"; then
    echo "poll failed (transient), retrying: $(printf '%s' "$out" | head -1)"
    continue
  fi
  status="$(printf '%s\n' "$out" | sed -n 's/^ *status: //p' | head -1)"
  echo "[$((SECONDS / 60))m] status: $status"
  case "$status" in
    "In Progress"|"") ;;
    *) break ;;
  esac
done

if [ "$status" != "Accepted" ]; then
  echo "::error::notarization did not accept (status: $status)"
  exit 1
fi
echo "Notarization: Accepted ($target)"
