"""Synonym loading and application for German dialect event terms.

Loads synonym groups from a YAML config and applies them during text
normalization so that dialect variants (e.g. Fasnet, Fasnacht, Fasching)
are mapped to a single canonical form before fuzzy matching.
"""

from __future__ import annotations

from pathlib import Path

import yaml


def load_synonym_map(config_path: Path) -> dict[str, str]:
    """Load synonym groups from YAML and build a flat variant -> canonical map.

    The returned dict has keys sorted by length descending (longest first)
    so that compound words are handled correctly during replacement.

    Args:
        config_path: Path to the synonyms.yaml file.

    Returns:
        Dict mapping variant strings to canonical forms, sorted longest-first.
        Returns empty dict if the file doesn't exist or is empty.
    """
    if not config_path.exists():
        return {}

    with open(config_path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    if not raw or "synonym_groups" not in raw:
        return {}

    flat: dict[str, str] = {}
    for canonical, variants in raw["synonym_groups"].items():
        if not variants:
            continue
        for variant in variants:
            flat[variant] = canonical

    # Sort by key length descending so longest matches first
    return dict(sorted(flat.items(), key=lambda x: -len(x[0])))


def apply_synonyms(text: str, synonym_map: dict[str, str]) -> str:
    """Replace dialect variants with canonical forms in text.

    Iterates over the synonym map (already sorted longest-first by
    ``load_synonym_map``) and performs substring replacement.

    Args:
        text: Input text (should already be lowercased and umlaut-expanded).
        synonym_map: Flat variant -> canonical mapping.

    Returns:
        Text with all matching variants replaced by their canonical form.
    """
    if not synonym_map:
        return text

    for variant, canonical in synonym_map.items():
        text = text.replace(variant, canonical)

    return text
