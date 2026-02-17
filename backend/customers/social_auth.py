import jwt
import requests as http_requests
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from django.conf import settings

APPLE_PUBLIC_KEYS_URL = "https://appleid.apple.com/auth/keys"
_apple_keys_cache = None


def verify_google_token(token: str) -> dict:
    """
    Verify a Google ID token and return user info.

    Returns dict with keys: sub, email, name, picture
    Raises ValueError if token is invalid.
    """
    idinfo = id_token.verify_oauth2_token(
        token,
        google_requests.Request(),
        settings.GOOGLE_CLIENT_ID,
    )
    # Verify issuer
    if idinfo["iss"] not in ("accounts.google.com", "https://accounts.google.com"):
        raise ValueError("Invalid issuer.")
    return {
        "sub": idinfo["sub"],           # Google user ID
        "email": idinfo.get("email"),
        "name": idinfo.get("name", ""),
        "picture": idinfo.get("picture", ""),
    }


def _get_apple_public_keys():
    """Fetch and cache Apple's public keys."""
    global _apple_keys_cache
    if _apple_keys_cache is None:
        resp = http_requests.get(APPLE_PUBLIC_KEYS_URL, timeout=10)
        resp.raise_for_status()
        _apple_keys_cache = resp.json()["keys"]
    return _apple_keys_cache


def verify_apple_token(token: str) -> dict:
    """
    Verify an Apple identity token and return user info.

    Returns dict with keys: sub, email, name
    Raises ValueError if token is invalid.
    """
    # Decode header to find the right key
    header = jwt.get_unverified_header(token)
    kid = header.get("kid")
    if not kid:
        raise ValueError("Token missing kid header.")

    # Find matching public key
    apple_keys = _get_apple_public_keys()
    matching_key = None
    for key in apple_keys:
        if key["kid"] == kid:
            matching_key = key
            break
    if not matching_key:
        raise ValueError("No matching Apple public key found.")

    # Build public key and verify
    public_key = jwt.algorithms.RSAAlgorithm.from_jwk(matching_key)
    decoded = jwt.decode(
        token,
        key=public_key,
        algorithms=["RS256"],
        audience=settings.APPLE_CLIENT_ID,
        issuer="https://appleid.apple.com",
    )

    return {
        "sub": decoded["sub"],
        "email": decoded.get("email"),
        "name": "",  # Apple only sends name on first auth; frontend must pass it
    }
