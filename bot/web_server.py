# bot/web_server.py

from flask import Flask, request
from threading import Thread
from bot.config import TOKEN
from aiogram import types
from bot.main_core import bot, dp
import asyncio

WEBHOOK_PATH = f"/webhook/{TOKEN.split(':')[0]}"
WEBAPP_HOST = "0.0.0.0"
WEBAPP_PORT = 8080

app = Flask(__name__)

@app.route('/')
def index():
    return "✅ Бот работает!"

@app.route(WEBHOOK_PATH, methods=["POST"])
def webhook_handler():
    try:
        data = request.get_json(force=True)

        # Устанавливаем текущие экземпляры бота и диспетчера
        bot.set_current(bot)
        dp.set_current(dp)

        update = types.Update(**data)
        asyncio.run(dp.process_update(update))
        return "OK", 200
    except Exception as e:
        print(f"❌ Ошибка при обработке webhook: {e}")
        return "Internal Server Error", 500

def run():
    app.run(host=WEBAPP_HOST, port=WEBAPP_PORT)

def keep_alive():
    t = Thread(target=run)
    t.start()
