"""Custom aiogram middlewares used by the bot."""

from .anti_spam import AntiSpamMiddleware
from .banned import BannedMiddleware
from .bot_status import BotStatusMiddleware
from .callback_dedup import CallbackDedupMiddleware
from .user_sync import UserSyncMiddleware

__all__ = [
    "AntiSpamMiddleware",
    "BannedMiddleware",
    "BotStatusMiddleware",
    "CallbackDedupMiddleware",
    "UserSyncMiddleware",
]
