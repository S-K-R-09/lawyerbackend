from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import get_settings

_s = get_settings()
limiter = Limiter(key_func=get_remote_address, enabled=_s.RATE_LIMIT_ENABLED)


def auth_limit() -> str:
    return get_settings().AUTH_RATE_LIMIT
