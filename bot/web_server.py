import asyncio
import atexit
from threading import Thread

from aiogram import types
from flask import Flask, request

from bot.bot_instance import bot
from bot.config import TOKEN
from bot.main_core import build_dispatcher, on_shutdown, on_startup

WEBHOOK_PATH = f"/webhook/{TOKEN.split(':')[0]}"
WEBAPP_HOST = "0.0.0.0"
WEBAPP_PORT = 8080

app = Flask(__name__)
dispatcher = build_dispatcher()
asyncio.run(on_startup(dispatcher))
atexit.register(lambda: asyncio.run(on_shutdown(dispatcher)))


@app.route("/")
def index():
    return "✅ Бот работает!"


@app.route(WEBHOOK_PATH, methods=["POST"])
def webhook_handler():
    try:
        data = request.get_json(force=True)
        update = types.Update(**data)
        asyncio.run(dispatcher.feed_update(bot, update))
        return "OK", 200
    except Exception as e:
        print(f"❌ Ошибка при обработке webhook: {e}")
        return "Internal Server Error", 500


def run():
    app.run(host=WEBAPP_HOST, port=WEBAPP_PORT)


def keep_alive():
    t = Thread(target=run)
    t.start()
