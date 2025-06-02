# Setup secrets
```
cp .env.example .env
```

You'll need a Twitch application and a Discord webhook, fill in the secrets in `.env`.

# Script to post new clips
Setup `check_clips_and_post.sh` to run with a cron job (max 30 requests per minute).

# Script to post when you start streaming