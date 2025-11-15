"""Custom aiogram middlewares used by the bot."""

from .banned import BannedMiddleware

__all__ = ["BannedMiddleware"]