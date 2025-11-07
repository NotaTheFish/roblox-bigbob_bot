import os
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

os.environ.setdefault("TELEGRAM_TOKEN", "test:token")
os.environ.setdefault("ADMIN_LOGIN_PASSWORD", "DEFAULT")


from bot.services.stats import TopUserEntry, format_top_users


def test_format_top_users_with_entries():
    entries = [
        TopUserEntry(user_id=1, username="Alice", tg_username="alice", balance=200),
        TopUserEntry(user_id=2, username=None, tg_username="bob", balance=150),
        TopUserEntry(user_id=3, username=None, tg_username=None, balance=50),
    ]

    expected = (
        "🏆 Топ игроков:\n\n"
        "1. Alice — 200 💰\n"
        "2. @bob — 150 💰\n"
        "3. ID 3 — 50 💰"
    )

    assert format_top_users(entries) == expected


def test_format_top_users_empty():
    assert format_top_users([]) == "🏆 Топ игроков: пока нет данных"