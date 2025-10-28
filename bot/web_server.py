# bot/web_server.py

from flask import Flask, request
from threading import Thread
from bot.config import TOKEN, WEBHOOK_URL
from aiogram import types
from aiogram.utils.executor import start_webhook
from bot.main import dp, bot  # убедись, что main импортирует dp и bot

WEBHOOK_PATH = f"/webhook/{TOKEN.split(':')[0]}"
WEBAPP_HOST = "0.0.0.0"
WEBAPP_PORT = 8080

app = Flask(__name__)

@app.route('/')
def index():
    return "✅ Бот работает!"

@app.route(WEBHOOK_PATH, methods=["POST"])
def webhook_handler():
    update = types.Update.de_json(request.get_json(force=True))
    dp.process_update(update)
    return "OK", 200

def run():
    app.run(host=WEBAPP_HOST, port=WEBAPP_PORT)

def keep_alive():
    t = Thread(target=run)
    t.start()
