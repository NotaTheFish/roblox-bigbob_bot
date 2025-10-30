from aiogram import types, Dispatcher
from bot.db import SessionLocal, TopUpRequest, User
from bot.main_core import bot
from bot.utils.achievement_checker import check_achievements


async def approve_topup(call: types.CallbackQuery):
    req_id = int(call.data.split(":")[1])

    with SessionLocal() as s:
        req = s.query(TopUpRequest).filter_by(id=req_id).first()
        if not req or req.status != "pending":
            return await call.answer("Заявка не найдена", show_alert=True)

        user = s.query(User).filter_by(tg_id=req.user_id).first()
        if not user:
            req.status = "denied"
            s.commit()
            return await call.answer("Пользователь не найден", show_alert=True)

        # ✅ начисляем монеты
        user.balance += req.amount
        req.status = "approved"
        s.commit()

        # ✅ проверяем достижения здесь
        check_achievements(user)

    # ✅ после выхода из with — отправляем сообщения
    await bot.send_message(req.user_id, f"✅ Ваш баланс пополнен на {req.amount} монет!")
    await call.message.edit_text(f"✅ Заявка #{req_id} выполнена")
    await call.answer()


async def deny_topup(call: types.CallbackQuery):
    req_id = int(call.data.split(":")[1])

    with SessionLocal() as s:
        req = s.query(TopUpRequest).filter_by(id=req_id).first()
        if req:
            req.status = "denied"
            s.commit()

    await call.message.edit_text(f"❌ Заявка #{req_id} отклонена")

    try:
        await bot.send_message(req.user_id, f"❌ Ваша заявка #{req_id} отклонена")
    except:
        pass

    await call.answer()


def register_admin_payments(dp: Dispatcher):
    dp.register_callback_query_handler(approve_topup, lambda c: c.data.startswith("topup_ok"))
    dp.register_callback_query_handler(deny_topup, lambda c: c.data.starts
