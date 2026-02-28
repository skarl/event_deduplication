"""Tests for the text normalization pipeline."""

from pathlib import Path

import pytest

from event_dedup.preprocessing.normalizer import load_city_aliases, normalize_city, normalize_text
from event_dedup.preprocessing.synonyms import load_synonym_map

# Path to the city_aliases.yaml config
CITY_ALIASES_PATH = Path(__file__).resolve().parents[1] / "src" / "event_dedup" / "config" / "city_aliases.yaml"
SYNONYMS_PATH = Path(__file__).resolve().parents[1] / "src" / "event_dedup" / "config" / "synonyms.yaml"


@pytest.fixture()
def synonym_map() -> dict[str, str]:
    """Load the real synonym map for tests."""
    return load_synonym_map(SYNONYMS_PATH)


def test_normalize_lowercase():
    """Uppercase text is lowercased."""
    assert normalize_text("CHECKER TOBI") == "checker tobi"


def test_normalize_umlauts_composed():
    """Composed umlauts (single codepoints) are expanded to digraphs."""
    # \u00e4=ä, \u00f6=ö, \u00fc=ü
    assert normalize_text("B\u00fcrgerh\u00e4user") == "buergerhaeuser"
    assert normalize_text("sch\u00f6n") == "schoen"


def test_normalize_umlauts_decomposed():
    """Decomposed umlauts (base + combining diaeresis) are expanded."""
    # a + combining diaeresis = ä (decomposed)
    text = "a\u0308pfel"  # decomposed ä
    result = normalize_text(text)
    assert result == "aepfel"


def test_normalize_umlauts_eszett():
    """Eszett (sharp s) is expanded to ss."""
    assert normalize_text("Stra\u00dfe") == "strasse"


def test_normalize_whitespace():
    """Multiple spaces, tabs, and newlines collapse to single space."""
    assert normalize_text("  too   many  spaces  ") == "too many spaces"
    assert normalize_text("tabs\there") == "tabs here"
    assert normalize_text("new\nline") == "new line"


def test_normalize_punctuation():
    """Punctuation is stripped except hyphens."""
    assert normalize_text("Hart aber herzlich!") == "hart aber herzlich"
    assert normalize_text('"Quoted text"') == "quoted text"
    assert normalize_text("Question? Answer.") == "question answer"
    assert normalize_text("List: item (one)") == "list item one"


def test_normalize_keep_hyphens():
    """Hyphens are preserved for German compound words."""
    assert normalize_text("SPD-Veranstaltung") == "spd-veranstaltung"
    assert normalize_text("Kita-Gizig-Umzug") == "kita-gizig-umzug"


def test_normalize_empty():
    """None and empty string both return empty string."""
    assert normalize_text(None) == ""
    assert normalize_text("") == ""


def test_normalize_city_with_alias():
    """City that has an alias is resolved to the parent municipality."""
    aliases = load_city_aliases(CITY_ALIASES_PATH)
    assert normalize_city("Waltershofen", aliases) == "freiburg im breisgau"


def test_normalize_city_without_alias():
    """City without an alias is returned normalized."""
    aliases = load_city_aliases(CITY_ALIASES_PATH)
    assert normalize_city("Emmendingen", aliases) == "emmendingen"


def test_normalize_city_case_insensitive():
    """City normalization is case-insensitive."""
    assert normalize_city("WALDKIRCH") == "waldkirch"


def test_normalize_city_empty():
    """None and empty city return empty string."""
    assert normalize_city(None) == ""
    assert normalize_city("") == ""


def test_load_city_aliases():
    """City aliases file loads and normalizes keys and values."""
    aliases = load_city_aliases(CITY_ALIASES_PATH)
    # Keys should be normalized (lowercase, no umlauts)
    assert "nordweil" in aliases
    assert aliases["nordweil"] == "kenzingen"
    assert "waltershofen" in aliases
    assert aliases["waltershofen"] == "freiburg im breisgau"


# ===========================================================================
# Synonym-aware normalization tests
# ===========================================================================


def test_normalize_with_synonyms_fasnet(synonym_map: dict[str, str]):
    """normalize_text with synonym_map replaces fasnet with fastnacht."""
    # "Fasnet-Eröffnung" -> lowercase -> "fasnet-eröffnung" -> umlaut expansion -> "fasnet-eroeffnung"
    # -> synonym -> "fastnacht-eroeffnung"
    result = normalize_text("Fasnet-Er\u00f6ffnung", synonym_map=synonym_map)
    assert "fastnacht" in result
    assert "fasnet" not in result


def test_normalize_with_synonyms_compound(synonym_map: dict[str, str]):
    """normalize_text with synonym_map handles compound word Fasnetsumzug."""
    result = normalize_text("Fasnetsumzug", synonym_map=synonym_map)
    assert "fastnacht" in result


def test_normalize_without_synonyms_unchanged():
    """normalize_text without synonym_map does not replace dialect terms."""
    result = normalize_text("Fasnet")
    assert result == "fasnet"


def test_normalize_city_unaffected():
    """normalize_city still works without synonym_map."""
    assert normalize_city("Waldkirch") == "waldkirch"
