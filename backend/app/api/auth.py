"""
Auth + Stripe subscription routes.

POST /auth/register   — create account
POST /auth/login      — get JWT
GET  /auth/me         — current user info
POST /stripe/checkout — create Stripe Checkout Session
POST /stripe/webhook  — Stripe webhook (signature-verified)
GET  /stripe/status   — subscription status for current user
"""
from __future__ import annotations

import hashlib
import hmac
import os
import time
from typing import Annotated

import stripe
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel, EmailStr

# ── Stripe client ────────────────────────────────────────────────────────────
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
STRIPE_PRICE_ID = os.environ.get("STRIPE_PRICE_ID", "")
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://54.203.13.36")

# ── JWT config ────────────────────────────────────────────────────────────────
JWT_SECRET = os.environ.get("JWT_SECRET", "change-me-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = 24 * 30  # 30 days

# ── Auth bypass flag (dev convenience) ───────────────────────────────────────
# Set AUTH_REQUIRED=false in .env to disable login gating entirely
def auth_required() -> bool:
    return os.environ.get("AUTH_REQUIRED", "true").lower() not in ("false", "0", "no")


router = APIRouter()
_bearer = HTTPBearer(auto_error=False)


# ── DB helpers ───────────────────────────────────────────────────────────────

def _get_conn():
    """Return a psycopg connection from the shared pool."""
    from app.db.session import get_engine
    engine = get_engine()
    return engine.raw_connection()


def _hash_password(password: str) -> str:
    import bcrypt
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _check_password(password: str, hashed: str) -> bool:
    import bcrypt
    return bcrypt.checkpw(password.encode(), hashed.encode())


def _make_token(user_id: int, email: str) -> str:
    payload = {
        "sub": str(user_id),
        "email": email,
        "iat": int(time.time()),
        "exp": int(time.time()) + JWT_EXPIRE_HOURS * 3600,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def _decode_token(token: str) -> dict:
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])


# ── Dependency: current user ──────────────────────────────────────────────────

class CurrentUser(BaseModel):
    user_id: int
    email: str
    is_subscribed: bool


def get_current_user(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> CurrentUser | None:
    """Returns current user or None if not authenticated."""
    if not auth_required():
        # Dev bypass: return a fake superuser
        return CurrentUser(user_id=0, email="dev@local", is_subscribed=True)
    if not creds:
        return None
    try:
        payload = _decode_token(creds.credentials)
    except JWTError:
        return None
    user_id = int(payload["sub"])
    email = payload["email"]

    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT is_subscribed FROM users WHERE id = %s", (user_id,)
            )
            row = cur.fetchone()
    finally:
        conn.close()

    if not row:
        return None
    return CurrentUser(user_id=user_id, email=email, is_subscribed=bool(row[0]))


def require_user(user: Annotated[CurrentUser | None, Depends(get_current_user)]) -> CurrentUser:
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user


def require_subscribed(user: Annotated[CurrentUser, Depends(require_user)]) -> CurrentUser:
    if not user.is_subscribed:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Active subscription required",
        )
    return user


# ── Request/response schemas ──────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    token: str
    email: str
    is_subscribed: bool


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/auth/register", response_model=TokenResponse)
def register(body: RegisterRequest):
    if len(body.password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")
    pw_hash = _hash_password(body.password)
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO users (email, password_hash) VALUES (%s, %s) RETURNING id",
                (body.email.lower().strip(), pw_hash),
            )
            row = cur.fetchone()
        conn.commit()
    except Exception as exc:
        conn.rollback()
        if "unique" in str(exc).lower():
            raise HTTPException(409, "Email already registered")
        raise HTTPException(500, "Registration failed") from exc
    finally:
        conn.close()
    user_id = row[0]
    token = _make_token(user_id, body.email.lower().strip())
    return TokenResponse(token=token, email=body.email.lower().strip(), is_subscribed=False)


@router.post("/auth/login", response_model=TokenResponse)
def login(body: LoginRequest):
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, password_hash, is_subscribed FROM users WHERE email = %s",
                (body.email.lower().strip(),),
            )
            row = cur.fetchone()
    finally:
        conn.close()
    if not row or not _check_password(body.password, row[1]):
        raise HTTPException(401, "Invalid email or password")
    token = _make_token(row[0], body.email.lower().strip())
    return TokenResponse(token=token, email=body.email.lower().strip(), is_subscribed=bool(row[2]))


@router.get("/auth/me")
def me(user: Annotated[CurrentUser, Depends(require_user)]):
    return {"user_id": user.user_id, "email": user.email, "is_subscribed": user.is_subscribed}


# ── Stripe ────────────────────────────────────────────────────────────────────

@router.post("/stripe/checkout")
def create_checkout(user: Annotated[CurrentUser, Depends(require_user)]):
    """Create a Stripe Checkout Session for the Pro subscription."""
    if not STRIPE_PRICE_ID:
        raise HTTPException(500, "Stripe not configured")

    # Get or create Stripe customer
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT stripe_customer_id FROM users WHERE id = %s", (user.user_id,))
            row = cur.fetchone()
        customer_id = row[0] if row else None
    finally:
        conn.close()

    if not customer_id:
        customer = stripe.Customer.create(email=user.email, metadata={"user_id": user.user_id})
        customer_id = customer.id
        conn = _get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE users SET stripe_customer_id = %s WHERE id = %s",
                    (customer_id, user.user_id),
                )
            conn.commit()
        finally:
            conn.close()

    session = stripe.checkout.Session.create(
        customer=customer_id,
        payment_method_types=["card"],
        line_items=[{"price": STRIPE_PRICE_ID, "quantity": 1}],
        mode="subscription",
        success_url=f"{FRONTEND_URL}?payment=success",
        cancel_url=f"{FRONTEND_URL}?payment=cancelled",
        metadata={"user_id": str(user.user_id)},
    )
    return {"url": session.url}


@router.post("/stripe/webhook")
async def stripe_webhook(request: Request):
    """Verify Stripe signature and update subscription status."""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    except stripe.error.SignatureVerificationError:
        raise HTTPException(400, "Invalid signature")
    except Exception as exc:
        raise HTTPException(400, str(exc))

    evt_type = event["type"]
    data = event["data"]["object"]

    if evt_type == "checkout.session.completed":
        customer_id = data.get("customer")
        _set_subscription(customer_id, True, data.get("subscription"))

    elif evt_type in ("customer.subscription.created", "customer.subscription.updated"):
        customer_id = data.get("customer")
        active = data.get("status") in ("active", "trialing")
        _set_subscription(customer_id, active, data.get("id"))

    elif evt_type == "customer.subscription.deleted":
        customer_id = data.get("customer")
        _set_subscription(customer_id, False, data.get("id"))

    return {"received": True}


def _set_subscription(customer_id: str | None, active: bool, sub_id: str | None = None):
    if not customer_id:
        return
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE users
                   SET is_subscribed = %s,
                       stripe_sub_id = COALESCE(%s, stripe_sub_id),
                       updated_at = NOW()
                   WHERE stripe_customer_id = %s""",
                (active, sub_id, customer_id),
            )
        conn.commit()
    finally:
        conn.close()


@router.get("/stripe/status")
def subscription_status(user: Annotated[CurrentUser, Depends(require_user)]):
    return {"is_subscribed": user.is_subscribed, "email": user.email}
