\# Render Deployment Guide



This project ships with a \[`render.yaml`](render.yaml) descriptor that provisions two

services: the FastAPI backend (`roblox-backend`) and the Telegram bot webhook handler

(`roblox-bot`).



\## 1. Prepare environment variables



1\. Copy the example file and fill in the required secrets:



&nbsp;  ```bash

&nbsp;  cp .env.example .env

&nbsp;  ```



2\. Populate the values in `.env`:

&nbsp;  \* `TELEGRAM\_TOKEN`

&nbsp;  \* `ADMIN\_LOGIN\_PASSWORD`

&nbsp;  \* `BACKEND\_HMAC\_SECRET`

&nbsp;  \* `DATABASE\_URL`

&nbsp;  \* `REDIS\_URL` (for example `redis://default:<PASSWORD>@<HOST>:<PORT>`). If omitted the
&nbsp;    bot will run with in-memory FSM storage that loses conversation state on restart, so
&nbsp;    configure Redis for production.

&nbsp;  \* Any optional settings you plan to use (`DOMAIN`, `ROBLOX\_API\_BASE\_URL`,

&nbsp;    `TELEGRAM\_PAYMENT\_SECRET`, etc.).



3\. In the Render dashboard, create the `roblox-backend` and `roblox-bot` services from

&nbsp;  this repository and use the "Copy from .env file" option to sync values from your

&nbsp;  local `.env` file. This keeps local development and hosted environments in sync.



\## 2. Deploy



1\. Push the repository to GitHub (or another provider Render supports).

2\. From the Render dashboard, import the project and ensure it uses the provided

&nbsp;  \[`render.yaml`](render.yaml).

3\. On the first deploy Render will run `render\_start.sh`, using the `SERVICE\_ROLE`

&nbsp;  variable from `.env` to decide whether a container runs the backend or bot process.

4\. After the services are live, Render executes `python3 auto\_set\_webhook.py` for the

&nbsp;  bot service, so make sure the webhook related values (`DOMAIN`, `WEBHOOK\_PATH`,

&nbsp;  optional `WEBHOOK\_URL`) are set in your `.env` before syncing the environment.

5\. Before restarting services when new migrations are deployed, open the Render shell for
&nbsp;  `roblox-backend` (or run your deployment script) and execute `alembic upgrade head`
&nbsp;  so the database schema stays current.

6\. Verify the deployment with the Postman collection in
&nbsp;  [`docs/postman/collection.json`](docs/postman/collection.json) and the companion
&nbsp;  environment file [`docs/postman/environment.json`](docs/postman/environment.json).



\## 3. Keep secrets updated



When secrets change, update `.env` locally and use Render's dashboard to resync the

changes to both services. Commit the updated `.env.example` to share new variables with

the rest of the team.

