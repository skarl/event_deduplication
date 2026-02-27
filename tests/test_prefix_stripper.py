"""Tests for the prefix stripping module."""

from pathlib import Path

from event_dedup.preprocessing.prefix_stripper import (
    PrefixConfig,
    load_prefix_config,
    normalize_title,
    strip_prefixes,
)

# Path to the actual prefixes.yaml config
PREFIXES_PATH = Path(__file__).resolve().parents[1] / "src" / "event_dedup" / "config" / "prefixes.yaml"


def _config() -> PrefixConfig:
    """Load the actual prefix config for tests."""
    return load_prefix_config(PREFIXES_PATH)


def test_strip_dash_prefix():
    """Dash prefix is stripped, returning the event name."""
    config = _config()
    result = strip_prefixes("Nordwiler Narrenfahrplan - Fasnetumzug", config)
    assert result == "Fasnetumzug"


def test_strip_colon_prefix():
    """Colon prefix is stripped, returning the event name."""
    config = _config()
    result = strip_prefixes("Vortrag: Landschaftsmalerei im Fokus", config)
    assert result == "Landschaftsmalerei im Fokus"


def test_strip_generic_prefix():
    """Generic prefix with dash separator is stripped."""
    config = _config()
    result = strip_prefixes("Tag der offenen T\u00fcr - Kindergarten St. Franziskus", config)
    assert result == "Kindergarten St. Franziskus"


def test_no_prefix_match():
    """Title without a matching prefix is returned unchanged."""
    config = _config()
    result = strip_prefixes("Primel-Aktion Emmendingen", config)
    assert result == "Primel-Aktion Emmendingen"


def test_case_insensitive():
    """Prefix matching is case-insensitive."""
    config = _config()
    result = strip_prefixes("nordwiler narrenfahrplan - Test", config)
    assert result == "Test"


def test_en_dash_separator():
    """En-dash separator is recognized."""
    config = _config()
    # \u2013 is en-dash
    result = strip_prefixes("Kommunales Kino \u2013 Der Salzpfad", config)
    assert result == "Der Salzpfad"


def test_em_dash_separator():
    """Em-dash separator is recognized."""
    config = _config()
    # \u2014 is em-dash
    result = strip_prefixes("Kommunales Kino \u2014 Der Salzpfad", config)
    assert result == "Der Salzpfad"


def test_double_dash_separator():
    """Double dash separator is recognized."""
    config = _config()
    result = strip_prefixes("Kommunales Kino -- Der Salzpfad", config)
    assert result == "Der Salzpfad"


def test_no_recursive_strip():
    """Only the first matching prefix is stripped, not recursively."""
    # Create a config where the result of stripping could match another prefix
    config = PrefixConfig(
        dash_prefixes=["A", "B"],
        colon_prefixes=[],
        generic_prefixes=[],
    )
    result = strip_prefixes("A - B - actual title", config)
    # Only "A - " is stripped, leaving "B - actual title"
    assert result == "B - actual title"


def test_normalize_title_strips_and_normalizes():
    """normalize_title strips prefix then normalizes the result."""
    config = _config()
    result = normalize_title("Nordwiler Narrenfahrplan - Kita-Gizig-Umzug", config)
    # Prefix stripped, then lowercased
    assert result == "kita-gizig-umzug"
    assert "nordwiler" not in result


def test_normalize_title_no_prefix():
    """normalize_title just normalizes when no prefix matches."""
    config = _config()
    result = normalize_title("Primel-Aktion Emmendingen", config)
    assert result == "primel-aktion emmendingen"


def test_load_prefix_config():
    """Prefix config loads with all sections populated."""
    config = _config()
    assert len(config.dash_prefixes) > 0
    assert len(config.colon_prefixes) > 0
    assert len(config.generic_prefixes) > 0
    assert "Nordwiler Narrenfahrplan" in config.dash_prefixes
    assert "Vortrag" in config.colon_prefixes
