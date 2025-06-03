# Setup secrets
```
cp .env.example .env
```

You'll need a Twitch application and a Discord webhook, fill in the secrets in `.env`. Setup an HTTPS URL to be your EventSub incoming URL, and proxy nginx from that URL to LOCAL_PORT (default 3000):

```
server {
    server_name your-domain.com;
    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```
