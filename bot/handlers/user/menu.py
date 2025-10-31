from aiogram import types, Dispatcher

from bot.db import SessionLocal, Admin
from bot.handlers.user.shop import user_shop
from bot.keyboards.main_menu import main_menu, profile_menu, shop_menu, support_menu, play_menu

def _is_admin(uid: int) -> bool:
    with SessionLocal() as s:
        return bool(s.query(Admin).filter_by(telegram_id=uid).first())

# --- Открыть подменю ---

async def open_profile_menu(message: types.Message):
    await message.answer("👤 Профиль", reply_markup=profile_menu())

async def open_shop_menu(message: types.Message):
    await message.answer("🛒 Магазин", reply_markup=shop_menu())

async def open_support_menu(message: types.Message):
    await message.answer("🆘 Поддержка\nНапишите ваш вопрос, нажав «✍️ Написать в поддержку».", reply_markup=support_menu())

async def open_play_menu(message: types.Message):
    # позже заменим на реальные ссылки/inline-кнопки
    await message.answer("🎮 Выберите сервер:", reply_markup=play_menu())


async def play_server_one(message: types.Message):
    await message.answer("🌐 Сервер #1: ссылка появится позже")


async def play_server_two(message: types.Message):
    await message.answer("🌐 Сервер #2: ссылка появится позже")


async def open_shop_items(message: types.Message):
    await user_shop(message, "item")


async def open_shop_privileges(message: types.Message):
    await user_shop(message, "privilege")


async def open_shop_currency(message: types.Message):
    await user_shop(message, "money")

# --- Назад в главное меню ---

async def back_to_main(message: types.Message):
    is_admin = _is_admin(message.from_user.id)
    await message.answer("↩ Главное меню", reply_markup=main_menu(is_admin=is_admin))

# --- Заглушки для внутренних пунктов профиля ---

async def profile_ref_link(message: types.Message):
    # TODO: подставить реальную ссылку
    await message.answer("🔗 Ваша реферальная ссылка: будет добавлено скоро.")

async def profile_promo(message: types.Message):
    await message.answer("🎟 Введите промокод командой: /promo CODE")

async def profile_topup(message: types.Message):
    await message.answer("💳 Пополнение: используйте /topup")

async def profile_top(message: types.Message):
    await message.answer("🏆 Топ игроков: скоро добавим красивый вывод!")


async def support_contact(message: types.Message):
    await message.answer(
        "✍️ Напишите @your_support или ответьте на это сообщение — мы поможем!",
    )

# --- Регистрация ---

def register_user_menu(dp: Dispatcher):
    dp.register_message_handler(open_profile_menu, lambda m: m.text == "👤 Профиль")
    dp.register_message_handler(open_shop_menu,    lambda m: m.text == "🛒 Магазин")
    dp.register_message_handler(open_support_menu, lambda m: m.text == "🆘 Поддержка")
    dp.register_message_handler(open_play_menu,    lambda m: m.text == "🎮 Играть")
    dp.register_message_handler(play_server_one,  lambda m: m.text == "🌐 Сервер #1")
    dp.register_message_handler(play_server_two,  lambda m: m.text == "🌐 Сервер #2")
    dp.register_message_handler(back_to_main,      lambda m: m.text == "⬅️ Назад")

    dp.register_message_handler(open_shop_items,      lambda m: m.text == "🎁 Предметы")
    dp.register_message_handler(open_shop_privileges, lambda m: m.text == "🛡 Привилегии")
    dp.register_message_handler(open_shop_currency,   lambda m: m.text == "💰 Кеш")

    # профиль: внутренние пункты
    dp.register_message_handler(profile_ref_link,  lambda m: m.text == "🔗 Реферальная ссылка")
    dp.register_message_handler(profile_promo,     lambda m: m.text == "🎟 Промокод")
    dp.register_message_handler(profile_topup,     lambda m: m.text == "💳 Пополнить баланс")
    dp.register_message_handler(profile_top,       lambda m: m.text == "🏆 Топ игроков")
    dp.register_message_handler(support_contact,   lambda m: m.text == "✍️ Написать в поддержку")
