"""Tests for synonym loading and application."""

from pathlib import Path

import pytest

from event_dedup.preprocessing.synonyms import apply_synonyms, load_synonym_map

# Path to the real synonyms.yaml config
SYNONYMS_PATH = Path(__file__).resolve().parents[1] / "src" / "event_dedup" / "config" / "synonyms.yaml"


@pytest.fixture()
def synonym_map() -> dict[str, str]:
    """Load the real synonym map for tests."""
    return load_synonym_map(SYNONYMS_PATH)


class TestLoadSynonymMap:
    """Tests for load_synonym_map."""

    def test_loads_valid_yaml(self, synonym_map: dict[str, str]) -> None:
        """Loading from synonyms.yaml returns a non-empty mapping."""
        assert len(synonym_map) > 0

    def test_canonical_not_in_map(self, synonym_map: dict[str, str]) -> None:
        """Canonical forms are NOT keys in the map (only variants are)."""
        assert "fastnacht" not in synonym_map
        assert "hemdglunker" not in synonym_map

    def test_variants_sorted_longest_first(self, synonym_map: dict[str, str]) -> None:
        """Keys are sorted by length descending."""
        keys = list(synonym_map.keys())
        for i in range(len(keys) - 1):
            assert len(keys[i]) >= len(keys[i + 1])

    def test_missing_file_returns_empty(self, tmp_path: Path) -> None:
        """Non-existent file returns empty dict."""
        result = load_synonym_map(tmp_path / "nonexistent.yaml")
        assert result == {}

    def test_empty_file_returns_empty(self, tmp_path: Path) -> None:
        """Empty YAML file returns empty dict."""
        empty_file = tmp_path / "empty.yaml"
        empty_file.write_text("")
        result = load_synonym_map(empty_file)
        assert result == {}

    def test_all_fastnacht_variants_present(self, synonym_map: dict[str, str]) -> None:
        """All carnival term variants map to fastnacht."""
        for variant in ["fasnet", "fasnacht", "fasching", "karneval", "fasent", "fasend", "fasnets"]:
            assert synonym_map[variant] == "fastnacht"

    def test_all_hemdglunker_variants_present(self, synonym_map: dict[str, str]) -> None:
        """All hemdglunker variants map to hemdglunker."""
        for variant in ["hemdklunker", "hemdglunki", "hendglunki"]:
            assert synonym_map[variant] == "hemdglunker"


class TestApplySynonyms:
    """Tests for apply_synonyms."""

    def test_fasnet_replacement(self, synonym_map: dict[str, str]) -> None:
        assert apply_synonyms("fasnet", synonym_map) == "fastnacht"

    def test_fasching_replacement(self, synonym_map: dict[str, str]) -> None:
        assert apply_synonyms("fasching", synonym_map) == "fastnacht"

    def test_karneval_replacement(self, synonym_map: dict[str, str]) -> None:
        assert apply_synonyms("karneval", synonym_map) == "fastnacht"

    def test_hemdklunker_replacement(self, synonym_map: dict[str, str]) -> None:
        assert apply_synonyms("hemdklunker", synonym_map) == "hemdglunker"

    def test_compound_word_fasnetsumzug(self, synonym_map: dict[str, str]) -> None:
        """Compound: fasnetsumzug -> fastnachtumzug (fasnets matches first)."""
        assert apply_synonyms("fasnetsumzug", synonym_map) == "fastnachtumzug"

    def test_hyphenated_form(self, synonym_map: dict[str, str]) -> None:
        assert apply_synonyms("fasnet-eroeffnung", synonym_map) == "fastnacht-eroeffnung"

    def test_no_synonyms_unchanged(self, synonym_map: dict[str, str]) -> None:
        assert apply_synonyms("konzert im park", synonym_map) == "konzert im park"

    def test_empty_map_unchanged(self) -> None:
        assert apply_synonyms("fasnet", {}) == "fasnet"

    def test_multiple_replacements(self, synonym_map: dict[str, str]) -> None:
        result = apply_synonyms("fasnet hemdklunker", synonym_map)
        assert result == "fastnacht hemdglunker"

    def test_canonical_form_not_replaced(self, synonym_map: dict[str, str]) -> None:
        """Canonical form in text is NOT replaced."""
        assert apply_synonyms("fastnacht", synonym_map) == "fastnacht"
        assert apply_synonyms("hemdglunker", synonym_map) == "hemdglunker"
