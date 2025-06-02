# Setup secrets
```
cp .env.example .env
```

You'll need a Twitch application and a Discord webhook, fill in the secrets in `.env`. To generate an EventSub secret, run `openssl rand -hex 32`.

# Script to post new clips
Setup `check_clips_and_post.sh` to run with a cron job (max 30 requests per minute).

# Script to post when you start streaming

1. Install fcgiwrap and nginx
2. Setup a nginx server, replacing `your-domain.com` and the location of the script:

```
server {
    listen 80;
    server_name your-domain.com
    location /twitch {
        include fastcgi_params;
        fastcgi_pass unix:/var/run/fcgiwrap.socket;
        fastcgi_param SCRIPT_FILENAME /home/twitch/twitch-update-bot/streaming_subscription.sh
    }
}
```

3. Use certbot to setup HTTPS for your-domain.com
4. Setup EventSub by running `register_eventsub.sh`