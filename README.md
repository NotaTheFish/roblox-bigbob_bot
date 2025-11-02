# Roblox Telegram Bot ??

Production-ready Telegram bot for Roblox with Render deploy.

## Features

* Aiogram + Flask + PostgreSQL (async)
* Auto webhook
* Render deploy

## How to run

1\. Set the `DATABASE\_URL` environment variable to your PostgreSQL connection string

&nbsp;  (for example `postgresql+asyncpg://user:password@localhost:5432/database`).

2\. Install dependencies and create the database schema:



&nbsp;  ```bash

&nbsp;  pip install -r requirements.txt

&nbsp;  python create\_db.py

&nbsp;  ```



3\. Start the bot core:



&nbsp;  ```bash

&nbsp;  python bot/main\_core.py

&nbsp;  ```



