"""Quick integration test for AI matching against real Gemini API.

Usage:
    GEMINI_API_KEY=... .venv/bin/python scripts/test_ai_integration.py
"""
from __future__ import annotations

import asyncio
import os
import sys

# Two realistic ambiguous event pairs from different sources
# Pair 1: Same event described differently (should be "same")
PAIR_SAME = (
    {
        "id": "test-bwb-001",
        "title": "Hemdglunkerumzug mit Schlüsselübergabe",
        "description": (
            "Der traditionelle Hemdglunkerumzug findet am Schmutzigen Donnerstag "
            "in der Emmendinger Innenstadt statt. Nach dem Umzug erfolgt die "
            "symbolische Schlüsselübergabe an die Narren auf dem Marktplatz."
        ),
        "short_description": "Hemdglunkerumzug in Emmendingen",
        "source_code": "bwb",
        "source_type": "artikel",
        "location_name": "Innenstadt",
        "location_city": "Emmendingen",
        "dates": [{"date": "2026-02-12", "start_time": "19:00"}],
        "categories": ["fasnacht"],
    },
    {
        "id": "test-emt-001",
        "title": "Hemdglunkerumzug Emmendingen",
        "description": (
            "Hemdglunkerumzug durch die Emmendinger Innenstadt mit "
            "anschliessender Schlüsselübergabe auf dem Marktplatz."
        ),
        "short_description": "Hemdglunker mit Schlüsselübergabe",
        "source_code": "emt",
        "source_type": "terminliste",
        "location_name": "Marktplatz Emmendingen",
        "location_city": "Emmendingen",
        "dates": [{"date": "2026-02-12", "start_time": "19:00"}],
        "categories": ["fasnacht"],
    },
)

# Pair 2: Different events at same venue (should be "different")
PAIR_DIFFERENT = (
    {
        "id": "test-bwb-002",
        "title": "Rathaussturm durch Kindergärten",
        "description": (
            "Am Schmutzigen Donnerstag stürmen die Kinder der Emmendinger "
            "Kindergärten das Rathaus und fordern den Schlüssel vom Bürgermeister."
        ),
        "short_description": "Kinder stürmen das Rathaus",
        "source_code": "bwb",
        "source_type": "artikel",
        "location_name": "Rathaus",
        "location_city": "Emmendingen",
        "dates": [{"date": "2026-02-12", "start_time": "10:00"}],
        "categories": ["fasnacht", "kinder"],
    },
    {
        "id": "test-emt-002",
        "title": "Kinderhemdglunkerumzug",
        "description": (
            "Der Kinderhemdglunkerumzug zieht durch die Emmendinger Innenstadt. "
            "Treffpunkt ist am Schlossplatz."
        ),
        "short_description": "Kinderhemdglunkerumzug Emmendingen",
        "source_code": "emt",
        "source_type": "terminliste",
        "location_name": "Schlossplatz",
        "location_city": "Emmendingen",
        "dates": [{"date": "2026-02-12", "start_time": "14:00"}],
        "categories": ["fasnacht", "kinder"],
    },
)


async def test_pair(client, event_a, event_b, signals, ai_config, label):
    """Test a single pair and print results."""
    from event_dedup.ai_matching.client import call_gemini

    print(f"\n{'='*60}")
    print(f"TEST: {label}")
    print(f"  Event A: {event_a['title']} ({event_a['source_code']})")
    print(f"  Event B: {event_b['title']} ({event_b['source_code']})")
    print(f"  Signals: date={signals.date:.2f} geo={signals.geo:.2f} "
          f"title={signals.title:.2f} desc={signals.description:.2f}")

    try:
        result, prompt_tok, completion_tok = await call_gemini(
            client, event_a, event_b, signals, ai_config,
        )
        print(f"\n  RESULT:")
        print(f"    Decision:   {result.decision}")
        print(f"    Confidence: {result.confidence}")
        print(f"    Reasoning:  {result.reasoning}")
        print(f"    Tokens:     {prompt_tok} prompt / {completion_tok} completion")
        return result
    except Exception as e:
        print(f"\n  ERROR: {e}")
        return None


async def main():
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        print("ERROR: Set GEMINI_API_KEY environment variable")
        sys.exit(1)

    from event_dedup.ai_matching.client import create_client
    from event_dedup.matching.combiner import SignalScores
    from event_dedup.matching.config import AIMatchingConfig

    ai_config = AIMatchingConfig(
        enabled=True,
        api_key=api_key,
        model="gemini-2.5-flash",
        confidence_threshold=0.6,
    )

    client = create_client(api_key)

    print("AI Matching Integration Test")
    print(f"Model: {ai_config.model}")
    print(f"Confidence threshold: {ai_config.confidence_threshold}")

    # Test 1: Same event (ambiguous signals)
    signals_same = SignalScores(date=0.95, geo=0.90, title=0.55, description=0.45)
    r1 = await test_pair(
        client, *PAIR_SAME, signals_same, ai_config,
        "Same event, different sources (expect: same)"
    )

    # Test 2: Different events (ambiguous signals)
    signals_diff = SignalScores(date=0.70, geo=0.90, title=0.40, description=0.35)
    r2 = await test_pair(
        client, *PAIR_DIFFERENT, signals_diff, ai_config,
        "Different events, same city/day (expect: different)"
    )

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    ok = 0
    total = 2
    if r1 and r1.decision == "same":
        print("  [PASS] Pair 1: correctly identified as SAME")
        ok += 1
    elif r1:
        print(f"  [FAIL] Pair 1: expected 'same', got '{r1.decision}'")
    else:
        print("  [ERROR] Pair 1: API call failed")

    if r2 and r2.decision == "different":
        print("  [PASS] Pair 2: correctly identified as DIFFERENT")
        ok += 1
    elif r2:
        print(f"  [FAIL] Pair 2: expected 'different', got '{r2.decision}'")
    else:
        print("  [ERROR] Pair 2: API call failed")

    print(f"\n  Result: {ok}/{total} passed")


if __name__ == "__main__":
    asyncio.run(main())
