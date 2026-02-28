"""Matching pipeline configuration with sensible defaults.

All parameters can be overridden via ``config/matching.yaml``.
If the file does not exist, defaults are used.
"""

from __future__ import annotations

from pathlib import Path

import yaml
import structlog
from pydantic import BaseModel, model_validator


class ScoringWeights(BaseModel):
    """Relative weights for the four matching signals."""

    date: float = 0.30
    geo: float = 0.25
    title: float = 0.30
    description: float = 0.15

    @model_validator(mode="after")
    def warn_if_weights_dont_sum(self) -> "ScoringWeights":
        """Log a warning if weights do not sum to approximately 1.0."""
        total = self.date + self.geo + self.title + self.description
        if abs(total - 1.0) > 0.01:
            structlog.get_logger().warning(
                "scoring_weights_sum_mismatch",
                total=round(total, 4),
                expected=1.0,
            )
        return self


class ThresholdConfig(BaseModel):
    """Combined-score thresholds for match/no-match decisions."""

    high: float = 0.75
    low: float = 0.35


class GeoConfig(BaseModel):
    """Parameters for geographic distance scoring."""

    max_distance_km: float = 10.0
    min_confidence: float = 0.85
    neutral_score: float = 0.5


class DateConfig(BaseModel):
    """Parameters for date/time overlap scoring."""

    time_tolerance_minutes: int = 30
    time_close_minutes: int = 90
    close_factor: float = 0.7
    far_factor: float = 0.3


class TitleConfig(BaseModel):
    """Parameters for title fuzzy-matching."""

    primary_weight: float = 0.7
    secondary_weight: float = 0.3
    blend_lower: float = 0.40
    blend_upper: float = 0.80
    cross_source_type: TitleConfig | None = None


TitleConfig.model_rebuild()


class ClusterConfig(BaseModel):
    """Constraints for connected-component clustering."""

    max_cluster_size: int = 15
    min_internal_similarity: float = 0.40


class FieldStrategies(BaseModel):
    """Strategies for merging individual fields from multiple sources."""

    title: str = "longest_non_generic"
    short_description: str = "longest"
    description: str = "longest"
    highlights: str = "union"
    location_name: str = "most_complete"
    location_city: str = "most_frequent"
    location_street: str = "most_complete"
    geo: str = "highest_confidence"
    categories: str = "union"
    is_family_event: str = "any_true"
    is_child_focused: str = "any_true"
    admission_free: str = "any_true"


class CanonicalConfig(BaseModel):
    """Configuration for canonical event creation."""

    field_strategies: FieldStrategies = FieldStrategies()


class AIMatchingConfig(BaseModel):
    """Configuration for AI-assisted matching tier."""

    enabled: bool = False
    api_key: str = ""
    model: str = "gemini-2.5-flash"
    temperature: float = 0.1
    max_output_tokens: int = 2048
    max_concurrent_requests: int = 5
    confidence_threshold: float = 0.6
    cache_enabled: bool = True

    # Cost monitoring (Gemini 2.5 Flash pricing)
    cost_per_1m_input_tokens: float = 0.30
    cost_per_1m_output_tokens: float = 2.50


class CategoryWeightsConfig(BaseModel):
    """Category-specific scoring weight overrides with priority ordering."""

    priority: list[str] = []
    overrides: dict[str, ScoringWeights] = {}


class MatchingConfig(BaseModel):
    """Top-level matching configuration combining all sub-configs."""

    scoring: ScoringWeights = ScoringWeights()
    thresholds: ThresholdConfig = ThresholdConfig()
    geo: GeoConfig = GeoConfig()
    date: DateConfig = DateConfig()
    title: TitleConfig = TitleConfig()
    cluster: ClusterConfig = ClusterConfig()
    canonical: CanonicalConfig = CanonicalConfig()
    ai: AIMatchingConfig = AIMatchingConfig()
    category_weights: CategoryWeightsConfig = CategoryWeightsConfig()


def load_matching_config(path: Path) -> MatchingConfig:
    """Load matching configuration from a YAML file.

    If the file does not exist, returns a ``MatchingConfig`` with all
    default values.  Partial overrides are supported -- only the keys
    present in the YAML file will override defaults.
    """
    if not path.exists():
        return MatchingConfig()

    with open(path) as f:
        data = yaml.safe_load(f) or {}

    return MatchingConfig(**data)
