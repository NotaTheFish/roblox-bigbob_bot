import pytest
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, User

from bot.middleware.callback_dedup import CallbackDedupMiddleware


class RecordingMessage:
    def __init__(
        self,
        text: str,
        reply_markup: InlineKeyboardMarkup | None = None,
        *,
        chat_id: int = 1,
        message_id: int = 1,
    ) -> None:
        self.text = text
        self.reply_markup = reply_markup
        self.chat = type("Chat", (), {"id": chat_id})()
        self.message_id = message_id
        self.edit_text_calls: list[tuple[str, dict]] = []
        self.edit_markup_calls: list[tuple[InlineKeyboardMarkup | None, dict]] = []

    async def edit_text(self, text: str, **kwargs):
        self.edit_text_calls.append((text, kwargs))
        self.text = text
        if "reply_markup" in kwargs:
            self.reply_markup = kwargs.get("reply_markup")
        return text

    async def edit_reply_markup(self, reply_markup: InlineKeyboardMarkup | None = None, **kwargs):
        self.edit_markup_calls.append((reply_markup, kwargs))
        self.reply_markup = reply_markup
        return reply_markup


async def build_callback(message: RecordingMessage, data: str = "cb:1") -> CallbackQuery:
    callback = CallbackQuery.model_construct(
        id="1",
        from_user=User.model_construct(id=1, is_bot=False, first_name="Test"),
        chat_instance="instance",
        data=data,
        message=message,
    )
    answers: list[tuple[str | None, bool]] = []

    async def answer(text: str | None = None, show_alert: bool = False):
        answers.append((text, show_alert))
        return None

    object.__setattr__(callback, "answers", answers)
    object.__setattr__(callback, "answer", answer)
    return callback


@pytest.mark.anyio
async def test_duplicate_callback_skip_edit():
    markup = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="1", callback_data="page:1")]])
    message = RecordingMessage("Page 1", reply_markup=markup)
    callback = await build_callback(message)
    middleware = CallbackDedupMiddleware(hint="Already updated")

    async def handler(event, data):
        assert event.message is message
        await data["event_message"].edit_text("Page 1", reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="1", callback_data="page:1")]]
        ))
        return "handled"

    result = await middleware(handler, callback, {})

    assert result == "handled"
    assert message.edit_text_calls == []
    assert callback.answers == [("Already updated", False)]


@pytest.mark.anyio
async def test_edits_allowed_when_content_changes():
    markup = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="1", callback_data="page:1")]])
    updated_markup = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="2", callback_data="page:2")]])
    message = RecordingMessage("Page 1", reply_markup=markup)
    callback = await build_callback(message, data="cb:2")
    middleware = CallbackDedupMiddleware(hint=None)

    async def handler(event, data):
        assert event.message is message
        await data["event_message"].edit_text("Page 2", reply_markup=updated_markup)
        await data["event_message"].edit_reply_markup(reply_markup=updated_markup)
        return "handled"

    result = await middleware(handler, callback, {})

    assert result == "handled"
    assert message.edit_text_calls == [("Page 2", {"reply_markup": updated_markup})]
    assert message.edit_markup_calls == []
    assert callback.answers == [(None, False)]

    # Repeat the same callback press to ensure dedup now answers instead of editing again.
    repeat_callback = await build_callback(message, data="cb:2")

    async def repeat_handler(event, data):
        assert event.message is message
        await data["event_message"].edit_text("Page 2", reply_markup=updated_markup)

    await middleware(repeat_handler, repeat_callback, {})

    assert message.edit_text_calls == [("Page 2", {"reply_markup": updated_markup})]
    assert repeat_callback.answers == [(None, False)]


@pytest.mark.anyio
async def test_logs_callbacks_are_not_wrapped():
    message = RecordingMessage("Logs", reply_markup=None)
    callback = await build_callback(message, data="logs:next")
    middleware = CallbackDedupMiddleware(hint="Already updated")

    async def handler(event, data):
        await event.message.edit_text("Updated via logs")
        return "event_message" not in data and event.message is message

    result = await middleware(handler, callback, {})

    assert result is True
    assert message.edit_text_calls == [("Updated via logs", {})]
    assert callback.answers == []