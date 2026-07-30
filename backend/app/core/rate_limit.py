"""
Rate limiter setup (slowapi).

WHY per-IP rate limiting on the resume upload endpoint specifically:
This is the one endpoint an unauthenticated member of the public can hit.
Without rate limiting, it's an open door to (a) running up your Claude
API bill via scripted abuse, and (b) filling Supabase Storage with junk.
Keyed by IP by default; if you put this behind Cloudflare/a proxy, make
sure X-Forwarded-For is trusted correctly or every request will appear
to come from the proxy's IP and rate-limit everyone as one client.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
