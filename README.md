# Setup secrets
```
cp .env.example .env
```

You'll need a Twitch application and a Discord webhook, fill in the secrets in `.env`. Setup an HTTPS URL to be your EventSub incoming URL, and proxy nginx from that URL to LOCAL_PORT (default 3000):

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
