# bot/web_server.py

from flask import Flask, request
from threading import Thread
from bot.config import TOKEN
from aiogram import Bot, Dispatcher, types
from bot.main_core import bot, dp

WEBHOOK_PATH = f"/webhook/{TOKEN.split(':')[0]}"
WEBAPP_HOST = "0.0.0.0"
WEBAPP_PORT = 8080

app = Flask(__name__)

@app.route('/')
def index():
    return "✅ Бот работает!"

@app.route(WEBHOOK_PATH, methods=["POST"])
async def webhook_handler():
    try:
        data = request.get_json(force=True)
        update = types.Update(**data)
        await dp.feed_update(bot, update)
        return "OK", 200
    except Exception as e:
        print(f"❌ Ошибка при обработке webhook: {e}")
        return "Internal Server Error", 500

def run():
    app.run(host=WEBAPP_HOST, port=WEBAPP_PORT)

def keep_alive():
    t = Thread(target=run)
    t.start()
