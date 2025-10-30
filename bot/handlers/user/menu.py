from aiogram import types, Dispatcher
from bot.db import SessionLocal, User, Admin
from bot.keyboards.main_menu import main_menu, profile_menu, shop_menu, support_menu, play_menu

def _is_admin(uid: int) -> bool:
    with SessionLocal() as s:
        return bool(s.query(Admin).filter_by(telegram_id=uid).first())

# --- Открыть подменю ---

async def open_profile_menu(message: types.Message):
    await message.answer("🏠 Профиль", reply_markup=profile_menu())

async def open_shop_menu(message: types.Message):
    await message.answer("🛒 Магазин", reply_markup=shop_menu())

async def open_support_menu(message: types.Message):
    await message.answer("🆘 Поддержка\nНапишите ваш вопрос, нажав «✍️ Написать в поддержку».", reply_markup=support_menu())

async def open_play_menu(message: types.Message):
    # позже заменим на реальные ссылки/inline-кнопки
    await message.answer("🎮 Выберите сервер:", reply_markup=play_menu())

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

# --- Регистрация ---

def register_user_menu(dp: Dispatcher):
    dp.register_message_handler(open_profile_menu, lambda m: m.text == "🏠 Профиль")
    dp.register_message_handler(open_shop_menu,    lambda m: m.text == "🛒 Магазин")
    dp.register_message_handler(open_support_menu, lambda m: m.text == "🆘 Поддержка")
    dp.register_message_handler(open_play_menu,    lambda m: m.text == "🎮 Играть")
    dp.register_message_handler(back_to_main,      lambda m: m.text == "⬅️ Назад")

    # профиль: внутренние пункты
    dp.register_message_handler(profile_ref_link,  lambda m: m.text == "🔗 Реферальная ссылка")
    dp.register_message_handler(profile_promo,     lambda m: m.text == "🎟 Промокод")
    dp.register_message_handler(profile_topup,     lambda m: m.text == "💳 Пополнить баланс")
    dp.register_message_handler(profile_top,       lambda m: m.text == "🏆 Топ игроков")
