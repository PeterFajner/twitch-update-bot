from flask import Flask, request, jsonify
import hmac
import hashlib
import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
TWITCH_EVENTSUB_SECRET = os.getenv("TWITCH_EVENTSUB_SECRET")

def verify_signature(headers, body):
    received_sig = headers.get("Twitch-Eventsub-Message-Signature", "")
    message_id = headers.get("Twitch-Eventsub-Message-Id", "")
    timestamp = headers.get("Twitch-Eventsub-Message-Timestamp", "")

    hmac_message = message_id + timestamp + body
    expected_sig = hmac.new(
        TWITCH_EVENTSUB_SECRET.encode(),
        msg=hmac_message.encode(),
        digestmod=hashlib.sha256
    ).hexdigest()

    return f"sha256={expected_sig}" == received_sig

@app.route("/", methods=["POST"])
def handle_eventsub():
    body = request.data.decode("utf-8")

    if not verify_signature(request.headers, body):
        return "Signature verification failed", 403

    data = request.get_json()

    # Respond to challenge
    if data["subscription"]["type"] == "stream.online" and "challenge" in data:
        return data["challenge"], 200

    # Handle live notification
    if data.get("subscription", {}).get("type") == "stream.online":
        username = data["event"]["broadcaster_user_name"]
        stream_url = f"https://twitch.tv/{username}"
        payload = {
            "content": f"🔴 **{username} is live!**\n{stream_url}"
        }
        response = requests.post(DISCORD_WEBHOOK_URL, json=payload)
        print('response from discord', response)

    return "", 204

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)