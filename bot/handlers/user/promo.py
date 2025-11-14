"""Promo code command handler."""

from aiogram import Router, types
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext

from bot.states.user_states import PromoInputState
from .promocode_use import redeem_promocode


router = Router(name="user_promo")


@router.message(Command("promo"))
async def activate_promo(
    message: types.Message, command: CommandObject, state: FSMContext
):
    """Handle /promo command and kick off promo code redemption."""
    raw_code = (command.args or "").strip()

    if not raw_code:
        await state.set_state(PromoInputState.waiting_for_code)
        await message.reply("Введите код прямо в чат")
        return

    redeemed = await redeem_promocode(message, raw_code)

    if redeemed:
        current_state = await state.get_state()
        if current_state == PromoInputState.waiting_for_code.state:
            data = await state.get_data()
            in_profile = data.get("in_profile", False)
            await state.clear()
            if in_profile:
                await state.update_data(in_profile=True)