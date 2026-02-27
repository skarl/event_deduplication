"""Tests for blocking key generation."""

from datetime import date

from event_dedup.preprocessing.blocking import (
    GEO_CONFIDENCE_THRESHOLD,
    generate_blocking_keys,
    geo_grid_key,
    is_valid_geo,
)


def test_date_city_blocking_key():
    """Date + city produces a dc| blocking key."""
    keys = generate_blocking_keys(
        dates=[date(2026, 2, 12)],
        city_normalized="kenzingen",
        lat=None,
        lon=None,
        geo_confidence=None,
    )
    assert keys == ["dc|2026-02-12|kenzingen"]


def test_date_geo_blocking_key():
    """High confidence + valid coords produce a dg| blocking key."""
    keys = generate_blocking_keys(
        dates=[date(2026, 2, 12)],
        city_normalized=None,
        lat=48.19,
        lon=7.81,
        geo_confidence=1.0,
    )
    assert len(keys) == 1
    assert keys[0].startswith("dg|2026-02-12|")


def test_both_blocking_keys():
    """Event with city AND valid geo gets both dc| and dg| keys."""
    keys = generate_blocking_keys(
        dates=[date(2026, 2, 12)],
        city_normalized="kenzingen",
        lat=48.19,
        lon=7.81,
        geo_confidence=1.0,
    )
    assert len(keys) == 2
    dc_keys = [k for k in keys if k.startswith("dc|")]
    dg_keys = [k for k in keys if k.startswith("dg|")]
    assert len(dc_keys) == 1
    assert len(dg_keys) == 1


def test_low_confidence_no_geo_key():
    """Confidence below threshold produces no dg| key."""
    keys = generate_blocking_keys(
        dates=[date(2026, 2, 12)],
        city_normalized="kenzingen",
        lat=48.19,
        lon=7.81,
        geo_confidence=0.80,
    )
    dg_keys = [k for k in keys if k.startswith("dg|")]
    assert len(dg_keys) == 0
    # Still has dc| key
    assert len(keys) == 1


def test_outlier_coordinates_filtered():
    """Coordinates outside bounding box (Darmstadt) produce no dg| key."""
    keys = generate_blocking_keys(
        dates=[date(2026, 2, 12)],
        city_normalized="darmstadt",
        lat=49.74,  # Darmstadt latitude -- outside Breisgau box
        lon=8.65,   # Darmstadt longitude -- outside Breisgau box
        geo_confidence=0.848,
    )
    dg_keys = [k for k in keys if k.startswith("dg|")]
    assert len(dg_keys) == 0
    # Still has dc| key
    dc_keys = [k for k in keys if k.startswith("dc|")]
    assert len(dc_keys) == 1


def test_multi_date_multiple_keys():
    """Multiple dates generate keys for each date."""
    keys = generate_blocking_keys(
        dates=[date(2026, 2, 12), date(2026, 2, 13)],
        city_normalized="kenzingen",
        lat=48.19,
        lon=7.81,
        geo_confidence=1.0,
    )
    # 2 dates x 2 key types = 4 keys
    assert len(keys) == 4
    dc_keys = [k for k in keys if k.startswith("dc|")]
    dg_keys = [k for k in keys if k.startswith("dg|")]
    assert len(dc_keys) == 2
    assert len(dg_keys) == 2
    assert "dc|2026-02-12|kenzingen" in dc_keys
    assert "dc|2026-02-13|kenzingen" in dc_keys


def test_no_city_no_geo():
    """No city and no geo produces empty list."""
    keys = generate_blocking_keys(
        dates=[date(2026, 2, 12)],
        city_normalized=None,
        lat=None,
        lon=None,
        geo_confidence=None,
    )
    assert keys == []


def test_no_city_empty_string_no_key():
    """Empty city string produces no dc| key."""
    keys = generate_blocking_keys(
        dates=[date(2026, 2, 12)],
        city_normalized="",
        lat=None,
        lon=None,
        geo_confidence=None,
    )
    assert keys == []


def test_geo_grid_key_consistency():
    """Same coordinates always produce the same grid key."""
    key1 = geo_grid_key(48.19, 7.81)
    key2 = geo_grid_key(48.19, 7.81)
    assert key1 == key2
    # Slightly different coords in the same cell should produce the same key
    key3 = geo_grid_key(48.19, 7.82)
    assert key1 == key3  # close enough to be in same cell


def test_is_valid_geo_within_bounds():
    """Coordinates within Breisgau with high confidence are valid."""
    assert is_valid_geo(48.19, 7.81, 1.0) is True
    assert is_valid_geo(47.99, 7.85, GEO_CONFIDENCE_THRESHOLD) is True


def test_is_valid_geo_outside_bounds():
    """Coordinates outside the bounding box are invalid even with high confidence."""
    # Darmstadt
    assert is_valid_geo(49.74, 8.65, 0.848) is False
    # High confidence but outside bounds
    assert is_valid_geo(49.74, 8.65, 1.0) is False


def test_is_valid_geo_low_confidence():
    """Low confidence makes valid coordinates invalid."""
    assert is_valid_geo(48.19, 7.81, 0.80) is False


def test_is_valid_geo_boundary_confidence():
    """Confidence exactly at threshold is valid."""
    assert is_valid_geo(48.19, 7.81, GEO_CONFIDENCE_THRESHOLD) is True
