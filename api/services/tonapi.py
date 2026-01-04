"""
Soulpull MVP — TonAPI Service

Сервис для проверки платежей через TonAPI.
Используется для верификации что платёж реально пришёл в блокчейн.

TonAPI Events API:
- GET /v2/accounts/{account_id}/events — история событий аккаунта
- Ищем TonTransfer с нужным sender, receiver, amount
"""

import os
import logging
import requests
from typing import Optional

logger = logging.getLogger(__name__)

# Конфигурация из .env
TONAPI_BASE_URL = os.getenv("TONAPI_BASE_URL", "https://tonapi.io").rstrip("/")
TONAPI_KEY = os.getenv("TONAPI_KEY", "")


class TonApiError(RuntimeError):
    """Ошибка при работе с TonAPI"""
    pass


def _headers() -> dict:
    """Заголовки для запросов к TonAPI"""
    h = {"Accept": "application/json"}
    if TONAPI_KEY:
        h["Authorization"] = f"Bearer {TONAPI_KEY}"
    return h


def get_account_events(account_id: str, limit: int = 25) -> dict:
    """
    Получить последние события аккаунта.
    
    Args:
        account_id: TON адрес (user-friendly или raw)
        limit: количество событий
        
    Returns:
        dict с ключом "events" — список событий
    """
    url = f"{TONAPI_BASE_URL}/v2/accounts/{account_id}/events"
    
    try:
        logger.info(f"[TonAPI] GET {url} limit={limit}")
        r = requests.get(url, headers=_headers(), params={"limit": limit}, timeout=20)
        
        if r.status_code != 200:
            logger.error(f"[TonAPI] Error {r.status_code}: {r.text[:500]}")
            raise TonApiError(f"TonAPI error {r.status_code}: {r.text[:300]}")
        
        data = r.json()
        logger.info(f"[TonAPI] Got {len(data.get('events', []))} events")
        return data
        
    except requests.RequestException as e:
        logger.error(f"[TonAPI] Request failed: {e}")
        raise TonApiError(f"TonAPI request failed: {e}")


def normalize_address(addr: str) -> str:
    """
    Нормализация адреса для сравнения.
    TonAPI может возвращать адреса в разных форматах.
    """
    if not addr:
        return ""
    # Убираем пробелы и приводим к lowercase для raw адресов
    addr = addr.strip()
    # Если это raw адрес (0:...), нормализуем
    if addr.startswith("0:") or addr.startswith("-1:"):
        return addr.lower()
    return addr


def find_ton_transfer_event(
    events_json: dict,
    *,
    receiver: str,
    sender: str,
    amount_nano: int,
    comment_contains: Optional[str] = None,
    min_timestamp: Optional[int] = None,
) -> Optional[dict]:
    """
    Найти событие TonTransfer с нужными параметрами.
    
    Args:
        events_json: ответ от get_account_events
        receiver: адрес получателя (наш кошелёк)
        sender: адрес отправителя (кошелёк пользователя)
        amount_nano: сумма в нанотонах
        comment_contains: подстрока в комментарии (опционально)
        min_timestamp: минимальный timestamp транзакции (опционально)
        
    Returns:
        dict с event_id, tx_hash, comment если найдено, иначе None
    """
    events = events_json.get("events") or []
    
    # Нормализуем адреса для сравнения
    receiver_norm = normalize_address(receiver)
    sender_norm = normalize_address(sender)
    
    logger.info(f"[TonAPI] Searching for transfer: {sender_norm} -> {receiver_norm}, amount={amount_nano}")
    
    for ev in events:
        event_id = ev.get("event_id") or ev.get("id") or ""
        timestamp = ev.get("timestamp") or 0
        
        # Проверка timestamp
        if min_timestamp and timestamp < min_timestamp:
            continue
        
        actions = ev.get("actions") or []
        
        for action in actions:
            action_type = (action.get("type") or "").lower()
            
            # Ищем TonTransfer
            if "tontransfer" not in action_type:
                continue
            
            # Данные могут быть в разных полях
            data = (
                action.get("TonTransfer") or 
                action.get("ton_transfer") or 
                action.get("data") or 
                {}
            )
            
            # Извлекаем sender
            s = data.get("sender") or data.get("from") or ""
            if isinstance(s, dict):
                s = s.get("address") or s.get("account_address") or ""
            s = normalize_address(s)
            
            # Извлекаем recipient
            r = data.get("recipient") or data.get("to") or ""
            if isinstance(r, dict):
                r = r.get("address") or r.get("account_address") or ""
            r = normalize_address(r)
            
            # Извлекаем amount
            amt = data.get("amount") or data.get("value") or 0
            try:
                amt_int = int(amt)
            except (ValueError, TypeError):
                continue
            
            # Извлекаем комментарий
            comment = data.get("comment") or ""
            
            # Извлекаем tx_hash из in_msg или lt
            tx_hash = ""
            if ev.get("in_msg"):
                tx_hash = ev["in_msg"].get("hash") or ev["in_msg"].get("msg_hash") or ""
            if not tx_hash:
                tx_hash = str(ev.get("lt") or event_id)
            
            logger.debug(f"[TonAPI] Checking: {s} -> {r}, amount={amt_int}, comment={comment}")
            
            # Проверяем совпадение
            # Сравниваем адреса (могут быть в разных форматах)
            sender_match = (s == sender_norm) or (sender in s) or (s in sender)
            receiver_match = (r == receiver_norm) or (receiver in r) or (r in receiver)
            
            if not sender_match:
                continue
            if not receiver_match:
                continue
            
            # Проверяем сумму с погрешностью 1% (на комиссии)
            amount_diff = abs(amt_int - int(amount_nano))
            amount_tolerance = int(amount_nano) * 0.01  # 1%
            if amount_diff > amount_tolerance:
                continue
            
            # Проверяем комментарий если нужно
            if comment_contains and comment_contains not in str(comment):
                continue
            
            logger.info(f"[TonAPI] ✅ Found matching transfer! event_id={event_id}, tx_hash={tx_hash}")
            
            return {
                "event_id": event_id,
                "tx_hash": tx_hash,
                "comment": comment,
                "amount": amt_int,
                "timestamp": timestamp,
            }
    
    logger.info("[TonAPI] No matching transfer found")
    return None


def verify_payment(
    receiver_address: str,
    sender_address: str,
    amount_nano: int,
    order_id: Optional[str] = None,
) -> Optional[dict]:
    """
    Высокоуровневая функция проверки платежа.
    
    Args:
        receiver_address: адрес получателя (наш кошелёк)
        sender_address: адрес отправителя (кошелёк пользователя)
        amount_nano: ожидаемая сумма в нанотонах
        order_id: ID заказа для поиска в комментарии
        
    Returns:
        dict с данными о транзакции если найдена, иначе None
    """
    try:
        events = get_account_events(receiver_address, limit=30)
        
        comment_contains = f"SP:{order_id}" if order_id else None
        
        return find_ton_transfer_event(
            events,
            receiver=receiver_address,
            sender=sender_address,
            amount_nano=amount_nano,
            comment_contains=comment_contains,
        )
        
    except TonApiError as e:
        logger.error(f"[TonAPI] verify_payment failed: {e}")
        return None

