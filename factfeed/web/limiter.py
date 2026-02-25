"""Shared slowapi rate-limiter singleton.

Defined in its own module to avoid circular imports between
factfeed.web.main (which sets app.state.limiter) and the route
modules that apply @limiter.limit decorators.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
