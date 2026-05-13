import asyncio
import logging
import os

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request

import commands

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_API = f"https://api.telegram.org/bot{TOKEN}"

app = FastAPI()

_pending: dict[int, commands.PendingEvent] = {}


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
    if cmd == "/week":
        return commands.handle_week()
    if cmd == "/today":
        return commands.handle_today()
    if cmd in ("/help", "/start"):
        return commands.HELP_TEXT
    if cmd == "/suggestions":
        return commands.handle_suggestions(args)
    return "Unknown command — send /help for the command list."


async def _handle(data: dict) -> None:
    message = data.get("message") or data.get("edited_message")
    if not message:
        return

    chat_id: int = message["chat"]["id"]
    text: str = message.get("text", "").strip()

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


@app.get("/health")
async def health():
    return {"status": "ok"}
