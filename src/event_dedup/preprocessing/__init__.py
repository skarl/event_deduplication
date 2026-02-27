"""Preprocessing pipeline for event text normalization and blocking key generation."""

from event_dedup.preprocessing.blocking import generate_blocking_keys, geo_grid_key, is_valid_geo
from event_dedup.preprocessing.normalizer import load_city_aliases, normalize_city, normalize_text
from event_dedup.preprocessing.prefix_stripper import (
    PrefixConfig,
    load_prefix_config,
    normalize_title,
    strip_prefixes,
)

__all__ = [
    "generate_blocking_keys",
    "geo_grid_key",
    "is_valid_geo",
    "load_city_aliases",
    "load_prefix_config",
    "normalize_city",
    "normalize_text",
    "normalize_title",
    "PrefixConfig",
    "strip_prefixes",
]
