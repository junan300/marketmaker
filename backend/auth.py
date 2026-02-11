"""
API Authentication & Rate Limiting Middleware

Security layer:
- API key authentication for all endpoints
- Rate limiting per client
- CORS policies
- Localhost bypass for development
- WebSocket path exemption
"""

import os
import time
import hashlib
import secrets
import logging
from collections import defaultdict
from fastapi import Request, HTTPException, Security
from fastapi.security import APIKeyHeader
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("auth")

# ── API Key Management ──────────────────────────────────────────────

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)

# Store hashed keys (never store raw API keys)
_valid_key_hashes: set = set()


def generate_api_key() -> str:
    """Generate a new API key. Display it once, then store only the hash."""
    key = f"smm_{secrets.token_urlsafe(32)}"
    key_hash = hashlib.sha256(key.encode()).hexdigest()
    _valid_key_hashes.add(key_hash)
    logger.info(f"New API key generated (hash: {key_hash[:12]}...)")
    return key


def load_api_key_from_env():
    """Load API key from environment variable."""
    key = os.getenv("MM_API_KEY")
    if key:
        key_hash = hashlib.sha256(key.encode()).hexdigest()
        _valid_key_hashes.add(key_hash)
        logger.info("API key loaded from environment")
    else:
        logger.warning("No MM_API_KEY set — generating a temporary key")
        temp_key = generate_api_key()
        print(f"\n{'='*60}")
        print(f"  TEMPORARY API KEY (set MM_API_KEY env var to persist):")
        print(f"  {temp_key}")
        print(f"{'='*60}\n")


def validate_api_key(key: str) -> bool:
    """Validate an API key by comparing hashes."""
    if not key:
        return False
    key_hash = hashlib.sha256(key.encode()).hexdigest()
    return key_hash in _valid_key_hashes


async def require_api_key(api_key: str = Security(API_KEY_HEADER)):
    """FastAPI dependency — use on protected endpoints."""
    if not validate_api_key(api_key):
        logger.warning("Invalid API key attempt")
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return api_key


# ── Rate Limiting ───────────────────────────────────────────────────

class RateLimiter:
    """
    Simple sliding-window rate limiter.
    Tracks requests per client IP within a time window.
    """

    def __init__(self, max_requests: int = 60, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict = defaultdict(list)

    def is_allowed(self, client_ip: str) -> bool:
        now = time.time()
        cutoff = now - self.window_seconds

        self._requests[client_ip] = [
            t for t in self._requests[client_ip] if t > cutoff
        ]

        if len(self._requests[client_ip]) >= self.max_requests:
            return False

        self._requests[client_ip].append(now)
        return True

    def get_remaining(self, client_ip: str) -> int:
        now = time.time()
        cutoff = now - self.window_seconds
        current = len([t for t in self._requests.get(client_ip, []) if t > cutoff])
        return max(0, self.max_requests - current)


# Global rate limiter instance
rate_limiter = RateLimiter(max_requests=120, window_seconds=60)


# ── Middleware ──────────────────────────────────────────────────────

class AuthMiddleware(BaseHTTPMiddleware):
    """
    Combined authentication + rate limiting middleware.

    Exempt paths (no auth required):
    - /health — for load balancer health checks
    - /docs, /openapi.json — Swagger UI (disable in production)
    - /ws/* — WebSocket connections (handled separately)
    """

    EXEMPT_PATHS = {"/health", "/docs", "/openapi.json", "/redoc", "/"}
    EXEMPT_PREFIXES = ("/ws/",)  # WebSocket paths bypass HTTP auth

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Skip auth for exempt paths
        if path in self.EXEMPT_PATHS:
            return await call_next(request)

        # Skip auth for WebSocket and other exempt prefixes
        if any(path.startswith(p) for p in self.EXEMPT_PREFIXES):
            return await call_next(request)

        # Rate limiting
        client_ip = request.client.host if request.client else "unknown"
        if not rate_limiter.is_allowed(client_ip):
            logger.warning(f"Rate limit exceeded for {client_ip}")
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded. Try again later.",
            )

        # API key check — allow localhost without key in development
        api_key = request.headers.get("X-API-Key")
        allow_localhost = os.getenv("MM_ALLOW_LOCALHOST", "true").lower() == "true"
        if allow_localhost and client_ip in ("127.0.0.1", "localhost", "::1"):
            response = await call_next(request)
            response.headers["X-RateLimit-Remaining"] = str(
                rate_limiter.get_remaining(client_ip)
            )
            return response

        # Require API key for non-localhost
        if not validate_api_key(api_key):
            raise HTTPException(status_code=401, detail="Invalid or missing API key")

        response = await call_next(request)
        response.headers["X-RateLimit-Remaining"] = str(
            rate_limiter.get_remaining(client_ip)
        )
        return response


# ── Binding Safety ──────────────────────────────────────────────────

def get_bind_host() -> str:
    """
    Determine safe bind host.
    Default to localhost-only. Set MM_BIND_HOST=0.0.0.0 to expose.
    """
    host = os.getenv("MM_BIND_HOST", "127.0.0.1")
    if host == "0.0.0.0":
        logger.warning(
            "Server binding to 0.0.0.0 — accessible from network. "
            "Ensure API key auth is configured and firewall rules are in place."
        )
    return host
