"""Shared aiogram bot instance."""

from aiogram import Bot
from aiogram.enums import ParseMode

from bot.config import TOKEN


bot = Bot(token=TOKEN, parse_mode=ParseMode.HTML)
