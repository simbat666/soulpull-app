import base64
import hashlib
import hmac
import json
import os
import struct
import time
from urllib.parse import urlencode

from django.test import Client, TestCase
from django.utils import timezone

from nacl.signing import SigningKey


def _sha256(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def _ton_proof_message(*, address: str, domain: str, timestamp: int, payload: str) -> bytes:
    wc_s, hex_s = address.split(":", 1)
    wc = int(wc_s)
    addr_hash = bytes.fromhex(hex_s)
    domain_bytes = domain.encode("utf-8")
    payload_bytes = payload.encode("utf-8")
    address_part = int(wc).to_bytes(4, byteorder="big", signed=True) + addr_hash
    domain_part = struct.pack("<I", len(domain_bytes)) + domain_bytes
    ts_part = struct.pack("<Q", int(timestamp))
    return b"ton-proof-item-v2/" + address_part + domain_part + ts_part + payload_bytes


def _ton_proof_hash(message: bytes) -> bytes:
    return _sha256(b"\xff\xff" + b"ton-connect" + _sha256(message))


class TonProofFlowTests(TestCase):
    def setUp(self) -> None:
        self.client = Client()

    def _login_and_get_token(self) -> str:
        r = self.client.get("/api/v1/tonproof/payload")
        self.assertEqual(r.status_code, 200)
        payload = r.json()["payload"]

        signing_key = SigningKey.generate()
        pubkey = signing_key.verify_key.encode()  # 32 bytes
        pubkey_hex = pubkey.hex()

        addr_hash = os.urandom(32).hex()
        address = f"0:{addr_hash}"
        ts = int(time.time())
        domain = "refnet.click"

        msg = _ton_proof_message(address=address, domain=domain, timestamp=ts, payload=payload)
        to_sign = _ton_proof_hash(msg)
        sig = signing_key.sign(to_sign).signature
        sig_b64 = base64.urlsafe_b64encode(sig).decode("ascii").rstrip("=")

        proof = {
            "timestamp": ts,
            "domain": {"lengthBytes": len(domain.encode("utf-8")), "value": domain},
            "payload": payload,
            "signature": sig_b64,
        }

        r2 = self.client.post(
            "/api/v1/tonproof/verify",
            data=json.dumps({"wallet_address": address, "public_key": pubkey_hex, "proof": proof}),
            content_type="application/json",
        )
        self.assertEqual(r2.status_code, 200, r2.content)
        token = r2.json()["token"]
        self.assertTrue(token)
        return token

    def test_me_requires_bearer(self):
        r = self.client.get("/api/v1/me")
        self.assertEqual(r.status_code, 401)

    def test_tonproof_login_and_me(self):
        token = self._login_and_get_token()
        r = self.client.get("/api/v1/me", **{"HTTP_AUTHORIZATION": f"Bearer {token}"})
        self.assertEqual(r.status_code, 200)
        self.assertIn("wallet_address", r.json())

    def test_telegram_verify(self):
        token = self._login_and_get_token()
        bot_token = "123:TEST_BOT_TOKEN"
        os.environ["TELEGRAM_BOT_TOKEN"] = bot_token

        user_obj = {"id": 777, "username": "testuser", "first_name": "Test"}
        data = {
            "auth_date": str(int(time.time())),
            "query_id": "AAE",
            "user": json.dumps(user_obj),
        }
        data_check = "\n".join([f"{k}={v}" for k, v in sorted(data.items())]).encode("utf-8")
        secret_key = hashlib.sha256(bot_token.encode("utf-8")).digest()
        data["hash"] = hmac.new(secret_key, data_check, hashlib.sha256).hexdigest()
        init_data = urlencode(data)

        r = self.client.post(
            "/api/v1/telegram/verify",
            data=json.dumps({"initData": init_data}),
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {token}"},
        )
        self.assertEqual(r.status_code, 200, r.content)
        r2 = self.client.get("/api/v1/me", **{"HTTP_AUTHORIZATION": f"Bearer {token}"})
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r2.json()["telegram"]["id"], 777)

    def test_payments_create_requires_env(self):
        token = self._login_and_get_token()
        # SSOT: payments require telegram + inviter
        bot_token = "123:TEST_BOT_TOKEN"
        os.environ["TELEGRAM_BOT_TOKEN"] = bot_token

        user_obj = {"id": 777, "username": "testuser", "first_name": "Test"}
        data = {
            "auth_date": str(int(time.time())),
            "query_id": "AAE",
            "user": json.dumps(user_obj),
        }
        data_check = "\n".join([f"{k}={v}" for k, v in sorted(data.items())]).encode("utf-8")
        secret_key = hashlib.sha256(bot_token.encode("utf-8")).digest()
        data["hash"] = hmac.new(secret_key, data_check, hashlib.sha256).hexdigest()
        init_data = urlencode(data)
        r_tg = self.client.post(
            "/api/v1/telegram/verify",
            data=json.dumps({"initData": init_data}),
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {token}"},
        )
        self.assertEqual(r_tg.status_code, 200, r_tg.content)

        r_inv = self.client.post(
            "/api/v1/inviter/apply",
            data=json.dumps({"inviter": "123456"}),
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {token}"},
        )
        self.assertEqual(r_inv.status_code, 200, r_inv.content)

        if "RECEIVER_WALLET" in os.environ:
            del os.environ["RECEIVER_WALLET"]
        r = self.client.post(
            "/api/v1/payments/create",
            data=json.dumps({}),
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {token}"},
        )
        self.assertEqual(r.status_code, 400)

        os.environ["RECEIVER_WALLET"] = "UQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        r2 = self.client.post(
            "/api/v1/payments/create",
            data=json.dumps({}),
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": f"Bearer {token}"},
        )
        self.assertEqual(r2.status_code, 200, r2.content)
        j = r2.json()
        self.assertIn("receiver", j)
        self.assertIn("amount", j)


