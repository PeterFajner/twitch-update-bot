#!/bin/bash

set -euo pipefail
exec >>/var/log/twitch_eventsub.log 2>&1
echo "Started script at $(date)"

# load secrets
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "Loading environment variables from $SCRIPT_DIR"
source "$SCRIPT_DIR/.env"

# log request
echo "$(date "+%Y-%m-%d %H:%M:%S") - Received request" >> /var/log/twitch_eventsub.log
cat >> /var/log/twitch_eventsub.log

# read and parse fastcgi headers
declare -A HEADERS
while IFS='=' read -r key value; do
    HEADERS["$key"]="$value"
done < <(env | grep -E '^HTTP_' || true)

get_header() {
    local key="HTTP_$(echo "$1" | tr '[:lower:]-' '[:upper:]_')"
    echo "${HEADERS[$key]}"
}

# extract twitch headers
MSG_ID=$(get_header "Twitch-Eventsub-Message-Id")
MSG_TS=$(get_header "Twitch-Eventsub-Message-Timestamp")
MSG_SIG=$(get_header "Twitch-Eventsub-Message-Signature")

# read raw request body
RAW_BODY=$(cat)

# compute hmac
VALID_SIG="sha256=$(printf "%s%s%s" "$MSG_ID" "$MSG_TS" "$RAW_BODY" |
    openssl dgst -sha256 -hmac "$TWITCH_EVENTSUB_SECRET" -binary |
    xxd -p -c 256)"

# reject if invalid signature
if [[ "$MSG_SIG" != "$VALID_SIG" ]]; then
    echo "Status: 403 Forbidden"
    echo "Content-Type: text/plain"
    echo
    echo "Invalid signature"
    exit 0
fi

# respond to challenge
if echo "$RAW_BODY" | jq -e 'has("challenge")' >/dev/null; then
    CHALLENGE=$(echo "$RAW_BODY" | jq -r .challenge)
    echo "Status: 200 OK"
    echo "Content-Type: text/plain"
    echo
    echo "$CHALLENGE"
    exit 0
fi

# if event is stream.online then post to discord
EVENT_TYPE=$(echo "$RAW_BODY" | jq -r .subscription.type)
if [ "$EVENT_TYPE" == "stream.online" ]; then
    BROADCASTER=$(echo "$RAW_BODY" | jq -r .event.broadcaster_user_name)
    STREAM_URL="https://twitch.tv/$BROADCASTER"

    PAYLOAD=$(jq -n \
        --arg content "🔴 **$BROADCASTER is live!** Watch here: $STREAM_URL" \
        '{content: $content}')

    curl -s -X POST "$DISCORD_WEBHOOK_URL" \
        -H "Content-Type: application/json" \
        -d "$PAYLOAD" >/dev/null

    echo "Status: 200 OK"
    echo "Content-Type: text/plain"
    echo
    echo "Posted to Discord: $BROADCASTER is live!"
    exit 0
fi

# fallback
echo "Status: 200 OK"
echo "Content-Type: text/plain"
echo
echo "Event received"
