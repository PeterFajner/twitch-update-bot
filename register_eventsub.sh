#!/bin/bash

set -euo pipefail

# load secrets
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "Loading environment variables from $SCRIPT_DIR"
source "$SCRIPT_DIR/.env"

# get oauth2 token and broadcaster ID
ACCESS_TOKEN_RESPONSE=$(curl -sX POST 'https://id.twitch.tv/oauth2/token' \
    -H 'Content-Type: application/x-www-form-urlencoded' \
    -d "client_id=$TWITCH_CLIENT_ID&client_secret=$TWITCH_CLIENT_SECRET&grant_type=client_credentials")
ACCESS_TOKEN=$(echo $ACCESS_TOKEN_RESPONSE | jq -r .access_token)
BROADCASTER_USER_ID=$(curl -s -H "Client-ID: $TWITCH_CLIENT_ID" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  "https://api.twitch.tv/helix/users?login=$TWITCH_USERNAME" | jq -r '.data[0].id')

# register eventsub subscription
curl -s -X POST 'https://api.twitch.tv/helix/eventsub/subscriptions' \
  -H "Client-ID: $TWITCH_CLIENT_ID" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d @- <<EOF | jq
{
  "type": "stream.online",
  "version": "1",
  "condition": {
    "broadcaster_user_id": "$BROADCASTER_USER_ID"
  },
  "transport": {
    "method": "webhook",
    "callback": "$TWITCH_WEBHOOK_URL",
    "secret": "$TWITCH_EVENTSUB_SECRET"
  }
}
EOF