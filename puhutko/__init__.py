from contextlib import asynccontextmanager
from datetime import datetime, timedelta
import os
import asyncio
from dotenv import load_dotenv

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    CallbackQuery,
    Update,
)
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command
from aiogram import Bot, Dispatcher
from fastapi import FastAPI, Request

from .whitelist import WhitelistFilter
from .format import relative_time
from .score import sm2_next
from .card import Card
from .datastore import CardStats, Datastore

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", ":c")
DATASTORE = Datastore(os.getenv("REDIS_URL", "redis://localhost:6379/0"))

BOT = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))

dp = Dispatcher()

filter = WhitelistFilter()
dp.message.filter(filter)
dp.callback_query.filter(filter)


def main_review_kb(card_id: int, due_ts: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Flip", callback_data=f"flip:{card_id}:{due_ts}"
                ),
            ]
        ]
    )
    return kb


def grading_kb(card: Card) -> InlineKeyboardMarkup:
    qualities = [("Again", 1), ("Good", 4), ("Easy", 5)]
    buttons = []
    for label, q in qualities:
        interval, *_ = sm2_next(card, q)
        next_due = datetime.now() + timedelta(days=interval)
        btn_text = f"{label} ({relative_time(next_due)})"
        buttons.append(
            [
                InlineKeyboardButton(
                    text=btn_text, callback_data=f"grade:{card.card_id}:{q}"
                )
            ]
        )
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    return kb


@dp.message(Command(commands=["cram"]))
async def cmd_cram(message: Message):
    user = message.chat.id
    enabled = await DATASTORE.get_cram_mode(user)
    new_state = not enabled
    await DATASTORE.set_cram_mode(user, new_state)
    status = "enabled" if new_state else "disabled"

    await DATASTORE.log_event(user=user, event="cram", extra={"status": status})

    await message.answer(
        f"Cram mode is now <b>{status}</b>. Cards will {'ignore scheduling' if new_state else 'follow normal intervals'} during review."
    )


@dp.message(Command(commands=["stats"]))
async def cmd_stats(message: Message):
    user = message.chat.id
    stats: CardStats = await DATASTORE.stats(user)

    if stats.num_cards == 0:
        await message.answer("You have no cards yet. Add cards with `front\\n\\nback`.")
        return

    avg_dt = datetime.now() - timedelta(seconds=stats.avg_age_seconds)
    oldest_dt = datetime.now() - timedelta(seconds=stats.oldest_age_seconds)
    avg_age_str = relative_time(avg_dt)
    oldest_str = relative_time(oldest_dt)

    text = (
        f"<strong>Your Stats:</strong>\n"
        f"Total cards: <b>{stats.num_cards}</b>\n"
        f"Average time since last review: <b>{avg_age_str}</b>\n"
        f"Oldest review: <b>{oldest_str}</b>\n"
        f"Average repetitions: <b>{stats.avg_reps:.2f}</b>\n"
    )

    await message.answer(text)


@dp.message(Command(commands=["start"]))
async def cmd_start(message: Message):
    user = message.chat.id

    cram = await DATASTORE.get_cram_mode(user)
    popped = await DATASTORE.pop_one_due(user, cram=cram)
    if not popped:
        await message.answer(
            "No cards are due for review. Add some with `front\\nback` messages."
        )
        return

    card_id, due_ts = popped
    card = await DATASTORE.get_card(user, card_id)

    if not card:
        await message.answer("Card not found (it may have been deleted).")
        return

    await DATASTORE.log_event(user=user, event="show_card", card_id=card.card_id)

    text = f"{card.front}"
    kb = main_review_kb(card.card_id, due_ts)
    await message.answer(text, reply_markup=kb)


@dp.message()
async def on_message_create_card(message: Message):
    user = message.chat.id

    text = (message.text or "").strip()
    if not text:
        return

    if "\n" not in text:
        await message.reply(
            "To add a card send: `front\\nback` (a newline between front and back)."
        )
        return

    front, back = text.split("\n", 1)
    front = front.strip()
    back = back.strip()
    if not front or not back:
        await message.reply("Both front and back must be non-empty.")
        return

    card = Card.simple(front, back, True)
    await DATASTORE.save_card(user, card, next_due=datetime.now())
    await message.reply(f"<strong>Created <code>{card.card_id}</code>!</strong>")


@dp.callback_query()
async def on_callback(call: CallbackQuery):
    user = call.from_user.id
    data = call.data or ""
    parts = data.split(":")
    if len(parts) < 3:
        await call.answer("Invalid action", show_alert=True)
        return

    action = parts[0]

    if action == "flip":
        try:
            card_id = int(parts[1])
        except Exception:
            await call.answer("Invalid flip parameters", show_alert=True)
            return

        card = await DATASTORE.get_card(user, card_id)
        if not card:
            await call.answer("Card disappeared", show_alert=True)
            return

        await DATASTORE.log_event(user=user, event="flip_card", card_id=card.card_id)

        new_text = f"{card.front}\n\n{card.back}"
        kb = grading_kb(card)
        try:
            await call.message.edit_text(new_text, reply_markup=kb)  # type: ignore
        except Exception:
            await call.message.answer(new_text, reply_markup=kb)  # type: ignore
        await call.answer()
        return

    if action == "grade":
        try:
            card_id = int(parts[1])
            q = int(parts[2])
        except Exception:
            await call.answer("Invalid grade parameters", show_alert=True)
            return

        card = await DATASTORE.get_card(user, card_id)
        if not card:
            await call.answer("Card not found", show_alert=True)
            return

        await DATASTORE.log_event(
            user=user,
            event="grade_card",
            card_id=card.card_id,
            extra={
                "quality": q,
                "interval_days": card.interval,
                "ease_factor": card.ease_factor,
            },
        )

        new_interval_days, new_ef, new_reps = sm2_next(card, q)
        card.interval = int(new_interval_days)
        card.ease_factor = float(new_ef)
        card.repetitions = int(new_reps)
        card.last_review = datetime.now()

        next_due = datetime.now() + timedelta(days=new_interval_days)
        await DATASTORE.save_card(user, card, next_due=next_due)

        final_text = f"{card.front}\n{card.back}\n\n<strong>Scheduled: {relative_time(next_due)}</strong>"
        try:
            await call.message.edit_text(final_text, reply_markup=None)  # type: ignore
        except Exception:
            await call.message.answer(final_text)  # type: ignore

        await call.answer("Answer recorded. Good job!")

        next_entry = await DATASTORE.pop_one_due(user)
        if next_entry:
            next_card_id, next_due_ts = next_entry
            next_card = await DATASTORE.get_card(user, next_card_id)
            if next_card:
                kb = main_review_kb(next_card.card_id, next_due_ts)
                await call.message.answer(next_card.front, reply_markup=kb)  # type: ignore
        else:
            await call.message.answer(  # type: ignore
                "No more cards due right now. Add more with `front\\n\\nback`."
            )
        return

    await call.answer("Unknown action", show_alert=True)


PUBLIC_DOMAIN = os.getenv("RAILWAY_PUBLIC_DOMAIN", None)

if PUBLIC_DOMAIN:

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await BOT.set_webhook(WEBHOOK_URL)
        print(f"Webhook set: {WEBHOOK_URL}")
        try:
            yield
        finally:
            await BOT.delete_webhook()
            await BOT.session.close()
            print("Webhook deleted and bot session closed")

    app = FastAPI(lifespan=lifespan)

    WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"
    WEBHOOK_URL = f"https://{PUBLIC_DOMAIN}{WEBHOOK_PATH}"

    @app.post(WEBHOOK_PATH)
    async def telegram_webhook(req: Request):
        data = await req.json()
        update = Update(**data)
        await dp.feed_update(BOT, update)
        return {"ok": True}

else:

    async def main():
        try:
            print("Bot started. Polling...")
            await dp.start_polling(BOT)
        finally:
            await BOT.session.close()

    if __name__ == "__main__":
        asyncio.run(main())
