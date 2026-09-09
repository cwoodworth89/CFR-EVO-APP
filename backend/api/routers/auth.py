"""
Authentication and Authorization Endpoints for CFR EVO API Gateway.
Provides JWT session validation, role assignment, and local/Tailscale IP filtering.
"""
import os
import ipaddress
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import APIRouter, HTTPException, Request, Depends

try:
    from backend.api.schemas import LoginRequest
except ModuleNotFoundError:
    from api.schemas import LoginRequest

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Tailscale Carrier-Grade NAT subnet (100.64.0.0/10)
TAILSCALE_SUBNET = ipaddress.ip_network("100.64.0.0/10")

# JWT configuration
JWT_ALGORITHM = "HS256"
# The unlock lasts this long unless LOCK is pressed (operator, 2026-09-08: "carry a 30 days
# unlock state unless specifically locked"; an auto-lock is a production feature, not built).
TOKEN_LIFETIME = timedelta(days=30)


def _jwt_secret() -> str:
    """The token signing key, from the environment and nowhere else.

    This was a literal in this file with an env override, so every clone of the repository
    could mint admin tokens for every deployment, and the kiosk ran on the literal. Read per
    call, not at import, so a test or a restart with a new value takes effect. Unset is a
    configuration error and login says so (CLAUDE.md 6.1; the same rule as ADMIN_PASSWORD,
    punch-list #65): compose passes ${JWT_SECRET} from the root .env.
    """
    return os.environ.get("JWT_SECRET", "").strip()


def get_client_ip(request: Request) -> str:
    """Extracts client IP address from proxy headers or direct connection."""
    x_forwarded_for = request.headers.get("x-forwarded-for")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else "127.0.0.1"


def is_allowed_network(client_ip_str: str) -> bool:
    """Validates if IP is loopback, RFC1918 private, or Tailscale CGNAT subnet."""
    if not client_ip_str:
        return False
    if client_ip_str in ["127.0.0.1", "::1", "localhost", "testclient"]:
        return True
    try:
        ip = ipaddress.ip_address(client_ip_str)
        if ip.is_loopback or ip.is_private or ip in TAILSCALE_SUBNET:
            return True
    except ValueError:
        pass
    return False


@router.post("/login")
def login(req: LoginRequest, request: Request):
    """Authenticates station kiosk admins, restricted to local and Tailscale networks."""
    client_ip = get_client_ip(request)
    if not is_allowed_network(client_ip):
        logging.warning(f"Admin login attempt blocked from unauthorized IP '{client_ip}'")
        raise HTTPException(
            status_code=403,
            detail=f"Admin access restricted to localhost or Tailscale network. Your IP ({client_ip}) is not authorized."
        )

    user_id = (req.username or req.email or "cfradmin").strip()
    user_pass = (req.password or "").strip()

    # One password, from the environment, and no other (punch-list #65, operator ruling
    # 2026-09-05). This used to accept the configured value OR three literals, so setting
    # ADMIN_PASSWORD added a password and never removed the defaults; the 401 text named one.
    # Unset is a configuration error, reported as such, never a default (CLAUDE.md 6.1, #61).
    expected_pass = os.environ.get("ADMIN_PASSWORD", "").strip()
    if not expected_pass:
        logging.error("ADMIN_PASSWORD is not set; admin login is disabled until it is (root .env, read by compose).")
        raise HTTPException(status_code=503, detail="Admin login is not configured on this server.")
    secret = _jwt_secret()
    if not secret:
        logging.error("JWT_SECRET is not set; admin login is disabled until it is (root .env, read by compose).")
        raise HTTPException(status_code=503, detail="Admin login is not configured on this server.")

    if user_pass and user_pass == expected_pass:
        token_payload = {
            "sub": user_id,
            "exp": datetime.now(timezone.utc) + TOKEN_LIFETIME
        }
        token = jwt.encode(token_payload, secret, algorithm=JWT_ALGORITHM)
        return {
            "access_token": token,
            "token_type": "bearer",
            "user": {"username": user_id, "role": "admin"}
        }
    raise HTTPException(status_code=401, detail="Invalid username or password.")


@router.get("/session")
def get_session(request: Request, authorization: Optional[str] = None):
    """Validates active JWT token and returns current user session."""
    client_ip = get_client_ip(request)
    if not is_allowed_network(client_ip):
        return {"session": None}

    auth_header = authorization or request.headers.get("authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return {"session": None}
    token = auth_header.split(" ")[1]
    secret = _jwt_secret()
    if not secret:
        return {"session": None}
    try:
        payload = jwt.decode(token, secret, algorithms=[JWT_ALGORITHM])
        return {"session": {"user": {"username": payload.get("sub"), "role": "admin"}}}
    except Exception:
        return {"session": None}


def require_admin(request: Request) -> dict:
    """FastAPI dependency: the user behind a valid admin token, or 401.

    Gates the operator rulings a shared screen must not offer to crews, the arrival point
    and the Street View saves (operator, 2026-09-08: "only admin unlocked"). Reads stay
    open. The unlock is the padlock in the workstation header; the token it stores is the
    one login issues, 30 days unless LOCK is pressed. Direct Python callers (the tests, the
    override alias) pass the user themselves; only HTTP traffic goes through here.
    """
    session = get_session(request, None).get("session")
    if not session:
        raise HTTPException(status_code=401, detail="Admin unlock required for this change.")
    return session["user"]


@router.get("/me")
def get_me(request: Request, authorization: Optional[str] = None):
    """Alias for /session returning current user metadata."""
    return get_session(request, authorization)


@router.post("/logout")
def logout():
    """Stateless logout endpoint for client session cleanup."""
    return {"status": "success", "message": "Logged out successfully"}
