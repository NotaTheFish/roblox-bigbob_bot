# bot/web_server.py

from flask import Flask, request
from threading import Thread
from aiogram import types
from bot.main_core import dp, bot  # ✅ импорт из отдельного файла (см. ниже)

app = Flask(__name__)

WEBHOOK_PATH = f"/webhook/8460465818"

@app.route('/')
def index():
    return "✅ Бот работает!"

@app.route(WEBHOOK_PATH, methods=['POST'])
def webhook_handler():
    update = types.Update.de_json(request.get_json(force=True))
    bot.loop.create_task(dp.process_update(update))
    return "OK", 200

def run():
    app.run(host="0.0.0.0", port=10000)

def keep_alive():
    t = Thread(target=run)
    t.start()
