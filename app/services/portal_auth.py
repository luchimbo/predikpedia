"""Verify the short-lived credential issued by the authenticated portal."""
import base64
import hashlib
import hmac
import json
import time
from uuid import UUID


def verify_handoff(token: str, secret: str, now: int | None = None) -> str | None:
    if len(secret) < 32 or len(token) > 1024:
        return None
    try:
        payload, signature = token.split(".")
        expected = hmac.new(secret.encode(), payload.encode("ascii"), hashlib.sha256).digest()
        encoded = base64.urlsafe_b64encode(expected).decode("ascii").rstrip("=")
        if not hmac.compare_digest(signature, encoded):
            return None
        claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        now = int(time.time()) if now is None else now
        issued, expiry = claims["iat"], claims["exp"]
        if (claims["aud"] != "predikpedia-streamlit" or type(issued) is not int
                or type(expiry) is not int or expiry - issued != 60
                or issued > now + 5 or now >= expiry):
            return None
        return str(UUID(claims["sub"]))
    except (ValueError, TypeError, KeyError, AttributeError):
        return None
