"""Shared slowapi Limiter instance.

Lives in its own module so endpoint code can import the decorator without
importing main.py (which would be circular — main.py imports the routers).
"""
from slowapi import Limiter
from slowapi.util import get_remote_address


limiter = Limiter(key_func=get_remote_address)
