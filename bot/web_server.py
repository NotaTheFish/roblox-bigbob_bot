# bot/web_server.py

from flask import Flask, request
from threading import Thread
from aiogram import types
from bot.main import dp, bot  # импортируем dispatcher и bot

app = Flask(__name__)

# ⚙️ важно: указываем именно такой путь!
WEBHOOK_PATH = f"/webhook/8460465818"

@app.route('/')
def index():
    return "✅ Бот работает!"

# 🧠 правильная обработка вебхука
@app.route(WEBHOOK_PATH, methods=['POST'])
def webhook_handler():
    update = types.Update.de_json(request.get_json(force=True))
    bot.loop.create_task(dp.process_update(update))
    return "OK", 200

def run():
    app.run(host="0.0.0.0", port=10000)  # Render слушает именно 10000 порт

def keep_alive():
    t = Thread(target=run)
    t.start()
