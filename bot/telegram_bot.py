"""
Minimal Telegram bot (no external deps).

Purpose:
- Provide an entry point into the Telegram WebApp with a required ref:
  https://refnet.click/?ref=<telegram_id>
- Works via long-polling (getUpdates).

Env:
- TELEGRAM_BOT_TOKEN (required)
- APP_URL (optional, default: https://refnet.click)
"""

import json
import logging
import os
import time
import urllib.parse
import urllib.request


log = logging.getLogger("soulpull.telegram_bot")


def _api_url(method: str) -> str:
    token = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
    if not token:
        raise RuntimeError("Missing TELEGRAM_BOT_TOKEN env var")
    return f"https://api.telegram.org/bot{token}/{method}"


def _post(method: str, payload: dict) -> dict:
    data = urllib.parse.urlencode(payload).encode("utf-8")
    req = urllib.request.Request(_api_url(method), data=data, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read().decode("utf-8")
    return json.loads(raw)


def _get(method: str, params: dict) -> dict:
    url = _api_url(method) + "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=40) as resp:
        raw = resp.read().decode("utf-8")
    return json.loads(raw)


def send_message(chat_id: int, text: str, reply_markup: dict | None = None) -> None:
    payload = {"chat_id": str(chat_id), "text": text, "parse_mode": "HTML", "disable_web_page_preview": "true"}
    if reply_markup is not None:
        payload["reply_markup"] = json.dumps(reply_markup, separators=(",", ":"))
    _post("sendMessage", payload)


def _make_webapp_keyboard(app_url: str) -> dict:
    return {
        "inline_keyboard": [
            [
                {
                    "text": "Open Soulpull",
                    "web_app": {"url": app_url},
                }
            ]
        ]
    }


def _handle_start(chat_id: int, user_id: int, username: str | None) -> None:
    base = (os.getenv("APP_URL") or "https://refnet.click").rstrip("/")
    webapp_url = f"{base}/?ref={user_id}"

    hi = f"Привет{(' @' + username) if username else ''}!\n\n" \
         f"Открой WebApp (Telegram) и продолжай:\n" \
         f"<code>{webapp_url}</code>\n\n" \
         f"Важно: вход только через Telegram WebApp."

    send_message(chat_id, hi, reply_markup=_make_webapp_keyboard(webapp_url))


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    # Validate token early
    _ = _api_url("getMe")
    try:
        me = _get("getMe", {})
        log.info("Bot started: %s", me.get("result", {}).get("username"))
    except Exception:
        log.exception("Failed to call getMe()")
        raise

    offset = None

    # Skip backlog on first start (optional):
    try:
        r = _get("getUpdates", {"timeout": "0"})
        updates = r.get("result") or []
        if updates:
            offset = int(updates[-1]["update_id"]) + 1
    except Exception:
        log.warning("Could not skip backlog; continuing normally.")

    while True:
        try:
            params = {"timeout": "25", "allowed_updates": json.dumps(["message"], separators=(",", ":"))}
            if offset is not None:
                params["offset"] = str(offset)
            r = _get("getUpdates", params)
            if not r.get("ok"):
                log.warning("getUpdates not ok: %s", r)
                time.sleep(2)
                continue
            for upd in r.get("result") or []:
                offset = int(upd["update_id"]) + 1
                msg = upd.get("message") or {}
                text = (msg.get("text") or "").strip()
                chat = msg.get("chat") or {}
                frm = msg.get("from") or {}

                chat_id = int(chat.get("id"))
                user_id = int(frm.get("id"))
                username = frm.get("username")

                if text.startswith("/start"):
                    _handle_start(chat_id, user_id, username)
                else:
                    send_message(
                        chat_id,
                        "Команда: <b>/start</b>\n\nНажми /start чтобы открыть WebApp.",
                    )
        except Exception:
            log.exception("Polling loop error")
            time.sleep(2)


if __name__ == "__main__":
    main()


