import asyncio
import logging
import os
from contextlib import asynccontextmanager

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request

import commands
import notes
import tasks

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_API = f"https://api.telegram.org/bot{TOKEN}"

_pending: dict[int, commands.PendingEvent] = {}
_owner_chat_id: int | None = int(os.environ["OWNER_CHAT_ID"]) if os.environ.get("OWNER_CHAT_ID") else None
_PC_COLLABORATOR_IDS: set[int] = {
    int(x.strip()) for x in os.environ.get("PC_COLLABORATOR_IDS", "").split(",") if x.strip()
}

# Commands collaborators can use without [pc] prefix
_READ_CMDS = {"/today", "/tomorrow", "/week", "/on", "/summary", "/help", "/start"}
# Commands collaborators can use only when args begin with [pc]
_PC_WRITE_CMDS = {"/add", "/edit", "/delete"}


def _is_owner(chat_id: int) -> bool:
    return chat_id == _owner_chat_id


def _is_collaborator(chat_id: int) -> bool:
    return chat_id in _PC_COLLABORATOR_IDS


def _is_known(chat_id: int) -> bool:
    return _is_owner(chat_id) or _is_collaborator(chat_id)


async def _send_weekly_summary() -> None:
    global _owner_chat_id
    if not _owner_chat_id:
        logger.warning("No OWNER_CHAT_ID set — skipping weekly summary notification")
        return
    try:
        text = commands.handle_weekly_preview()
        await _send(_owner_chat_id, text)
        logger.info("Sent weekly summary to chat_id=%s", _owner_chat_id)
    except Exception:
        logger.exception("Error sending weekly summary")


async def _send_morning_briefing() -> None:
    global _owner_chat_id
    if not _owner_chat_id:
        logger.warning("No OWNER_CHAT_ID set — skipping morning briefing")
        return
    try:
        text = commands.handle_today()
        await _send(_owner_chat_id, text)
        logger.info("Sent morning briefing to chat_id=%s", _owner_chat_id)
    except Exception:
        logger.exception("Error sending morning briefing")


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = AsyncIOScheduler(timezone="America/New_York")
    scheduler.add_job(
        _send_weekly_summary,
        CronTrigger(day_of_week="sun", hour=20, minute=0, timezone="America/New_York"),
    )
    scheduler.add_job(
        _send_morning_briefing,
        CronTrigger(hour=7, minute=0, timezone="America/New_York"),
    )
    scheduler.start()
    logger.info("Scheduler started — morning briefing 7:00 AM ET daily, weekly summary Sunday 8:00 PM ET")
    yield
    scheduler.shutdown()


app = FastAPI(lifespan=lifespan)


async def _send(chat_id: int, text: str) -> None:
    async with httpx.AsyncClient() as client:
        await client.post(
            f"{TELEGRAM_API}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"},
        )


def _route(text: str) -> str:
    parts = text.split(None, 1)
    cmd = parts[0].lower()
    args = parts[1].strip() if len(parts) > 1 else ""

    if cmd == "/add":
        return commands.handle_add(args)
    if cmd == "/avdg":
        return commands.handle_avdg(args)
    if cmd == "/delete":
        return commands.handle_delete(args)
    if cmd == "/edit":
        return commands.handle_edit(args)
    if cmd == "/summary":
        return commands.handle_summary()
    if cmd == "/week":
        return commands.handle_week()
    if cmd == "/today":
        return commands.handle_today()
    if cmd == "/tomorrow":
        return commands.handle_tomorrow()
    if cmd == "/on":
        return commands.handle_on(args)
    if cmd in ("/help", "/start"):
        return commands.HELP_TEXT
    if cmd == "/note":
        return notes.handle_note(args)
    if cmd == "/notes":
        return notes.handle_notes()
    if cmd == "/task":
        return tasks.handle_task(args)
    if cmd == "/suggestions":
        return commands.handle_suggestions(args)
    return "Unknown command — send /help for the command list."


async def _handle(data: dict) -> None:
    message = data.get("message") or data.get("edited_message")
    if not message:
        return

    global _owner_chat_id
    chat_id: int = message["chat"]["id"]
    text: str = message.get("text", "").strip()

    if _owner_chat_id is None:
        _owner_chat_id = chat_id
        logger.info("Owner chat_id set to %s", chat_id)

    # Silently drop messages from unknown users
    if not _is_known(chat_id):
        logger.info("Rejected unknown chat_id=%s", chat_id)
        return

    logger.info("Incoming from chat_id=%s: %r", chat_id, text)

    if not text:
        return

    # Pending color selection — user is replying with a category choice
    if not text.startswith("/") and chat_id in _pending:
        color_id = commands.parse_category_reply(text)
        if color_id is None:
            await _send(chat_id, "Didn't get that — reply with a number (1–7) or category name.")
            return
        pending = _pending.pop(chat_id)
        try:
            reply = commands.complete_pending(pending, color_id)
            logger.info("Completed pending event: %r", reply[:80])
            await _send(chat_id, reply)
        except Exception as e:
            logger.exception("Error completing pending event")
            await _send(chat_id, f"Something went wrong: {e}")
        return

    if not text.startswith("/"):
        await _send(chat_id, "Send a command — try /help to see what's available.")
        return

    # Collaborators are restricted to read commands and [pc]-prefixed write commands
    if _is_collaborator(chat_id):
        parts = text.split(None, 1)
        cmd = parts[0].lower()
        args = parts[1].strip() if len(parts) > 1 else ""
        if cmd not in _READ_CMDS:
            if cmd in _PC_WRITE_CMDS and args.lower().startswith("[pc]"):
                pass  # allowed
            elif cmd in _PC_WRITE_CMDS:
                await _send(chat_id, f"You can only manage Project Cook events. Add [pc] to your command — e.g. `{cmd} [pc] ...`")
                return
            else:
                await _send(chat_id, f"You don't have access to {cmd}.")
                return

    try:
        reply = _route(text)
        if isinstance(reply, commands.PendingEvent):
            _pending[chat_id] = reply
            reply = reply.prompt
        logger.info("Sending reply: %r", reply[:80])
        await _send(chat_id, reply)
    except Exception as e:
        logger.exception("Error handling command %r", text)
        try:
            await _send(chat_id, f"Something went wrong: {e}")
        except Exception:
            logger.exception("Failed to send error reply")


@app.post("/webhook/{token}")
async def webhook(token: str, request: Request):
    if token != TOKEN:
        raise HTTPException(status_code=403)
    data = await request.json()
    asyncio.create_task(_handle(data))
    return {"ok": True}


@app.post("/setup-webhook")
async def setup_webhook(request: Request):
    """Call once after deploying to register the Telegram webhook URL."""
    base = str(request.base_url).rstrip("/").replace("http://", "https://")
    url = f"{base}/webhook/{TOKEN}"
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{TELEGRAM_API}/setWebhook", json={"url": url})
    result = resp.json()
    logger.info("Webhook registered: %s", result)
    return result


@app.post("/test-weekly-summary")
async def test_weekly_summary():
    """Manually trigger the Sunday notification for testing."""
    await _send_weekly_summary()
    return {"ok": True, "sent_to": _owner_chat_id}


@app.post("/test-morning-briefing")
async def test_morning_briefing():
    """Manually trigger the morning briefing for testing."""
    await _send_morning_briefing()
    return {"ok": True, "sent_to": _owner_chat_id}


@app.get("/health")
async def health():
    return {"status": "ok"}
