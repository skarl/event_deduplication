# Phase 5: AI-Assisted Matching - Research

**Researched:** 2026-02-28
**Domain:** LLM-based event deduplication judgment (Gemini Flash API, structured output, caching, cost monitoring)
**Confidence:** HIGH

## Summary

The AI-assisted matching tier resolves ambiguous event pairs (combined score between 0.35 and 0.75) that deterministic scoring cannot confidently classify. The Google Gen AI SDK (`google-genai`) is the current unified Python SDK for Gemini, replacing the deprecated `google-generativeai`. Gemini 2.5 Flash is the recommended model: it supports structured JSON output via Pydantic schemas, has async support via `client.aio`, includes built-in retry with exponential backoff, and returns `usage_metadata` with per-request token counts for cost tracking.

The integration point is clean: the current pipeline produces `MatchDecisionRecord` objects with `decision="ambiguous"` and `tier="deterministic"`. The AI tier filters these, sends event pairs to Gemini Flash with a structured prompt, receives structured JSON responses (decision + confidence + reasoning), updates the decision records to `tier="ai"`, and feeds the resolved pairs back into the clustering step. The pipeline is currently pure/sync, so the AI tier should be an async function called from the worker orchestrator (which is already async).

**Primary recommendation:** Use `google-genai` SDK with `gemini-2.5-flash` model, Pydantic-based structured output, content-hash-based database caching, and per-response token tracking aggregated into a cost report.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| AI-01 | Ambiguous event pairs (scoring between low and high threshold) are sent to an LLM for resolution | Pipeline already produces `decision="ambiguous"` records; filter these, send to Gemini Flash, update tier to "ai" |
| AI-02 | AI matching uses Gemini Flash (or best cost-effective model determined during research) | Gemini 2.5 Flash (`gemini-2.5-flash`) is the best cost-performance model: $0.30/1M input, $2.50/1M output, 1M context window, structured output support |
| AI-03 | AI responses include structured decision, confidence score, and reasoning | Gemini Flash supports `response_mime_type="application/json"` with Pydantic `response_schema`; define `AIMatchResult(decision, confidence, reasoning)` |
| AI-04 | AI match results are cached to avoid re-evaluating identical pairs | Content-hash (SHA-256 of normalized event pair fields) stored in a database table; check before API call |
| AI-05 | AI usage is cost-monitored with per-batch and per-period reporting | `response.usage_metadata.prompt_token_count` + `candidates_token_count` tracked per request; aggregate in `ai_usage_log` table |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| google-genai | >=1.65 | Gemini API client | Official unified Google Gen AI SDK; replaces deprecated `google-generativeai`; supports both AI Studio and Vertex AI |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pydantic | (already in project) | Structured output schema | Define `AIMatchResult` model for Gemini JSON response schema |
| structlog | (already in project) | AI tier logging | Log API calls, cache hits, token usage, errors |
| hashlib | (stdlib) | Content hashing | Generate deterministic cache keys from event pair content |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| gemini-2.5-flash | gemini-2.5-flash-lite | 3x cheaper ($0.10/$0.40 per 1M input/output) but less capable reasoning; may produce lower quality dedup judgments. Try flash first, benchmark on ground truth, fall back to flash-lite if cost is a concern |
| google-genai | litellm | Unified multi-provider interface but adds dependency; unnecessary since project is Gemini-only |
| Database cache | In-memory cache (dict/lru_cache) | Lost on restart; database survives container restarts and enables cache analytics |

**Installation:**
```bash
uv add google-genai
```

## Architecture Patterns

### Recommended Module Structure
```
src/event_dedup/
  ai_matching/
    __init__.py
    client.py          # Gemini client initialization, API call wrapper
    prompt.py          # Prompt template and event formatting
    schemas.py         # Pydantic models for AI request/response
    cache.py           # Content-hash cache lookup/store
    cost_tracker.py    # Token usage aggregation and reporting
    resolver.py        # Orchestrator: filter ambiguous -> check cache -> call AI -> update decisions
  matching/
    pipeline.py        # Existing; add resolve_ambiguous_pairs() integration point
    config.py          # Add AIMatchingConfig section
  models/
    ai_match_cache.py  # SQLAlchemy model for cached AI results
    ai_usage_log.py    # SQLAlchemy model for usage tracking
```

### Pattern 1: AI Resolver as Pipeline Post-Processor

**What:** The AI resolver runs AFTER deterministic scoring, BEFORE clustering. It takes the list of `MatchDecisionRecord` objects, filters for `decision="ambiguous"`, resolves them via Gemini Flash, and returns updated decisions.

**When to use:** Always -- this is the core integration pattern.

**Why this pattern:** The matching pipeline is pure/sync. Rather than making it async, the AI resolution step runs as a separate async function called from the worker orchestrator (which is already async). The pipeline produces ambiguous decisions; the AI resolver transforms them into match/no_match decisions with `tier="ai"`.

**Example:**
```python
# In worker/orchestrator.py (already async)
from event_dedup.ai_matching.resolver import resolve_ambiguous_pairs

async def process_new_file(...):
    # Step 1-2: Ingest, load events (existing)

    # Step 3: Run deterministic matching (existing, sync)
    match_result = score_candidate_pairs(events, config)

    # Step 3.5: NEW - Resolve ambiguous pairs via AI
    if config.ai and config.ai.enabled:
        match_result = await resolve_ambiguous_pairs(
            match_result, events, config.ai, session_factory
        )

    # Step 4: Cluster (existing) -- now has fewer ambiguous decisions
    cluster_result = cluster_matches(match_result.decisions, ...)

    # Step 5: Synthesize + persist (existing)
```

### Pattern 2: Content-Hash Cache with Database Persistence

**What:** Before calling Gemini, compute a deterministic hash from the two events' matching-relevant fields. Check the `ai_match_cache` table. On hit, return cached result. On miss, call API and store result.

**When to use:** Every AI evaluation attempt.

**Example:**
```python
import hashlib
import json

def compute_pair_hash(event_a: dict, event_b: dict) -> str:
    """Deterministic hash of event pair content for cache lookup.

    Uses canonical ordering (id_a < id_b) and only matching-relevant fields
    so that the same real-world event pair always produces the same hash,
    regardless of processing order.
    """
    # Canonical ordering
    if event_a["id"] > event_b["id"]:
        event_a, event_b = event_b, event_a

    # Extract matching-relevant fields only
    def extract_fields(e: dict) -> dict:
        return {
            "title": e.get("title", ""),
            "description": e.get("description", ""),
            "short_description": e.get("short_description", ""),
            "location_city": e.get("location_city", ""),
            "location_name": e.get("location_name", ""),
            "dates": sorted(str(d) for d in (e.get("dates") or [])),
            "categories": sorted(e.get("categories") or []),
        }

    content = json.dumps(
        [extract_fields(event_a), extract_fields(event_b)],
        sort_keys=True, ensure_ascii=False
    )
    return hashlib.sha256(content.encode()).hexdigest()
```

### Pattern 3: Structured Prompt for Event Comparison

**What:** Format two events side-by-side with all relevant fields, ask the model for a structured judgment.

**Example:**
```python
SYSTEM_PROMPT = """You are an expert event deduplication system analyzing German regional events.

Your task: determine whether two event records describe the SAME real-world event
(same gathering, same place, same time) or DIFFERENT events.

Key considerations:
- German compound words and regional dialects may describe the same thing differently
- Source types differ: "artikel" (newspaper articles) have journalistic headlines,
  "terminliste" (event listings) have formal event names
- Same event may have slightly different dates if one source lists a multi-day range
- Location names may vary (abbreviations, spelling differences)
- Description length/style varies by source -- focus on factual overlap, not style

Respond with ONLY a JSON object matching the required schema."""

def format_event_pair(event_a: dict, event_b: dict, signals: SignalScores) -> str:
    """Format two events for AI comparison."""
    return f"""Compare these two events:

## Event A (ID: {event_a['id']}, Source: {event_a['source_code']}, Type: {event_a['source_type']})
Title: {event_a.get('title', 'N/A')}
Description: {(event_a.get('description') or event_a.get('short_description') or 'N/A')[:500]}
Location: {event_a.get('location_name', '')}, {event_a.get('location_city', '')}
Dates: {_format_dates(event_a.get('dates', []))}
Categories: {', '.join(event_a.get('categories') or [])}

## Event B (ID: {event_b['id']}, Source: {event_b['source_code']}, Type: {event_b['source_type']})
Title: {event_b.get('title', 'N/A')}
Description: {(event_b.get('description') or event_b.get('short_description') or 'N/A')[:500]}
Location: {event_b.get('location_name', '')}, {event_b.get('location_city', '')}
Dates: {_format_dates(event_b.get('dates', []))}
Categories: {', '.join(event_b.get('categories') or [])}

## Deterministic Scoring Context
Combined score: {signals.date + signals.geo + signals.title + signals.description:.2f}
- Date similarity: {signals.date:.2f}
- Geo proximity: {signals.geo:.2f}
- Title similarity: {signals.title:.2f}
- Description similarity: {signals.description:.2f}

Are these the SAME real-world event or DIFFERENT events?"""
```

### Pattern 4: Async Concurrent Resolution with Semaphore

**What:** Process multiple ambiguous pairs concurrently with rate limiting via asyncio.Semaphore.

**Example:**
```python
import asyncio
from google import genai

async def resolve_ambiguous_pairs(
    match_result: MatchResult,
    events: list[dict],
    ai_config: AIMatchingConfig,
    session_factory,
) -> MatchResult:
    """Resolve ambiguous pairs via Gemini Flash."""
    events_by_id = {e["id"]: e for e in events}
    ambiguous = [d for d in match_result.decisions if d.decision == "ambiguous"]

    if not ambiguous:
        return match_result

    client = genai.Client(api_key=ai_config.api_key)
    semaphore = asyncio.Semaphore(ai_config.max_concurrent_requests)  # e.g., 5

    async def resolve_one(decision: MatchDecisionRecord) -> MatchDecisionRecord:
        async with semaphore:
            # Check cache first
            pair_hash = compute_pair_hash(
                events_by_id[decision.event_id_a],
                events_by_id[decision.event_id_b],
            )
            cached = await lookup_cache(session_factory, pair_hash)
            if cached:
                return _apply_cached_result(decision, cached)

            # Call Gemini
            result = await call_gemini(client, decision, events_by_id, ai_config)

            # Store in cache
            await store_cache(session_factory, pair_hash, result)

            return _apply_ai_result(decision, result)

    resolved = await asyncio.gather(
        *[resolve_one(d) for d in ambiguous],
        return_exceptions=True,
    )

    # Build updated decisions list
    ambiguous_ids = {(d.event_id_a, d.event_id_b) for d in ambiguous}
    updated_decisions = [d for d in match_result.decisions if (d.event_id_a, d.event_id_b) not in ambiguous_ids]

    for original, result in zip(ambiguous, resolved):
        if isinstance(result, Exception):
            # Fallback: keep as ambiguous
            updated_decisions.append(original)
        else:
            updated_decisions.append(result)

    # Recount
    return MatchResult(
        decisions=updated_decisions,
        pair_stats=match_result.pair_stats,
        match_count=sum(1 for d in updated_decisions if d.decision == "match"),
        ambiguous_count=sum(1 for d in updated_decisions if d.decision == "ambiguous"),
        no_match_count=sum(1 for d in updated_decisions if d.decision == "no_match"),
    )
```

### Anti-Patterns to Avoid
- **Making the pure pipeline async:** The matching pipeline is intentionally pure/sync for testability. Do NOT make `score_candidate_pairs()` or `run_full_pipeline()` async. The AI resolution is a separate async step that runs between scoring and clustering.
- **Sending all pairs to AI:** Only ambiguous pairs go to AI. Match and no_match decisions from deterministic scoring are final.
- **Batching multiple pairs in one prompt:** Each pair should be its own API call. Combining multiple pairs in one prompt increases complexity, reduces reliability, and makes caching ineffective (different batch compositions).
- **Skipping structured output:** Always use `response_schema` with Pydantic models. Free-text responses require fragile parsing.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTTP retries | Custom retry loop | google-genai built-in retry (up to 4 retries, exponential backoff, handles 429/5xx) | Built into SDK; configurable via client init |
| Rate limiting | Token bucket / leaky bucket | asyncio.Semaphore + SDK retries | Semaphore limits concurrency; SDK handles 429 backoff |
| JSON response parsing | Regex/string parsing of AI output | Pydantic `response_schema` + `model_validate_json()` | Gemini constrains output to match schema; Pydantic validates |
| Token counting | Manual estimation | `response.usage_metadata.prompt_token_count` + `candidates_token_count` | Exact counts returned with every response |

**Key insight:** The google-genai SDK handles most of the complexity (retries, structured output, token counting). The implementation work is primarily in prompt engineering, caching, and pipeline integration.

## Common Pitfalls

### Pitfall 1: Ignoring Cache Key Stability
**What goes wrong:** Cache keys computed from different field orderings or formatting produce different hashes for the same event pair, causing cache misses and redundant API calls.
**Why it happens:** Dict ordering, date formatting inconsistencies, or forgetting canonical ordering (id_a < id_b).
**How to avoid:** Always sort events by ID before hashing. Extract only matching-relevant fields. Use `json.dumps(sort_keys=True)` for deterministic serialization.
**Warning signs:** Cache hit rate near 0% during reprocessing of unchanged data.

### Pitfall 2: Not Handling AI Failures Gracefully
**What goes wrong:** API errors (rate limits, model unavailable, invalid response) crash the entire pipeline.
**Why it happens:** No fallback behavior defined for AI tier failures.
**How to avoid:** On any AI error, keep the decision as `"ambiguous"` with `tier="deterministic"`. Log the error. The system works without AI -- it just has lower accuracy on edge cases.
**Warning signs:** Pipeline crashes when Gemini API has intermittent issues.

### Pitfall 3: Unbounded Concurrent Requests
**What goes wrong:** Sending all ambiguous pairs simultaneously exceeds rate limits (10 RPM on free tier).
**Why it happens:** Using `asyncio.gather()` without a semaphore.
**How to avoid:** Use `asyncio.Semaphore(max_concurrent)` to limit in-flight requests. Start with 5 concurrent, tune based on rate limit tier.
**Warning signs:** Frequent 429 errors; exponential backoff causing long delays.

### Pitfall 4: Prompt Doesn't Mention German Language Context
**What goes wrong:** Model treats German compound words, umlauts, and dialect terms as completely different, resulting in many false "different" judgments.
**Why it happens:** Prompt doesn't contextualize the domain as German regional events.
**How to avoid:** System prompt explicitly mentions German language, compound words, regional dialects, and source type differences (artikel vs terminliste).
**Warning signs:** AI disagrees with obvious matches that have German-specific name variations.

### Pitfall 5: Including Non-Deterministic Fields in Cache Key
**What goes wrong:** Fields like `created_at` or `batch_index` in the cache hash make every reprocessing cycle miss the cache.
**Why it happens:** Hashing the entire event dict instead of selecting only content fields.
**How to avoid:** Hash only title, description, short_description, location_city, location_name, dates, and categories -- the fields that determine whether events are the same.
**Warning signs:** Cache size grows linearly with reprocessing cycles, never hitting.

## Code Examples

### Gemini Client with Structured Output
```python
# Source: Google Gen AI SDK docs (https://googleapis.github.io/python-genai/)
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

class AIMatchResult(BaseModel):
    """Structured response from Gemini Flash for event pair comparison."""
    decision: str = Field(
        description="Whether the two events are the same real-world event. Must be 'same' or 'different'."
    )
    confidence: float = Field(
        description="Confidence in the decision, from 0.0 (no confidence) to 1.0 (certain).",
        ge=0.0, le=1.0,
    )
    reasoning: str = Field(
        description="Brief explanation of why the events are considered same or different, noting key matching or differentiating factors."
    )

async def call_gemini(
    client: genai.Client,
    event_a: dict,
    event_b: dict,
    signals: SignalScores,
    ai_config: AIMatchingConfig,
) -> AIMatchResult:
    """Call Gemini Flash for a single event pair comparison."""
    prompt = format_event_pair(event_a, event_b, signals)

    response = await client.aio.models.generate_content(
        model=ai_config.model,  # "gemini-2.5-flash"
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            response_mime_type="application/json",
            response_schema=AIMatchResult,
            temperature=0.1,  # Low temperature for consistent judgments
            max_output_tokens=300,  # Reasoning doesn't need to be long
        ),
    )

    result = AIMatchResult.model_validate_json(response.text)

    # Track token usage
    usage = response.usage_metadata
    return result, usage.prompt_token_count, usage.candidates_token_count
```

### AI Matching Configuration
```python
# Added to matching/config.py
class AIMatchingConfig(BaseModel):
    """Configuration for AI-assisted matching tier."""
    enabled: bool = False
    api_key: str = ""  # Or use GEMINI_API_KEY env var
    model: str = "gemini-2.5-flash"
    temperature: float = 0.1
    max_output_tokens: int = 300
    max_concurrent_requests: int = 5
    cache_enabled: bool = True

    # Cost monitoring
    cost_per_1m_input_tokens: float = 0.30
    cost_per_1m_output_tokens: float = 2.50
```

### Database Models for Cache and Usage Tracking
```python
# models/ai_match_cache.py
class AIMatchCache(Base):
    __tablename__ = "ai_match_cache"

    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True, autoincrement=True)
    pair_hash: Mapped[str] = mapped_column(sa.String(64), unique=True, index=True)
    event_id_a: Mapped[str] = mapped_column(sa.String)
    event_id_b: Mapped[str] = mapped_column(sa.String)
    decision: Mapped[str] = mapped_column(sa.String)  # "same" or "different"
    confidence: Mapped[float] = mapped_column(sa.Float)
    reasoning: Mapped[str] = mapped_column(sa.Text)
    model: Mapped[str] = mapped_column(sa.String)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime, server_default=sa.text("CURRENT_TIMESTAMP")
    )

# models/ai_usage_log.py
class AIUsageLog(Base):
    __tablename__ = "ai_usage_log"

    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True, autoincrement=True)
    batch_id: Mapped[str] = mapped_column(sa.String)  # Groups requests from one pipeline run
    event_id_a: Mapped[str] = mapped_column(sa.String)
    event_id_b: Mapped[str] = mapped_column(sa.String)
    model: Mapped[str] = mapped_column(sa.String)
    prompt_tokens: Mapped[int] = mapped_column(sa.Integer)
    completion_tokens: Mapped[int] = mapped_column(sa.Integer)
    total_tokens: Mapped[int] = mapped_column(sa.Integer)
    estimated_cost_usd: Mapped[float] = mapped_column(sa.Float)
    cached: Mapped[bool] = mapped_column(sa.Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime, server_default=sa.text("CURRENT_TIMESTAMP")
    )
```

### Cost Calculation
```python
def estimate_cost(
    prompt_tokens: int,
    completion_tokens: int,
    config: AIMatchingConfig,
) -> float:
    """Estimate cost in USD for a single API call."""
    input_cost = (prompt_tokens / 1_000_000) * config.cost_per_1m_input_tokens
    output_cost = (completion_tokens / 1_000_000) * config.cost_per_1m_output_tokens
    return input_cost + output_cost

# For the event dedup use case (~2000 events/week, ~765 in sample):
# Estimated ambiguous pairs: ~50-150 per batch (depends on threshold tuning)
# Estimated tokens per pair: ~800 input (two events + prompt) + ~100 output
# Cost per pair: (800/1M * $0.30) + (100/1M * $2.50) = $0.00049
# Cost per batch (100 pairs): ~$0.05
# Cost per month (4 batches): ~$0.20
# Conclusion: Extremely cost-effective at this volume
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `google-generativeai` SDK | `google-genai` SDK | Nov 2025 (deprecated) | Must use `google-genai`; old SDK no longer maintained |
| `genai.GenerativeModel()` | `genai.Client().models.generate_content()` | Nov 2025 | Client-based pattern; async via `client.aio` |
| Free-text JSON responses | `response_schema` with Pydantic | 2025 | Native structured output; no parsing needed |
| `gemini-1.5-flash` | `gemini-2.5-flash` | Jun 2025 (2.5 GA) | Better reasoning, same price tier, structured output support |

**Deprecated/outdated:**
- `google-generativeai` package: Support ended November 30, 2025. Do NOT use.
- `gemini-2.0-flash`: Still works but replaced by 2.5 Flash with better capabilities at same price.
- `genai.configure(api_key=...)` pattern: Old SDK pattern. New SDK uses `Client(api_key=...)`.

## Open Questions

1. **Optimal concurrency limit for free tier**
   - What we know: Free tier is 10 RPM / 250 RPD. Paid Tier 1 is significantly higher.
   - What's unclear: Exact RPM/TPM for Tier 1 (Google no longer publishes exact numbers; visible in AI Studio dashboard).
   - Recommendation: Start with `max_concurrent_requests=5` on free tier. If the project moves to paid tier, increase to 10-20. The volume (~100 ambiguous pairs/batch) fits comfortably within free tier limits (250 RPD).

2. **Gemini 2.5 Flash vs Flash-Lite for this task**
   - What we know: Flash-Lite is 3x cheaper ($0.10/$0.40 vs $0.30/$2.50 per 1M tokens). Flash has better reasoning.
   - What's unclear: Whether Flash-Lite's reasoning capability is sufficient for German event deduplication judgment.
   - Recommendation: Start with Flash (more capable). The cost difference at this volume is negligible (~$0.04/month vs ~$0.01/month). If quality issues arise, this is already the best option. If cost becomes an issue at higher volume, benchmark Flash-Lite on the ground truth dataset.

3. **Cache invalidation strategy**
   - What we know: Events are static once ingested (immutable source events). Cache entries remain valid indefinitely for the same event pair.
   - What's unclear: Whether model upgrades (e.g., Flash update) should invalidate cache.
   - Recommendation: Store the model ID in the cache. On model change, either invalidate (delete) old cache entries or accept potentially stale results. At this volume, re-evaluating all cached pairs on model change is trivial cost-wise.

4. **How "ambiguous" AI decisions should be handled**
   - What we know: AI returns decision + confidence. Some pairs may still be uncertain even for AI.
   - What's unclear: Should low-confidence AI decisions still override the "ambiguous" deterministic label?
   - Recommendation: Map AI `decision="same"` to `decision="match"` and `decision="different"` to `decision="no_match"` only when AI confidence >= 0.6. Below that, keep as `decision="ambiguous"` (will be surfaced in review queue in Phase 6).

## Sources

### Primary (HIGH confidence)
- [Google Gen AI SDK documentation](https://googleapis.github.io/python-genai/) - Client API, async pattern, structured output, token counting
- [Gemini API structured output docs](https://ai.google.dev/gemini-api/docs/structured-output) - Pydantic schema support, response_mime_type
- [Gemini API pricing](https://ai.google.dev/gemini-api/docs/pricing) - Token pricing for all Flash variants
- [Gemini API models](https://ai.google.dev/gemini-api/docs/models) - Model IDs, capabilities
- [Gemini API rate limits](https://ai.google.dev/gemini-api/docs/rate-limits) - Tier structure, batch limits
- [google-genai PyPI](https://pypi.org/project/google-genai/) - Version 1.65.0, Python >=3.10
- [googleapis/python-genai GitHub](https://github.com/googleapis/python-genai) - Installation, async examples, client patterns

### Secondary (MEDIUM confidence)
- [google-generativeai deprecated repo](https://github.com/google-gemini/deprecated-generative-ai-python) - Confirms deprecation Nov 2025
- [LLM-as-Judge deduplication techniques](https://forem.julialang.org/svilupp/duplicate-no-more-pt-2-mastering-llm-as-a-judge-scoring-51ff) - Prompt engineering patterns for record linkage
- [Gemini by Example: Rate limits and retries](https://geminibyexample.com/029-rate-limits-retries/) - RetryConfig, error handling patterns

### Tertiary (LOW confidence)
- Rate limit exact numbers (10 RPM / 250 RPD for free tier) - sourced from third-party aggregator sites; Google's official page redirects to AI Studio dashboard for exact limits

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Official Google SDK docs, PyPI, GitHub repo all confirm `google-genai` as the production SDK
- Architecture: HIGH - Integration points are clear from existing codebase analysis; async worker already exists
- Pitfalls: HIGH - Well-documented patterns from SDK docs and community; LLM-as-judge patterns established
- Pricing: HIGH - Official Google pricing page
- Rate limits: MEDIUM - Google no longer publishes exact RPM/TPM numbers publicly; third-party sources report ~10 RPM free tier

**Research date:** 2026-02-28
**Valid until:** 2026-03-30 (stable SDK; model IDs may evolve)
