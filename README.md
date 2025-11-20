# Roblox Telegram Bot ??

Production-ready Telegram bot for Roblox with Render deploy.

## Features

* Aiogram + Flask + PostgreSQL (async)
* Auto webhook
* Render deploy
* Consistent placeholder `@INKOGNITO_DROCHER` when a Telegram user has no public username

## Operator notes

Telegram occasionally hides usernames for privacy-focused users. Whenever that happens the
bot automatically substitutes the placeholder `@INKOGNITO_DROCHER`. If you see this
signature in admin-approval pop-ups or in the backend, it simply means the player did not
publish a Telegram handle—no manual action is required.

## Configuration

1. Copy the example environment file and populate the required secrets:

&nbsp;  ```bash
&nbsp;  cp .env.example .env
&nbsp;  ```

2. Edit `.env` and provide values for at least `TELEGRAM_TOKEN`, `ADMIN_LOGIN_PASSWORD`,
   `BACKEND_HMAC_SECRET`, and `DATABASE_URL`. The bot also expects `REDIS_URL` to point
   to your Redis instance (for example `redis://default:<PASSWORD>@<HOST>:<PORT>`); when
   unset it falls back to in-memory FSM storage, which is suitable only for local
   debugging because it loses state on restart. Optional settings such as `DOMAIN`,
   `ROBLOX_API_BASE_URL`, or Render-specific values (`SERVICE_ROLE`, `PORT`) can remain
   unchanged until you need them.

## How to run

1. Ensure your `.env` file is in place (see [Configuration](#configuration) above).

2. Install dependencies:



&nbsp;  ```bash

&nbsp;  pip install -r requirements.txt

&nbsp;  ```



3. Apply the database migrations. Set `DATABASE_URL`, `DATABASE_URL_SYNC`, or
   `DB_URL` to your PostgreSQL connection string **including**
   `?sslmode=require` when connecting to managed hosts such as Render/Railway,
   then run Alembic. For example:

   * **Windows PowerShell**

     ```powershell
     $env:DATABASE_URL = "postgresql+asyncpg://postgres:<PASSWORD>@<HOST>:<PORT>/railway?sslmode=require"
     alembic upgrade head
     ```

   * **macOS / Linux shell**

     ```bash
     export DATABASE_URL="postgresql+asyncpg://postgres:<PASSWORD>@<HOST>:<PORT>/railway?sslmode=require"
     alembic upgrade head
     ```



4. Start the bot core:



&nbsp;  ```bash

&nbsp;  python bot/main_core.py

&nbsp;  ```

## Updating the TON→nuts exchange rate

The Alembic migration `2d6da8b27afc_seed_ton_rate_setting` seeds the `settings`
table with a `ton_to_nuts_rate` entry (default value `210.0`) so the Telegram bot
always has a baseline rate for TON payments. To change the rate without touching
the database directly:

1. Make sure your account is approved as an admin (the same access level needed
   for the rest of the bot backoffice).
2. In Telegram, send `/tonrate <value>` (for example `/tonrate 215.5`) to the
   bot. The command accepts either `.` or `,` as the decimal separator and will
   reject non-positive numbers.
3. The bot confirms the previous and the new rate. Subsequent calls to
   `/topup` → “TON” will immediately reflect the updated exchange rate because
   the `topup_choose_ton` handler reads it from the `settings` table every time.

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

