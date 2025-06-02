#!/bin/bash

set -euo pipefail

# load secrets
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "Loading environment variables from $SCRIPT_DIR"
source "$SCRIPT_DIR/.env"

# get last time we checked for clips
LAST_CHECK_FILE="$SCRIPT_DIR/latest_clip_time.txt"
NOW=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
if [ -f "$LAST_CHECK_FILE" ]; then
    STARTED_AT=$(cat "$LAST_CHECK_FILE")
else
    STARTED_AT=$NOW
fi
echo $NOW >$LAST_CHECK_FILE

# get oauth2 token
ACCESS_TOKEN_RESPONSE=$(curl -sX POST 'https://id.twitch.tv/oauth2/token' \
    -H 'Content-Type: application/x-www-form-urlencoded' \
    -d "client_id=$TWITCH_CLIENT_ID&client_secret=$TWITCH_CLIENT_SECRET&grant_type=client_credentials")
ACCESS_TOKEN=$(echo $ACCESS_TOKEN_RESPONSE | jq -r .access_token)

# get broadcaster ID
BROADCASTER_ID=$(curl -s -H "Client-ID: $TWITCH_CLIENT_ID" \
    -H "Authorization: Bearer $ACCESS_TOKEN" \
    "https://api.twitch.tv/helix/users?login=$TWITCH_USERNAME" | jq -r '.data[0].id')
echo "Broadcaster ID: $BROADCASTER_ID"

# get latest clips
CLIPS_JSON=$(curl -s -G "https://api.twitch.tv/helix/clips" \
    -H "Client-ID: $TWITCH_CLIENT_ID" \
    -H "Authorization: Bearer $ACCESS_TOKEN" \
    --data-urlencode "broadcaster_id=$BROADCASTER_ID" \
    --data-urlencode "first=10" \
    --data-urlencode "started_at=$STARTED_AT")
CLIP_COUNT=$(echo "$CLIPS_JSON" | jq '.data | length')

echo "Clip count: $CLIP_COUNT"

if [ "$CLIP_COUNT" -eq 0 ]; then
    echo "No new clips since $STARTED_AT"
else
    echo "$CLIPS_JSON" | jq -c '.data[]' | while read -r clip; do
        TIMESTAMP=$(echo "$clip" | jq -r .created_at)

        PAYLOAD=$(echo "$clip" | jq -nc --argjson c "$clip" --arg ts "$TIMESTAMP" '{
      embeds: [{
        title: $c.title,
        url: $c.url,
        author: { name: $c.broadcaster_name },
        image: { url: $c.thumbnail_url },
        timestamp: $ts
      }]
    }')

        echo "$PAYLOAD" | curl -s -X POST "$DISCORD_WEBHOOK_URL" \
            -H "Content-Type: application/json" \
            -d @-

        echo "Posted clip: $(echo "$clip" | jq -r .title)"
    done
fi
