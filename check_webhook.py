import asyncio
from aiogram import Bot
from bot.config import TOKEN, DOMAIN

WEBHOOK_URL = f"{DOMAIN}/webhook/{TOKEN.split(':')[0]}"


async def check_webhook():
    bot = Bot(token=TOKEN)
    info = await bot.get_webhook_info()
    print("📡 Текущий вебхук:", info.url or "❌ Не установлен")

    if info.url != WEBHOOK_URL:
        print("🔄 Устанавливаю новый вебхук...")
        await bot.set_webhook(WEBHOOK_URL)
        print("✅ Вебхук установлен:", WEBHOOK_URL)
    else:
        print("✅ Вебхук уже установлен корректно")

    await bot.session.close()

asyncio.run(check_webhook())
