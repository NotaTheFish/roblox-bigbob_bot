import asyncio
from aiogram import Bot
from bot.config import TOKEN, DOMAIN

WEBHOOK_PATH = f"/webhook/{TOKEN.split(':')[0]}"
WEBHOOK_URL = f"{DOMAIN}{WEBHOOK_PATH}"

bot = Bot(token=TOKEN)

async def check_webhook():
    current_webhook = await bot.get_webhook_info()
    print(f"📡 Текущий вебхук: {current_webhook.url or '❌ Не установлен'}")

    if current_webhook.url != WEBHOOK_URL:
        print("🔄 Устанавливаю новый вебхук...")
        await bot.set_webhook(WEBHOOK_URL)
        print(f"✅ Вебхук установлен: {WEBHOOK_URL}")
    else:
        print("✅ Вебхук уже корректный.")

    await bot.session.close()

if __name__ == "__main__":
    asyncio.run(check_webhook())
