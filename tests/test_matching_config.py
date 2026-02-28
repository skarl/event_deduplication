"""Tests for matching pipeline configuration loading."""

from pathlib import Path

import pytest
import yaml

from event_dedup.matching.config import (
    DateConfig,
    GeoConfig,
    MatchingConfig,
    ScoringWeights,
    ThresholdConfig,
    TitleConfig,
    load_matching_config,
)


class TestLoadFromYaml:
    """Test loading configuration from a YAML file."""

    def test_load_full_config(self, tmp_path: Path) -> None:
        """Loading a complete YAML file should populate all fields."""
        config_path = tmp_path / "matching.yaml"
        config_path.write_text(
            yaml.dump(
                {
                    "scoring": {"date": 0.25, "geo": 0.25, "title": 0.25, "description": 0.25},
                    "thresholds": {"high": 0.80, "low": 0.30},
                }
            )
        )
        cfg = load_matching_config(config_path)
        assert cfg.scoring.date == 0.25
        assert cfg.scoring.description == 0.25
        assert cfg.thresholds.high == 0.80
        assert cfg.thresholds.low == 0.30

    def test_load_real_config(self) -> None:
        """The shipped config/matching.yaml should load without errors."""
        cfg = load_matching_config(Path("config/matching.yaml"))
        assert cfg.scoring.date == 0.30
        assert cfg.scoring.geo == 0.25
        assert cfg.thresholds.high == 0.75
        assert cfg.geo.max_distance_km == 10.0

    def test_load_empty_yaml(self, tmp_path: Path) -> None:
        """An empty YAML file should return all defaults."""
        config_path = tmp_path / "empty.yaml"
        config_path.write_text("")
        cfg = load_matching_config(config_path)
        assert cfg == MatchingConfig()


class TestDefaultValues:
    """Test default configuration values when no YAML exists."""

    def test_missing_file_returns_defaults(self, tmp_path: Path) -> None:
        """A non-existent file path should return all defaults."""
        cfg = load_matching_config(tmp_path / "nonexistent.yaml")
        assert cfg.scoring.date == 0.30
        assert cfg.scoring.geo == 0.25
        assert cfg.scoring.title == 0.30
        assert cfg.scoring.description == 0.15

    def test_default_thresholds(self) -> None:
        cfg = MatchingConfig()
        assert cfg.thresholds.high == 0.75
        assert cfg.thresholds.low == 0.35

    def test_default_geo(self) -> None:
        cfg = MatchingConfig()
        assert cfg.geo.max_distance_km == 10.0
        assert cfg.geo.min_confidence == 0.85
        assert cfg.geo.neutral_score == 0.5

    def test_default_date(self) -> None:
        cfg = MatchingConfig()
        assert cfg.date.time_tolerance_minutes == 30
        assert cfg.date.time_close_minutes == 90
        assert cfg.date.close_factor == 0.7
        assert cfg.date.far_factor == 0.3

    def test_default_title(self) -> None:
        cfg = MatchingConfig()
        assert cfg.title.primary_weight == 0.7
        assert cfg.title.secondary_weight == 0.3
        assert cfg.title.blend_lower == 0.40
        assert cfg.title.blend_upper == 0.80

    def test_default_field_strategies(self) -> None:
        cfg = MatchingConfig()
        assert cfg.canonical.field_strategies.title == "longest_non_generic"
        assert cfg.canonical.field_strategies.categories == "union"
        assert cfg.canonical.field_strategies.geo == "highest_confidence"


class TestPartialOverride:
    """Test that partial YAML overrides merge with defaults."""

    def test_override_single_section(self, tmp_path: Path) -> None:
        """Overriding one section should leave others at defaults."""
        config_path = tmp_path / "partial.yaml"
        config_path.write_text(yaml.dump({"thresholds": {"high": 0.90}}))
        cfg = load_matching_config(config_path)
        # Overridden
        assert cfg.thresholds.high == 0.90
        # Defaults preserved
        assert cfg.thresholds.low == 0.35
        assert cfg.scoring.date == 0.30

    def test_override_nested_field_strategy(self, tmp_path: Path) -> None:
        """Overriding a single field strategy should preserve others."""
        config_path = tmp_path / "partial.yaml"
        config_path.write_text(
            yaml.dump({"canonical": {"field_strategies": {"title": "shortest"}}})
        )
        cfg = load_matching_config(config_path)
        assert cfg.canonical.field_strategies.title == "shortest"
        assert cfg.canonical.field_strategies.description == "longest"


class TestValidation:
    """Test Pydantic validation behavior."""

    def test_invalid_weight_type(self) -> None:
        """Non-numeric weight should raise a validation error."""
        with pytest.raises(Exception):
            ScoringWeights(date="not_a_number")  # type: ignore[arg-type]

    def test_valid_custom_thresholds(self) -> None:
        """Custom threshold values should be accepted."""
        t = ThresholdConfig(high=0.95, low=0.10)
        assert t.high == 0.95
        assert t.low == 0.10

    def test_geo_config_construction(self) -> None:
        g = GeoConfig(max_distance_km=5.0, min_confidence=0.90, neutral_score=0.6)
        assert g.max_distance_km == 5.0

    def test_date_config_construction(self) -> None:
        d = DateConfig(time_tolerance_minutes=15, time_close_minutes=60)
        assert d.time_tolerance_minutes == 15
        assert d.close_factor == 0.7  # default

    def test_title_config_construction(self) -> None:
        t = TitleConfig(primary_weight=0.5, secondary_weight=0.5)
        assert t.primary_weight == 0.5
