# Deploy Argamag to Fly.io

The auto-generated URL will be `https://argamag.fly.dev` (change `argamag` in
`fly.toml` if you want a different subdomain).

## One-time setup

### 1. Install flyctl

```bash
brew install flyctl
```

### 2. Sign up / log in

```bash
fly auth signup   # first time — adds a credit card (required, but free tier covers low traffic)
fly auth login    # subsequent
```

### 3. Launch the app (skips Fly's wizard since we already have fly.toml)

```bash
cd /Users/batjinlamjav/Documents/personal/argamag
fly launch --no-deploy --copy-config --name argamag --region nrt
```

If `argamag` is taken globally, pick another name (`argamag-mongolia`, etc.)
and update the `app` field in `fly.toml` to match.

### 4. Create the persistent volume

```bash
fly volumes create argamag_data --region nrt --size 1   # 1 GB is plenty to start
```

### 5. Set the secret key

```bash
fly secrets set SECRET_KEY="$(openssl rand -hex 32)"
```

### 6. First deploy

```bash
fly deploy
```

When it finishes, your app is live at `https://argamag.fly.dev`. Visit it — you'll see the login screen.

### 7. Create user accounts (run against the deployed instance)

`fly ssh console` opens a shell on the running machine; the volume is mounted at `/data`.

```bash
fly ssh console
# now inside the container:
cd /app
python backend/manage.py create-user batjargal --full-name 'Батжаргал'
# ...prompted for password (twice)
python backend/manage.py create-user altanbat --full-name 'Алтанбат'
python backend/manage.py list-users
exit
```

`getpass` needs a TTY, so use interactive `fly ssh console` (not `-C "..."`).

## Day-to-day commands

```bash
fly deploy                              # redeploy after git changes
fly logs                                # tail server logs
fly status                              # is the machine running?
fly ssh console                         # shell into the machine
fly secrets set CORS_ORIGINS="..."      # update env vars (auto-redeploys)
fly volumes list                        # see volume usage
```

## If something breaks

```bash
fly releases                            # list deploy history
fly releases rollback <version>         # roll back to a previous deploy
```

Volume snapshots (Fly takes daily snapshots automatically for 5 days):

```bash
fly volumes snapshots list <volume-id>
fly volumes snapshots restore <snapshot-id>
```

## Seeding the existing horse data (one-time)

The local `data/horse.db` has your dad's 368 horses already. To push it to Fly:

```bash
# 1. Copy the local DB into the running machine's volume
fly ssh sftp shell
# at the sftp prompt:
put data/horse.db /data/horse.db
exit

# 2. Restart so the app picks it up
fly apps restart argamag
```

## Costs (rough)

- 1 GB volume: ~$0.15/mo
- shared-cpu-1x, 256MB, auto-stopped when idle: ~$0–2/mo for low family use
- Bandwidth: free under 100GB/mo
- Custom domain TLS: free

Expect $1–3/mo total for a few brothers checking it a few times a week.

## When you have a custom domain

```bash
fly certs add argamag.mn
# Add the DNS records it tells you to
fly certs check argamag.mn

# Then lock CORS to the new origin
fly secrets set CORS_ORIGINS="https://argamag.mn,https://argamag.fly.dev"
```
