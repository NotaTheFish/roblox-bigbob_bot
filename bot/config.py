# bot/config.py

TOKEN = "8460465818:AAGsCqOGndRS3GfJfLIOil0Gtqfct9uq_88"  # токен бота в кавычках
ADMINS = [5813380332, 1748138420]  # Telegram ID админов
DATABASE_URL = "sqlite:///data/db_v2.sqlite3"  # путь к базе данных
SECRET_KEY = "BIG2025BOB"  # секретный ключ (может использоваться для сессий)
DOMAIN = "https://roblox-bigbob-bot.onrender.com"  # адрес твоего веб-сервера
WEBHOOK_URL = f"{DOMAIN}/webhook/{TOKEN.split(':')[0]}"
  # полный URL для вебхука
