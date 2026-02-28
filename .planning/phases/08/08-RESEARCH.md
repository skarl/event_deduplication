# Phase 8: Dynamic Configuration System - Research

**Researched:** 2026-02-28
**Domain:** Database-backed configuration with REST API and React frontend
**Confidence:** HIGH

## Summary

Phase 8 replaces the current YAML-only configuration (`config/matching.yaml`) with a database-backed config system that is editable via a frontend page. The existing `MatchingConfig` Pydantic model in `src/event_dedup/matching/config.py` already defines all configurable parameters with defaults -- this phase adds a persistence layer (PostgreSQL table), a REST API (GET + PATCH), and a React config page. The worker currently loads config once at startup via `load_matching_config()` in `worker/__main__.py`; it needs to load from DB at pipeline-run time instead, falling back to YAML defaults when no DB config exists.

The Gemini API key is a special case: it must be stored securely (encrypted at rest or at minimum never returned in API responses) and displayed as write-only in the frontend (masked after saving). The existing `settings.gemini_api_key` env var and `ai_config.api_key` field already handle runtime access -- this phase adds persistent DB storage.

**Primary recommendation:** Use a single-row key-value config table storing the full `MatchingConfig` as a JSON column, with a thin SQLAlchemy model and Pydantic schema for validation. The API key gets a separate encrypted column. Keep the existing `MatchingConfig` Pydantic model as the source of truth for validation and defaults.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| CFG-01 | Store all matching config in DB with REST API; changes take effect on next pipeline run without restart | Single-row config table + GET/PATCH endpoints + worker loads from DB per-run |
| CFG-02 | Frontend config page for viewing/editing all matching parameters | React config page with grouped sections, Pydantic schema drives form structure |
| CFG-03 | Gemini API key stored securely, write-only in frontend, never returned in GET | Separate encrypted column, API schema excludes it from GET response, PATCH accepts write |
| CFG-04 | AI matching on/off toggle, visible and editable from frontend | `ai.enabled` boolean in config model, toggle component in AI section |
| CFG-05 | Previously hardcoded values now editable: scoring weights, thresholds, date/time, geo, title, cluster, AI params | All fields already defined in `MatchingConfig` Pydantic model -- expose in DB + API + frontend |
</phase_requirements>

## Standard Stack

### Core (already in project)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| SQLAlchemy | 2.0.47 | ORM for config table | Already used for all models |
| Alembic | 1.18.4 | Database migration for config table | Already used for all schema changes |
| FastAPI | 0.134.0 | REST API endpoints | Already used for all API routes |
| Pydantic | 2.12.5 | Config validation + API schemas | Already used for MatchingConfig and all API schemas |
| React 19 + TanStack Query 5 | 19.2.0 / 5.90.21 | Frontend config page | Already used for all frontend pages |
| Tailwind CSS 4 | 4.2.1 | Styling | Already used for all frontend styling |

### Supporting (already in project)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pydantic-settings | 2.x | Environment variable config | Already used in `settings.py` |
| structlog | 24.x | Logging config changes | Already used throughout |
| cryptography | (add) | Fernet encryption for API key | Only for CFG-03 API key encryption |

### New Dependency
| Library | Version | Purpose | Why |
|---------|---------|---------|-----|
| cryptography | latest | Fernet symmetric encryption for Gemini API key at rest | Standard Python encryption library, well-maintained, simple Fernet API for encrypt/decrypt |

**Installation:**
```bash
uv add cryptography
```

## Architecture Patterns

### Database Model: Single-Row Config Table

Use a single-row table with a JSON column storing the full `MatchingConfig` as serialized JSON, plus a separate `encrypted_api_key` column. This pattern is simpler than a key-value table and leverages Pydantic's existing serialization.

```
config_settings (single row, id=1)
├── id: Integer (PK, always 1)
├── config_json: JSON (stores full MatchingConfig minus API key)
├── encrypted_api_key: Text (Fernet-encrypted Gemini API key)
├── updated_at: DateTime
└── updated_by: String (operator name)
```

**Why single-row JSON over key-value:**
- The `MatchingConfig` Pydantic model already defines the complete structure with types and defaults
- Pydantic handles validation, defaults, and partial updates via `model_copy(update=...)`
- No mapping layer needed between flat KV rows and nested config objects
- PostgreSQL JSON column supports querying if ever needed

### Recommended Project Structure
```
src/event_dedup/
├── config/
│   ├── settings.py          # Existing env settings (unchanged)
│   ├── encryption.py        # NEW: Fernet encrypt/decrypt for API key
│   └── ...
├── models/
│   ├── config_settings.py   # NEW: SQLAlchemy model for config table
│   └── ...
├── api/
│   ├── routes/
│   │   ├── config.py        # NEW: GET/PATCH /api/config endpoints
│   │   └── ...
│   └── schemas.py           # EXTEND: Add config request/response schemas
├── matching/
│   ├── config.py            # EXTEND: Add load_config_from_db() function
│   └── ...
└── worker/
    ├── __main__.py           # MODIFY: Load config from DB at startup
    └── orchestrator.py       # MODIFY: Reload config from DB per pipeline run

frontend/src/
├── api/
│   └── client.ts            # EXTEND: Add fetchConfig, updateConfig
├── components/
│   └── ConfigPage.tsx        # NEW: Grouped config editor
├── hooks/
│   └── useConfig.ts          # NEW: TanStack Query hooks for config
├── types/
│   └── index.ts              # EXTEND: Add config types
└── App.tsx                   # MODIFY: Add /config route + nav link
```

### Pattern 1: Single-Row Upsert for Config
**What:** Config table always has exactly one row (id=1). GET returns it (or defaults). PATCH does upsert.
**When to use:** Always -- this is the only config pattern.
**Example:**
```python
# SQLAlchemy model
class ConfigSettings(Base):
    __tablename__ = "config_settings"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    config_json: Mapped[dict] = mapped_column(JSON, default=dict)
    encrypted_api_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )
    updated_by: Mapped[str] = mapped_column(String(100), default="system")
```

### Pattern 2: Pydantic-Driven Partial Update
**What:** PATCH body is a partial dict. Merge with existing config using Pydantic's `model_copy(update=...)`. Validate the result.
**When to use:** For the PATCH /api/config endpoint.
**Example:**
```python
@router.patch("/api/config")
async def update_config(updates: dict, db: AsyncSession = Depends(get_db)):
    # Load existing config from DB (or defaults)
    current = await get_config_from_db(db)

    # Extract API key before merging (handled separately)
    api_key = updates.pop("ai_api_key", None)

    # Deep merge: reconstruct MatchingConfig with updates
    current_dict = current.model_dump()
    merged = deep_merge(current_dict, updates)
    validated = MatchingConfig(**merged)  # Pydantic validates

    # Persist
    await upsert_config(db, validated, api_key)
    return config_response(validated)
```

### Pattern 3: Config Loading with DB Fallback
**What:** Worker loads config from DB at each pipeline run. Falls back to YAML if DB has no config.
**When to use:** In the worker orchestrator, before each `run_full_pipeline` call.
**Example:**
```python
async def load_config_for_run(session_factory) -> MatchingConfig:
    """Load config from DB, falling back to YAML defaults."""
    async with session_factory() as session:
        row = await session.get(ConfigSettings, 1)

    if row and row.config_json:
        config = MatchingConfig(**row.config_json)
        if row.encrypted_api_key:
            config.ai.api_key = decrypt(row.encrypted_api_key)
        return config

    # Fallback to YAML
    settings = get_settings()
    return load_matching_config(settings.matching_config_path)
```

### Pattern 4: Write-Only API Key in API Schema
**What:** GET response schema omits `ai.api_key`. PATCH request schema accepts `ai_api_key` as a top-level write-only field. GET returns `has_api_key: bool` instead.
**When to use:** For CFG-03 secure API key handling.
**Example:**
```python
class ConfigResponse(BaseModel):
    """GET /api/config response -- never includes API key."""
    scoring: ScoringWeights
    thresholds: ThresholdConfig
    geo: GeoConfig
    date: DateConfig
    title: TitleConfig
    cluster: ClusterConfig
    ai: AIConfigResponse  # ai_api_key excluded, has_api_key included
    has_api_key: bool
    updated_at: str | None

class AIConfigResponse(BaseModel):
    """AI config for GET responses -- key excluded."""
    enabled: bool
    model: str
    temperature: float
    max_output_tokens: int
    confidence_threshold: float
    cache_enabled: bool
    # No api_key field!

class ConfigUpdateRequest(BaseModel):
    """PATCH /api/config request -- supports partial updates."""
    scoring: ScoringWeights | None = None
    thresholds: ThresholdConfig | None = None
    # ... etc
    ai: AIConfigUpdate | None = None
    ai_api_key: str | None = None  # Write-only, stored encrypted
```

### Pattern 5: Frontend Grouped Config Sections
**What:** Config page organized into collapsible/tabbed sections matching the config model structure.
**When to use:** For CFG-02 frontend config page.

Frontend sections:
1. **Scoring Weights** -- date, geo, title, description weights (must sum to 1.0)
2. **Thresholds** -- high/low match thresholds
3. **Date/Time** -- time_tolerance_minutes, time_close_minutes, close_factor, far_factor
4. **Geographic** -- max_distance_km, min_confidence, neutral_score
5. **Title Matching** -- primary/secondary weights, blend bounds, cross-source-type
6. **AI Matching** -- enabled toggle, API key (masked input), model, temperature, confidence_threshold
7. **Clustering** -- max_cluster_size, min_internal_similarity

### Anti-Patterns to Avoid
- **Key-value table with string serialization:** Would require mapping layer, lose type safety, complex queries for nested config. Use JSON column instead.
- **Caching config in worker memory:** Config must be fresh from DB at each pipeline run. Don't cache between runs.
- **Returning API key in GET responses:** Even partially masked. Use a separate `has_api_key: bool` flag.
- **Storing API key in the JSON column:** Keep it in a separate encrypted column so it's impossible to accidentally serialize.
- **Frontend storing config locally:** Always fetch from API. Use TanStack Query's invalidation on mutation.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Encryption | Custom encryption scheme | `cryptography.fernet.Fernet` | Battle-tested, symmetric encryption, simple API |
| Config validation | Manual type checking | Pydantic `MatchingConfig(**data)` | Already validates all fields with types and defaults |
| Deep merge | Recursive dict merge | Pydantic `model_copy(update=...)` or simple recursive merge | Edge cases with None vs missing, nested models |
| Form generation | Manual form field mapping | Derive from config structure | Config sections already match Pydantic model structure |
| API response filtering | Manual field exclusion | Separate Pydantic response model | Pydantic schemas guarantee API key never leaks |

**Key insight:** The existing `MatchingConfig` Pydantic model is already the complete specification of all configurable parameters. The config system is essentially a persistence + API + UI layer around this existing model.

## Common Pitfalls

### Pitfall 1: Losing YAML Defaults on First DB Save
**What goes wrong:** Operator changes one setting via frontend, but the DB row only stores that one field. On next load, all other fields get Pydantic defaults instead of YAML-file values.
**Why it happens:** Partial update stored as partial JSON, not merged with full defaults.
**How to avoid:** Always store the COMPLETE `MatchingConfig` in DB. On first PATCH, load YAML defaults first, merge the update, then persist the full config.
**Warning signs:** Config values suddenly reset to defaults after first frontend edit.

### Pitfall 2: Category Weights and Cross-Source-Type Config
**What goes wrong:** The `category_weights` (with priority list and overrides map) and `title.cross_source_type` (nested TitleConfig) are complex nested structures that may not serialize/deserialize cleanly through JSON.
**Why it happens:** Pydantic model has `dict[str, ScoringWeights]` and `TitleConfig | None` which need careful JSON handling.
**How to avoid:** Use `MatchingConfig.model_dump()` for serialization and `MatchingConfig(**data)` for deserialization -- Pydantic handles nested models correctly. Test the round-trip explicitly.
**Warning signs:** Category weight overrides or cross-source-type settings lost after save/load.

### Pitfall 3: Concurrent Config Updates
**What goes wrong:** Two operators edit config simultaneously; one overwrites the other's changes.
**Why it happens:** No optimistic locking.
**How to avoid:** Include `updated_at` in the PATCH request. Compare with DB `updated_at` before saving. Return 409 Conflict if stale. This is an internal tool with few users, so simple timestamp check is sufficient.
**Warning signs:** Config changes disappear after saving.

### Pitfall 4: Encryption Key Management
**What goes wrong:** Fernet key not persisted, or different across containers. API key becomes unreadable after restart.
**Why it happens:** Fernet key generated randomly and not stored.
**How to avoid:** Store the Fernet key as an environment variable (`EVENT_DEDUP_ENCRYPTION_KEY`). Generate once, persist in `.env` or Docker secrets. If no key is set, fall back to env var for the API key directly (backward compatibility).
**Warning signs:** "Invalid token" errors when decrypting API key after container restart.

### Pitfall 5: Worker Config Not Refreshing
**What goes wrong:** Worker loads config once at startup, ignores DB changes.
**Why it happens:** Current code in `__main__.py` calls `load_matching_config()` once, passes the config object to all functions.
**How to avoid:** Move config loading into the orchestrator's `process_new_file` / `process_file_batch` functions so it's loaded from DB at each pipeline run. Keep the startup load for initial validation.
**Warning signs:** Config changes via frontend have no effect until worker restart.

### Pitfall 6: Scoring Weights Must Sum to 1.0
**What goes wrong:** Operator sets scoring weights that don't sum to 1.0, producing nonsensical match scores.
**Why it happens:** Frontend allows arbitrary float inputs.
**How to avoid:** Add a Pydantic validator on `ScoringWeights` that warns/normalizes when sum != 1.0. Frontend shows live sum and validation warning.
**Warning signs:** Match scores suddenly out of expected range.

## Code Examples

### Migration: Create config_settings table
```python
# config/alembic/versions/005_add_config_settings.py
"""Add config_settings table for dynamic configuration."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON

revision = "005_config_settings"
down_revision = "004_audit_log"  # Verify actual head
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "config_settings",
        sa.Column("id", sa.Integer(), primary_key=True, default=1),
        sa.Column("config_json", JSON(), nullable=False, server_default="{}"),
        sa.Column("encrypted_api_key", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_by", sa.String(100), server_default="system"),
    )

def downgrade() -> None:
    op.drop_table("config_settings")
```

### SQLAlchemy Model
```python
# src/event_dedup/models/config_settings.py
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column
from event_dedup.models.base import Base

class ConfigSettings(Base):
    __tablename__ = "config_settings"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    config_json: Mapped[dict] = mapped_column(JSON, server_default="{}", default=dict)
    encrypted_api_key: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime, server_default=sa.text("CURRENT_TIMESTAMP")
    )
    updated_by: Mapped[str] = mapped_column(sa.String(100), server_default="system")
```

### Encryption Utility
```python
# src/event_dedup/config/encryption.py
import os
from cryptography.fernet import Fernet

def get_fernet() -> Fernet:
    key = os.environ.get("EVENT_DEDUP_ENCRYPTION_KEY")
    if not key:
        raise ValueError("EVENT_DEDUP_ENCRYPTION_KEY not set")
    return Fernet(key.encode())

def encrypt_value(value: str) -> str:
    return get_fernet().encrypt(value.encode()).decode()

def decrypt_value(token: str) -> str:
    return get_fernet().decrypt(token.encode()).decode()
```

### API Route: GET /api/config
```python
@router.get("/api/config", response_model=ConfigResponse)
async def get_config(db: AsyncSession = Depends(get_db)):
    row = await db.get(ConfigSettings, 1)
    if not row:
        config = MatchingConfig()  # All defaults
        return ConfigResponse(
            **config_to_response(config),
            has_api_key=False,
            updated_at=None,
        )

    config = MatchingConfig(**row.config_json)
    return ConfigResponse(
        **config_to_response(config),
        has_api_key=row.encrypted_api_key is not None,
        updated_at=row.updated_at.isoformat() if row.updated_at else None,
    )
```

### API Route: PATCH /api/config
```python
@router.patch("/api/config", response_model=ConfigResponse)
async def update_config(
    request: ConfigUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    row = await db.get(ConfigSettings, 1)

    # Load current config (from DB or defaults)
    if row and row.config_json:
        current = MatchingConfig(**row.config_json)
    else:
        # First edit: start from YAML defaults
        settings = get_settings()
        current = load_matching_config(settings.matching_config_path)

    # Merge updates
    updates = request.model_dump(exclude_unset=True, exclude={"ai_api_key"})
    current_dict = current.model_dump()
    merged = deep_merge(current_dict, updates)
    validated = MatchingConfig(**merged)

    # Handle API key separately
    encrypted_key = row.encrypted_api_key if row else None
    if request.ai_api_key is not None:
        if request.ai_api_key == "":
            encrypted_key = None  # Clear the key
        else:
            encrypted_key = encrypt_value(request.ai_api_key)

    # Upsert
    config_dict = validated.model_dump()
    config_dict.pop("ai", None)  # Remove ai section, re-add without key
    ai_dict = validated.ai.model_dump()
    ai_dict.pop("api_key", None)
    config_dict["ai"] = ai_dict

    if row:
        row.config_json = config_dict
        row.encrypted_api_key = encrypted_key
    else:
        row = ConfigSettings(
            id=1, config_json=config_dict,
            encrypted_api_key=encrypted_key,
        )
        db.add(row)

    await db.commit()
    await db.refresh(row)

    return ConfigResponse(
        **config_to_response(validated),
        has_api_key=encrypted_key is not None,
        updated_at=row.updated_at.isoformat(),
    )
```

### Worker Config Loading (per pipeline run)
```python
# In orchestrator.py
async def load_config_for_run(
    session_factory: async_sessionmaker,
) -> MatchingConfig:
    """Load matching config from DB, falling back to YAML."""
    from event_dedup.models.config_settings import ConfigSettings

    async with session_factory() as session:
        row = await session.get(ConfigSettings, 1)

    if row and row.config_json:
        config = MatchingConfig(**row.config_json)
        # Restore API key from encrypted column
        if row.encrypted_api_key:
            try:
                config.ai.api_key = decrypt_value(row.encrypted_api_key)
            except Exception:
                pass  # Key decryption failed, leave empty
        return config

    # Fallback: YAML file
    settings = get_settings()
    config = load_matching_config(settings.matching_config_path)
    # Override from env var (backward compat)
    if settings.gemini_api_key:
        config.ai.enabled = True
        config.ai.api_key = settings.gemini_api_key
    return config
```

### Frontend Config Page (React)
```tsx
// ConfigPage.tsx - grouped sections pattern
function ConfigPage() {
  const { data: config, isLoading } = useConfig();
  const updateConfig = useUpdateConfig();

  if (isLoading) return <div>Loading...</div>;

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">Configuration</h2>

      <ScoringSection
        values={config.scoring}
        onChange={(scoring) => updateConfig.mutate({ scoring })}
      />
      <ThresholdSection
        values={config.thresholds}
        onChange={(thresholds) => updateConfig.mutate({ thresholds })}
      />
      <DateTimeSection values={config.date} onChange={...} />
      <GeoSection values={config.geo} onChange={...} />
      <TitleSection values={config.title} onChange={...} />
      <AISection
        values={config.ai}
        hasApiKey={config.has_api_key}
        onChange={...}
      />
      <ClusterSection values={config.cluster} onChange={...} />
    </div>
  );
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| YAML file loaded once at worker startup | DB-backed config loaded per pipeline run | Phase 8 | Config changes take effect immediately, no restart needed |
| Gemini API key in env var only | DB-stored encrypted API key + env var fallback | Phase 8 | Operators can set API key via frontend |
| Hardcoded AI enabled/disabled based on env var | DB-stored toggle, editable via frontend | Phase 8 | Non-developer operators can toggle AI matching |

**Backward compatibility:** Env vars (`EVENT_DEDUP_GEMINI_API_KEY`) continue to work as fallback. YAML config is used when no DB config exists. Existing deployments work unchanged until operator first saves config via frontend.

## Open Questions

1. **Category weight overrides editing in frontend**
   - What we know: `category_weights` has a priority list and a map of category-name -> ScoringWeights. This is a complex nested structure.
   - What's unclear: Whether operators need to edit category-specific weight overrides via the frontend, or if those remain YAML-only initially.
   - Recommendation: Include category weights in the DB config (they serialize fine as JSON), but keep the frontend editor simple -- show read-only display of category overrides initially. Full editing can be added later if needed. The requirement says "all matching parameters editable" so at minimum display them.

2. **Field strategies editing**
   - What we know: `canonical.field_strategies` maps field names to strategy names (strings like "longest", "union", etc.).
   - What's unclear: Whether operators should be able to change field merge strategies via the frontend.
   - Recommendation: Include in DB config but mark as "Advanced" section. Strategy names are constrained to a known set -- use dropdown selectors.

3. **Encryption key bootstrapping**
   - What we know: Fernet needs a persistent key. Docker deployments need it in environment.
   - What's unclear: First-time setup flow for generating the key.
   - Recommendation: Add a generate-key CLI command or document the one-liner: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`. If no encryption key is configured, fall back to storing the API key unencrypted (with a warning log) for development simplicity.

## Sources

### Primary (HIGH confidence)
- Project codebase: `src/event_dedup/matching/config.py` -- Full MatchingConfig model with all fields and defaults
- Project codebase: `src/event_dedup/worker/__main__.py` -- Current config loading at startup
- Project codebase: `src/event_dedup/worker/orchestrator.py` -- Pipeline execution flow
- Project codebase: `src/event_dedup/api/routes/canonical_events.py` -- Existing API route patterns
- Project codebase: `config/alembic/versions/003_add_ai_matching_tables.py` -- Migration patterns
- Project codebase: `tests/conftest.py` -- Test fixture patterns (SQLite in-memory, api_client)
- Project codebase: `frontend/src/api/client.ts` -- Frontend API client patterns
- Project codebase: `pyproject.toml` -- Dependency versions confirmed

### Secondary (MEDIUM confidence)
- SQLAlchemy 2.0 JSON column: Well-documented feature for PostgreSQL JSON columns with SQLAlchemy ORM
- Pydantic 2.x model_dump/model_copy: Standard API for serialization and partial updates
- cryptography.fernet: Standard symmetric encryption in Python, well-documented

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- All libraries already in use, just adding one dependency (cryptography)
- Architecture: HIGH -- Single-row config table is a well-known pattern, fits the existing Pydantic model perfectly
- Pitfalls: HIGH -- Identified from direct codebase analysis of current config loading flow
- Frontend: HIGH -- Follows exact same patterns as existing components (TanStack Query hooks, Tailwind styling)

**Research date:** 2026-02-28
**Valid until:** 2026-03-28 (stable project, no external dependency changes expected)
