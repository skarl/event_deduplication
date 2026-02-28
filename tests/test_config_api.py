"""Tests for the dynamic configuration API (GET/PATCH /api/config)."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from event_dedup.config.encryption import encrypt_value
from event_dedup.matching.config import MatchingConfig, load_config_for_run
from event_dedup.models.config_settings import ConfigSettings


# ---------------------------------------------------------------------------
# GET defaults
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_config_defaults(api_client):
    """GET /api/config returns 200 with all defaults when no DB row exists."""
    resp = await api_client.get("/api/config")
    assert resp.status_code == 200
    data = resp.json()

    # Check default scoring weights
    assert data["scoring"]["date"] == 0.30
    assert data["scoring"]["geo"] == 0.25
    assert data["scoring"]["title"] == 0.30
    assert data["scoring"]["description"] == 0.15

    # Check default thresholds
    assert data["thresholds"]["high"] == 0.75
    assert data["thresholds"]["low"] == 0.35

    # No API key stored
    assert data["has_api_key"] is False
    assert data["updated_at"] is None

    # AI section should NOT contain api_key
    assert "api_key" not in data["ai"]
    assert data["ai"]["enabled"] is False
    assert data["ai"]["model"] == "gemini-2.5-flash"


# ---------------------------------------------------------------------------
# PATCH scoring
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_patch_config_scoring(api_client):
    """PATCH with scoring.date=0.4 updates that field, leaves others at defaults."""
    resp = await api_client.patch(
        "/api/config", json={"scoring": {"date": 0.4, "geo": 0.2, "title": 0.25, "description": 0.15}}
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["scoring"]["date"] == 0.4
    assert data["scoring"]["geo"] == 0.2
    assert data["scoring"]["title"] == 0.25
    assert data["scoring"]["description"] == 0.15

    # Other sections remain at defaults
    assert data["thresholds"]["high"] == 0.75


# ---------------------------------------------------------------------------
# PATCH preserves unset fields
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_patch_config_preserves_unset(api_client):
    """PATCH scoring then PATCH thresholds -- scoring changes are preserved."""
    # First patch: update scoring
    await api_client.patch(
        "/api/config", json={"scoring": {"date": 0.4, "geo": 0.2, "title": 0.25, "description": 0.15}}
    )

    # Second patch: update thresholds only
    resp = await api_client.patch(
        "/api/config", json={"thresholds": {"high": 0.8}}
    )
    assert resp.status_code == 200
    data = resp.json()

    # Scoring should still reflect the first patch
    assert data["scoring"]["date"] == 0.4
    # Thresholds updated
    assert data["thresholds"]["high"] == 0.8


# ---------------------------------------------------------------------------
# API key handling
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_patch_api_key_not_in_get(api_client):
    """PATCH with ai_api_key sets has_api_key=True; GET never returns the key."""
    resp = await api_client.patch(
        "/api/config", json={"ai_api_key": "test-secret-key"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["has_api_key"] is True
    assert "api_key" not in data["ai"]

    # GET also shows has_api_key=True but no key value
    resp2 = await api_client.get("/api/config")
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["has_api_key"] is True
    assert "api_key" not in data2["ai"]


@pytest.mark.asyncio
async def test_clear_api_key(api_client):
    """PATCH with ai_api_key="" clears the stored key."""
    # Set key first
    await api_client.patch("/api/config", json={"ai_api_key": "some-key"})

    # Clear it
    resp = await api_client.patch("/api/config", json={"ai_api_key": ""})
    assert resp.status_code == 200
    data = resp.json()
    assert data["has_api_key"] is False


# ---------------------------------------------------------------------------
# AI enabled toggle
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_patch_ai_enabled_toggle(api_client):
    """PATCH toggles ai.enabled on and off."""
    resp_on = await api_client.patch(
        "/api/config", json={"ai": {"enabled": True}}
    )
    assert resp_on.status_code == 200
    assert resp_on.json()["ai"]["enabled"] is True

    resp_off = await api_client.patch(
        "/api/config", json={"ai": {"enabled": False}}
    )
    assert resp_off.status_code == 200
    assert resp_off.json()["ai"]["enabled"] is False


# ---------------------------------------------------------------------------
# Deep merge nested
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_deep_merge_nested(api_client):
    """PATCH with title.primary_weight preserves other title fields."""
    resp = await api_client.patch(
        "/api/config", json={"title": {"primary_weight": 0.8}}
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["title"]["primary_weight"] == 0.8
    # Other title defaults preserved
    assert data["title"]["secondary_weight"] == 0.3
    assert data["title"]["blend_lower"] == 0.40
    assert data["title"]["blend_upper"] == 0.80


# ---------------------------------------------------------------------------
# Round trip
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_config_round_trip(api_client):
    """PATCH complex config then GET returns the same values."""
    payload = {
        "scoring": {"date": 0.25, "geo": 0.25, "title": 0.25, "description": 0.25},
        "thresholds": {"high": 0.80, "low": 0.30},
        "geo": {"max_distance_km": 15.0},
        "date": {"time_tolerance_minutes": 45},
        "cluster": {"max_cluster_size": 20},
        "canonical": {
            "field_strategies": {
                "title": "longest",
                "description": "longest",
            }
        },
        "category_weights": {
            "priority": ["musik", "sport"],
            "overrides": {
                "musik": {"date": 0.20, "geo": 0.20, "title": 0.40, "description": 0.20}
            },
        },
    }

    patch_resp = await api_client.patch("/api/config", json=payload)
    assert patch_resp.status_code == 200

    get_resp = await api_client.get("/api/config")
    assert get_resp.status_code == 200
    data = get_resp.json()

    assert data["scoring"]["date"] == 0.25
    assert data["thresholds"]["high"] == 0.80
    assert data["geo"]["max_distance_km"] == 15.0
    assert data["date"]["time_tolerance_minutes"] == 45
    assert data["cluster"]["max_cluster_size"] == 20
    assert data["canonical"]["field_strategies"]["title"] == "longest"
    assert data["category_weights"]["priority"] == ["musik", "sport"]
    assert data["category_weights"]["overrides"]["musik"]["title"] == 0.40


# ---------------------------------------------------------------------------
# load_config_for_run
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_load_config_for_run(test_session_factory):
    """load_config_for_run returns config from DB when a row exists."""
    # Seed a ConfigSettings row
    config = MatchingConfig(scoring=MatchingConfig().scoring.model_copy(update={"date": 0.5, "geo": 0.2, "title": 0.2, "description": 0.1}))
    config_dict = config.model_dump()
    config_dict.get("ai", {}).pop("api_key", None)

    encrypted_key = encrypt_value("my-gemini-key")

    async with test_session_factory() as session:
        row = ConfigSettings(
            id=1,
            config_json=config_dict,
            encrypted_api_key=encrypted_key,
        )
        session.add(row)
        await session.commit()

    # Load config
    loaded = await load_config_for_run(test_session_factory)

    assert loaded.scoring.date == 0.5
    assert loaded.ai.api_key == "my-gemini-key"
