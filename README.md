# Roblox Telegram Bot ??

Production-ready Telegram bot for Roblox with Render deploy.

## Features

* Aiogram + Flask + PostgreSQL (async)
* Auto webhook
* Render deploy

## Configuration

1. Copy the example environment file and populate the required secrets:

&nbsp;  ```bash
&nbsp;  cp .env.example .env
&nbsp;  ```

2. Edit `.env` and provide values for at least `TELEGRAM_TOKEN`, `ADMIN_LOGIN_PASSWORD`,
   `BACKEND_HMAC_SECRET`, and `DATABASE_URL`. Optional settings such as `DOMAIN`,
   `ROBLOX_API_BASE_URL`, or Render-specific values (`SERVICE_ROLE`, `PORT`) can remain
   unchanged until you need them.

## How to run

1. Ensure your `.env` file is in place (see [Configuration](#configuration) above).

2. Install dependencies:



&nbsp;  ```bash

&nbsp;  pip install -r requirements.txt

&nbsp;  ```



3. Apply the database migrations (set `DATABASE_URL`, `DATABASE_URL_SYNC`, or `DB_URL`):



&nbsp;  ```bash

&nbsp;  alembic upgrade head

&nbsp;  ```



4. Start the bot core:



&nbsp;  ```bash

&nbsp;  python bot/main_core.py

&nbsp;  ```

## API testing with Postman

Import the collection under [`docs/postman/collection.json`](docs/postman/collection.json)
to exercise every backend endpoint from Postman (or any compatible client). The companion
environment file [`docs/postman/environment.json`](docs/postman/environment.json)
pre-populates variables for the base URL, HMAC secret, reusable idempotency keys, and
sample Roblox identifiers used in the example payloads. Update the environment values to
match your deployment before sending requests.

## Deploying to Render

Before deploying via `render.yaml`, copy `.env.example` to `.env` and provide the same
secrets used locally. Render will read the values defined in `.env` when synchronising
environment variables for the `roblox-backend` and `roblox-bot` services. See
[DEPLOYMENT.md](DEPLOYMENT.md) for a step-by-step walkthrough. When applying schema
changes in production, open the Render shell for the backend service (or run your
automation script) and execute `alembic upgrade head` before restarting workers so the
database stays in sync.

