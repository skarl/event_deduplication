"""REST API endpoints for dynamic matching configuration."""

from __future__ import annotations

from datetime import datetime, timezone

import sqlalchemy as sa
import structlog
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from event_dedup.api.deps import get_db
from event_dedup.api.schemas import (
    ConfigResponse,
    ConfigUpdateRequest,
    config_to_response,
)
from event_dedup.config.encryption import decrypt_value, encrypt_value
from event_dedup.matching.config import MatchingConfig
from event_dedup.models.config_settings import ConfigSettings

logger = structlog.get_logger()

router = APIRouter(prefix="/api/config", tags=["config"])


def _deep_merge(base: dict, updates: dict) -> dict:
    """Recursively merge *updates* into *base*, only overwriting leaves."""
    merged = dict(base)
    for key, value in updates.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


@router.get("", response_model=ConfigResponse)
async def get_config(db: AsyncSession = Depends(get_db)) -> ConfigResponse:
    """Return the current matching configuration.

    If no configuration has been saved to the database yet, returns all
    default values.  The Gemini API key is never included in the response;
    ``has_api_key`` indicates whether one is stored.
    """
    result = await db.execute(
        sa.select(ConfigSettings).where(ConfigSettings.id == 1)
    )
    row = result.scalar_one_or_none()

    if row is None:
        config = MatchingConfig()
        return ConfigResponse(**config_to_response(config))

    config = MatchingConfig(**row.config_json)
    updated_at = row.updated_at.isoformat() if row.updated_at else None
    return ConfigResponse(
        **config_to_response(
            config,
            has_api_key=row.encrypted_api_key is not None,
            updated_at=updated_at,
        )
    )


@router.patch("", response_model=ConfigResponse)
async def patch_config(
    body: ConfigUpdateRequest,
    db: AsyncSession = Depends(get_db),
) -> ConfigResponse:
    """Apply a partial update to the matching configuration.

    Only the fields present in the request body are updated; unset fields
    retain their current (or default) values.  The ``ai_api_key`` field is
    handled specially: a non-empty value is encrypted and stored; an empty
    string clears it.
    """
    # Load current state
    result = await db.execute(
        sa.select(ConfigSettings).where(ConfigSettings.id == 1)
    )
    row = result.scalar_one_or_none()

    if row is not None:
        current_config = MatchingConfig(**row.config_json)
    else:
        current_config = MatchingConfig()

    # Deep merge the update into the current config
    update_data = body.model_dump(exclude_unset=True, exclude={"ai_api_key"})
    merged = _deep_merge(current_config.model_dump(), update_data)

    # Validate merged config through Pydantic
    new_config = MatchingConfig(**merged)

    # Prepare the JSON blob -- strip api_key so it never leaks into config_json
    config_dict = new_config.model_dump()
    config_dict.get("ai", {}).pop("api_key", None)

    # Handle API key
    encrypted_api_key = row.encrypted_api_key if row else None
    if body.ai_api_key is not None:
        if body.ai_api_key == "":
            encrypted_api_key = None
            logger.info("api_key_cleared")
        else:
            encrypted_api_key = encrypt_value(body.ai_api_key)
            logger.info("api_key_updated")

    # If the API key is set, ensure ai.enabled stays in sync (user can
    # explicitly control this, but setting a key implies intent to use AI)
    if encrypted_api_key is not None:
        # Decrypt to set on config for validation; but don't store in JSON
        decrypted_key = decrypt_value(encrypted_api_key)
        new_config.ai.api_key = decrypted_key

    now = datetime.now(timezone.utc)

    if row is None:
        row = ConfigSettings(
            id=1,
            config_json=config_dict,
            encrypted_api_key=encrypted_api_key,
            updated_at=now,
            updated_by="api",
        )
        db.add(row)
    else:
        row.config_json = config_dict
        row.encrypted_api_key = encrypted_api_key
        row.updated_at = now
        row.updated_by = "api"

    await db.commit()
    await db.refresh(row)

    logger.info("config_updated", updated_at=now.isoformat())

    updated_at = row.updated_at.isoformat() if row.updated_at else None
    return ConfigResponse(
        **config_to_response(
            new_config,
            has_api_key=row.encrypted_api_key is not None,
            updated_at=updated_at,
        )
    )
