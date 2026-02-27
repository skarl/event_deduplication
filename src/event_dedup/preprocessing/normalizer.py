"""Text normalization pipeline for event deduplication.

Handles German-specific text normalization including umlaut expansion,
whitespace normalization, punctuation stripping, and city alias resolution.
"""

import re
import unicodedata
from pathlib import Path

import yaml


def normalize_text(text: str | None) -> str:
    """Normalize text for matching purposes.

    Steps:
        1. Return empty string for None/empty input
        2. Lowercase the text
        3. Expand German umlauts (both composed and decomposed forms)
        4. Normalize whitespace (collapse to single space, strip)
        5. Strip punctuation (keep hyphens for German compound words)
        6. Final strip

    Args:
        text: Input text to normalize.

    Returns:
        Normalized text string.
    """
    if not text:
        return ""

    result = text.lower()

    # Expand German umlauts -- handle composed forms (single codepoints)
    # Must be done BEFORE NFC normalization to catch both forms
    # First, normalize Unicode to NFC to merge any decomposed forms into composed
    result = unicodedata.normalize("NFC", result)

    # Now expand composed German umlauts
    result = result.replace("\u00e4", "ae")  # ä
    result = result.replace("\u00f6", "oe")  # ö
    result = result.replace("\u00fc", "ue")  # ü
    result = result.replace("\u00df", "ss")  # ß
    # Uppercase variants (already lowercased, but handle edge case of
    # characters that didn't lowercase properly)
    result = result.replace("\u00c4", "ae")  # Ä
    result = result.replace("\u00d6", "oe")  # Ö
    result = result.replace("\u00dc", "ue")  # Ü

    # Normalize whitespace: collapse multiple spaces/tabs/newlines to single space
    result = re.sub(r"\s+", " ", result).strip()

    # Strip punctuation but KEEP hyphens (important for German compound words)
    result = re.sub(r"[\"'!?,.:;()\[\]{}]", "", result)

    # Final strip (removing punctuation may leave trailing spaces)
    return result.strip()


def normalize_city(city: str | None, aliases: dict[str, str] | None = None) -> str:
    """Normalize a city name, applying alias resolution if configured.

    Args:
        city: City name to normalize.
        aliases: Optional dict mapping normalized district names to normalized
                 parent municipality names.

    Returns:
        Normalized city name (possibly resolved via alias).
    """
    if not city:
        return ""

    normalized = normalize_text(city)

    if aliases and normalized in aliases:
        return aliases[normalized]

    return normalized


def load_city_aliases(config_path: Path) -> dict[str, str]:
    """Load city alias mappings from a YAML config file.

    All keys and values are normalized at load time so lookups work
    with normalized city names.

    Args:
        config_path: Path to the city_aliases.yaml file.

    Returns:
        Dict mapping normalized district names to normalized municipality names.
    """
    with open(config_path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    if not raw:
        return {}

    return {normalize_text(k): normalize_text(v) for k, v in raw.items()}
