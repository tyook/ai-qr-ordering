"""JWT authentication middleware for Django Channels WebSocket connections.

Reads the token from the query string (?token=<jwt>) since WebSocket
does not support custom HTTP headers.
"""

from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.tokens import AccessToken


User = get_user_model()


@database_sync_to_async
def get_user_from_token(token_str: str):
    try:
        validated = AccessToken(token_str)
        return User.objects.get(id=validated["user_id"])
    except Exception:
        return AnonymousUser()


class JwtAuthMiddleware(BaseMiddleware):
    """Populate scope["user"] from a JWT access token in the query string."""

    async def __call__(self, scope, receive, send):
        qs = parse_qs(scope.get("query_string", b"").decode())
        token_list = qs.get("token", [])
        if token_list:
            scope["user"] = await get_user_from_token(token_list[0])
        else:
            scope["user"] = AnonymousUser()
        return await super().__call__(scope, receive, send)
