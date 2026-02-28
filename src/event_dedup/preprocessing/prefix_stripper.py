"""Configurable prefix stripping for event titles.

Strips source-specific prefixes (like "Nordwiler Narrenfahrplan - ...")
from event titles before normalization, so that matching focuses on
the actual event name rather than the source label.
"""

from pathlib import Path

import yaml
from pydantic import BaseModel

from event_dedup.preprocessing.normalizer import normalize_text


class PrefixConfig(BaseModel):
    """Configuration for prefix stripping patterns."""

    dash_prefixes: list[str] = []
    colon_prefixes: list[str] = []
    generic_prefixes: list[str] = []


def load_prefix_config(config_path: Path) -> PrefixConfig:
    """Load prefix configuration from a YAML file.

    Args:
        config_path: Path to the prefixes.yaml file.

    Returns:
        PrefixConfig with loaded prefix lists.
    """
    with open(config_path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    if not raw:
        return PrefixConfig()

    return PrefixConfig.model_validate(raw)


# Dash-like separators to check: regular dash, double dash, en-dash, em-dash
_DASH_SEPARATORS = (" - ", " -- ", " \u2013 ", " \u2014 ")


def strip_prefixes(title: str, config: PrefixConfig) -> str:
    """Strip the first matching prefix from a title.

    Matching is case-insensitive and checks against original-form prefixes.
    Only the FIRST matching prefix is stripped (no recursive stripping).

    Order of checking: dash_prefixes, colon_prefixes, generic_prefixes.

    Args:
        title: Original event title.
        config: Prefix configuration with lists of prefixes.

    Returns:
        Title with prefix stripped, or original title if no match.
    """
    title_lower = title.lower()

    # Check dash prefixes
    for prefix in config.dash_prefixes:
        prefix_lower = prefix.lower()
        for sep in _DASH_SEPARATORS:
            pattern = prefix_lower + sep
            if title_lower.startswith(pattern):
                return title[len(pattern):].strip()

    # Check colon prefixes
    for prefix in config.colon_prefixes:
        prefix_lower = prefix.lower()
        pattern = prefix_lower + ": "
        if title_lower.startswith(pattern):
            return title[len(pattern):].strip()

    # Check generic prefixes (same dash logic)
    for prefix in config.generic_prefixes:
        prefix_lower = prefix.lower()
        for sep in _DASH_SEPARATORS:
            pattern = prefix_lower + sep
            if title_lower.startswith(pattern):
                return title[len(pattern):].strip()

    return title


def normalize_title(
    title: str,
    prefix_config: PrefixConfig,
    synonym_map: dict[str, str] | None = None,
) -> str:
    """Strip prefixes from a title and then normalize the result.

    This is the standard pipeline for title normalization:
    1. Strip prefixes from the ORIGINAL title (case-insensitive)
    2. Normalize the stripped result (lowercase, umlaut expansion, synonyms, etc.)

    Args:
        title: Original event title.
        prefix_config: Prefix configuration.
        synonym_map: Optional synonym map for dialect normalization.

    Returns:
        Normalized title with prefix stripped.
    """
    stripped = strip_prefixes(title, prefix_config)
    return normalize_text(stripped, synonym_map=synonym_map)
