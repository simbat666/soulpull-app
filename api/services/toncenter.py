import json
import os
import urllib.parse
import urllib.request


class ToncenterError(RuntimeError):
    pass


def _base_url() -> str:
    return (os.getenv("TONCENTER_BASE_URL") or "https://toncenter.com/api/v3").rstrip("/")


def _api_key() -> str:
    return (os.getenv("TONCENTER_API_KEY") or "").strip()


def _http_get_json(url: str) -> dict:
    req = urllib.request.Request(url, method="GET")
    key = _api_key()
    if key:
        # Toncenter supports X-API-Key on some deployments; keep query api_key as fallback.
        req.add_header("X-API-Key", key)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        raise ToncenterError(f"toncenter request failed: {e.__class__.__name__}") from e
    try:
        data = json.loads(raw)
    except Exception as e:
        raise ToncenterError("toncenter returned non-json") from e
    return data if isinstance(data, dict) else {"data": data}


def get_jetton_wallet_address(*, owner_address: str, jetton_master_address: str) -> str:
    """
    Returns address of owner's jetton-wallet for a given jetton master.
    Uses Toncenter v3 endpoints.
    """
    owner = (owner_address or "").strip()
    master = (jetton_master_address or "").strip()
    if not owner:
        raise ToncenterError("missing owner_address")
    if not master:
        raise ToncenterError("missing jetton_master_address")

    # Prefer v3 endpoint if available.
    # Common schema: GET /jetton/wallets?owner_address=...&jetton_master_address=...
    q = {
        "owner_address": owner,
        "jetton_master_address": master,
        "limit": "1",
        "offset": "0",
    }
    # Fallback API key via query param (works on many toncenter setups).
    if _api_key():
        q["api_key"] = _api_key()

    url = f"{_base_url()}/jetton/wallets?{urllib.parse.urlencode(q)}"
    data = _http_get_json(url)

    # Try a few plausible response shapes
    items = None
    for k in ("jetton_wallets", "wallets", "items", "result", "data"):
        v = data.get(k)
        if isinstance(v, list):
            items = v
            break
    if items is None and isinstance(data.get("data"), list):
        items = data["data"]

    if not items:
        raise ToncenterError("jetton wallet not found")

    item0 = items[0] if isinstance(items[0], dict) else None
    if not item0:
        raise ToncenterError("jetton wallet not found")

    addr = item0.get("address") or item0.get("jetton_wallet_address") or item0.get("wallet_address")
    if not addr:
        raise ToncenterError("unexpected toncenter response (missing address)")
    return str(addr)


