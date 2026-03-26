# Deploying Thuk to Fly.io

This guide assumes you have Migrated from Render or are deploying from scratch.

## Prerequisites

1. Install Fly.io CLI: https://fly.io/docs/hands-on/install-flyctl/
2. Run `fly auth login` to authenticate

## 1. Create the App

From the root directory, run:
```bash
fly launch --no-deploy
```

When asked, select `sin` (Singapore) as the region (closes to India) or your preferred region.
The `fly.toml` is already pre-configured.

## 2. Set Up Fly Postgres DB

```bash
fly postgres create --name thuk-db --region sin
fly postgres attach thuk-db --app thuk-bot
```
This automatically sets `DATABASE_URL` in your app.

## 3. Set Up Upstash Redis

```bash
fly redis create --name thuk-redis --region sin
```
Get the connection string and set it as `REDIS_URL`:
```bash
fly secrets set REDIS_URL=redis://default:3d1970d9d4e44a8093926c4931a33d99@fly-thuk-redis.upstash.io:6379
```

## 4. Set App Secrets

Set your required Twilio webhook credentials and encryption key:

```bash
fly secrets set \
  TWILIO_ACCOUNT_SID=AC18415783011291151424350257481585 \
  TWILIO_AUTH_TOKEN=1184dd7103e5a7068148518d5c9acfa2\
  ENCRYPTION_KEY=QAuWYo3PJMW-y0Zs7EhbimL2QA10SsPmlxzazDSYpGM= \
  WEBHOOK_BASE_URL=https://thuk-bot.fly.dev
```

## 5. Deploy!

```bash
fly deploy
```

## 6. Update Twilio

Log into Twilio Console:
1. Go to **WhatsApp Sandbox Settings**
2. In the "WHEN A MESSAGE COMES IN" field, put your public URL:
   `https://thuk-bot.fly.dev/webhook/whatsapp`
3. Save changes.

Done! Send `help` to your bot to test it.
