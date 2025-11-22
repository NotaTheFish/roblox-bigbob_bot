from bot import config
from bot.handlers.user import messages


def test_secret_word_throttle_blocks_quick_reuse():
    messages.last_secret_word_use.clear()

    user_id = 12345
    base_time = 100.0

    assert messages._should_throttle_secret_word(user_id, now=base_time) is False
    assert (
        messages._should_throttle_secret_word(
            user_id, now=base_time + config.SECRET_WORD_THROTTLE_SECONDS - 0.1
        )
        is True
    )
    assert (
        messages._should_throttle_secret_word(
            user_id, now=base_time + config.SECRET_WORD_THROTTLE_SECONDS + 0.1
        )
        is False
    )