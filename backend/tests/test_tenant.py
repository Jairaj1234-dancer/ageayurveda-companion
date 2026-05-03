"""Tenant model + auth resolution + source allowlist tests.

Exercises the multi-tenant authentication path without actually hitting
Anthropic — the API client is never invoked during these tests.
"""
import uuid

import pytest
from fastapi import HTTPException

from app.api.v1.chat import _resolve_sources, _resolve_tenant
from app.models import Tenant
from app.models.tenant import generate_api_key


def _make_request(headers: dict | None = None):
    """Minimal Request stand-in for _resolve_tenant — only headers are read."""
    from starlette.requests import Request

    scope = {
        "type": "http",
        "method": "POST",
        "headers": [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()],
        "client": ("127.0.0.1", 9999),
    }
    return Request(scope)


def test_generate_api_key_format():
    key = generate_api_key()
    assert key.startswith("ageak_")
    assert len(key) > 20


def test_generate_api_key_unique():
    keys = {generate_api_key() for _ in range(20)}
    assert len(keys) == 20


# ---- _resolve_sources ---------------------------------------------------


def test_resolve_sources_no_tenant_no_body_returns_none():
    assert _resolve_sources(None, None) is None


def test_resolve_sources_body_only_passes_through():
    assert _resolve_sources(None, ["Charaka Samhita"]) == ["Charaka Samhita"]


def test_resolve_sources_tenant_only_uses_tenant_allowlist():
    t = Tenant(name="x", allowed_sources=["Charaka Samhita"])
    assert _resolve_sources(t, None) == ["Charaka Samhita"]


def test_resolve_sources_intersects_when_both_present():
    t = Tenant(name="x", allowed_sources=["Charaka Samhita", "Ashtanga Hridaya"])
    body = ["Charaka Samhita", "Sushruta Samhita"]
    # Sushruta is requested but not in tenant allowlist — must be excluded.
    assert _resolve_sources(t, body) == ["Charaka Samhita"]


def test_resolve_sources_tenant_no_allowlist_passes_body_through():
    t = Tenant(name="x", allowed_sources=None)
    assert _resolve_sources(t, ["Charaka Samhita"]) == ["Charaka Samhita"]


# ---- _resolve_tenant ----------------------------------------------------


async def test_resolve_tenant_no_auth_header_returns_none(db_session):
    request = _make_request()
    assert await _resolve_tenant(request, db_session) is None


async def test_resolve_tenant_non_tenant_bearer_returns_none(db_session):
    """Bearer tokens that don't start with `ageak_` are left alone — they
    might be admin JWTs or some other auth scheme."""
    request = _make_request({"Authorization": "Bearer some.jwt.token"})
    assert await _resolve_tenant(request, db_session) is None


async def test_resolve_tenant_unknown_key_raises_401(db_session):
    request = _make_request({"Authorization": "Bearer ageak_does_not_exist"})
    with pytest.raises(HTTPException) as exc:
        await _resolve_tenant(request, db_session)
    assert exc.value.status_code == 401


async def test_resolve_tenant_inactive_raises_401(db_session):
    t = Tenant(name="acme", anthropic_api_key="sk-ant-x", active=False)
    db_session.add(t)
    await db_session.commit()

    request = _make_request({"Authorization": f"Bearer {t.api_key}"})
    with pytest.raises(HTTPException) as exc:
        await _resolve_tenant(request, db_session)
    assert exc.value.status_code == 401


async def test_resolve_tenant_no_anthropic_key_raises_403(db_session):
    t = Tenant(name="acme", anthropic_api_key=None, active=True)
    db_session.add(t)
    await db_session.commit()

    request = _make_request({"Authorization": f"Bearer {t.api_key}"})
    with pytest.raises(HTTPException) as exc:
        await _resolve_tenant(request, db_session)
    assert exc.value.status_code == 403


async def test_resolve_tenant_valid_returns_tenant(db_session):
    t = Tenant(name="acme", anthropic_api_key="sk-ant-x", active=True)
    db_session.add(t)
    await db_session.commit()

    request = _make_request({"Authorization": f"Bearer {t.api_key}"})
    resolved = await _resolve_tenant(request, db_session)
    assert resolved is not None
    assert resolved.id == t.id


# ---- Per-tenant rate limit ---------------------------------------------


def test_rate_limit_blocks_after_threshold():
    from app.core import rate_limit as rl

    rl.reset()
    key = "test-bucket"
    # 3 hits allowed, 4th should raise.
    rl.check(key, 3)
    rl.check(key, 3)
    rl.check(key, 3)
    with pytest.raises(HTTPException) as exc:
        rl.check(key, 3)
    assert exc.value.status_code == 429


def test_rate_limit_zero_means_unlimited():
    from app.core import rate_limit as rl

    rl.reset()
    for _ in range(50):
        rl.check("unbounded", 0)


def test_rate_limit_separate_keys_isolated():
    from app.core import rate_limit as rl

    rl.reset()
    rl.check("a", 2)
    rl.check("a", 2)
    # Bucket "b" is independent and should still allow hits.
    rl.check("b", 2)
    rl.check("b", 2)
    with pytest.raises(HTTPException):
        rl.check("a", 2)
    with pytest.raises(HTTPException):
        rl.check("b", 2)
