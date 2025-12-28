import hashlib
import hmac
import json
from dataclasses import dataclass
from typing import Optional
from urllib.parse import parse_qsl


@dataclass(frozen=True)
class TelegramUser:
    telegram_id: int
    username: Optional[str]
    first_name: Optional[str]


def verify_init_data(init_data: str, bot_token: str) -> TelegramUser:
    """
    Verify Telegram WebApp initData signature.
    https://core.telegram.org/bots/webapps#validating-data-received-via-the-web-app
    """
    if not bot_token:
        raise ValueError("missing bot token")

    pairs = parse_qsl(init_data or "", keep_blank_values=True)
    data = dict(pairs)
    received_hash = (data.pop("hash", "") or "").strip()
    if not received_hash:
        raise ValueError("missing hash")

    # Build data-check-string
    items = [f"{k}={v}" for k, v in sorted(data.items())]
    data_check_string = "\n".join(items).encode("utf-8")

    secret_key = hashlib.sha256(bot_token.encode("utf-8")).digest()
    calculated_hash = hmac.new(secret_key, data_check_string, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(calculated_hash, received_hash):
        raise ValueError("bad signature")

    user_json = data.get("user") or ""
    if not user_json:
        raise ValueError("missing user")
    try:
        user = json.loads(user_json)
    except Exception:
        raise ValueError("invalid user json")

    telegram_id = int(user.get("id"))
    username = user.get("username")
    first_name = user.get("first_name")
    return TelegramUser(
        telegram_id=telegram_id,
        username=str(username) if username is not None else None,
        first_name=str(first_name) if first_name is not None else None,
    )


