"""Synthetic demand generation for scaffolded datasets.

Builds a somewhat realistic origin-destination demand profile from a bounding box alone,
without reading any real trip data.
This is intended for the demos and tests and should not be used for actual modeling or research ;)

The generator is based on a gravity model with added hotspots and weekday/weekend patterns.
Some noise is applied on top to make the output less regular.

Output is deterministic given the same seed for test reproducibility.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from typing import TYPE_CHECKING, Any

import h3
import numpy as np
import pandas as pd

from simulation.world.demand import demand_schema

if TYPE_CHECKING:
    from pathlib import Path


@dataclass(frozen=True)
class DemandParams:
    """Parameters controlling the shape of the synthetic demand.

    Parameters
    ----------
    base_arrival_rate : float
        Peak Poisson arrivals/hour at a maximum-intensity hex in its busiest time
        bucket.
    min_arrival_rate : float
        arrival-rate floor.
    n_hotspots : int
        Number of demand hotspots seeded across the region; one anchored near the
        centroid, the rest is random.
    hotspot_decay : float
        Gaussian falloff radius per hotspot, as a fraction of the region radius.
    self_trip_share : float
        Fraction of each origin's trips that stay within the origin hex
        (self-loops). 0.0 means origin never equals destination.
    gravity_alpha : float
        Distance-decay exponent in the destination-choice gravity model.
    demand_noise_std : float
        Standard deviation of the multiplicative noise applied to each per-bucket
        arrival rate.
    weekday_pattern : tuple of float
        Diurnal multipliers per 4-hour bucket on weekdays. Resampled to other
        bucket counts. Higher entries mean busier periods.
    weekend_pattern : tuple of float
        Diurnal multipliers per 4-hour bucket on weekends.
    """

    base_arrival_rate: float = 40.0
    min_arrival_rate: float = 0.05
    n_hotspots: int = 3
    hotspot_decay: float = 0.10
    self_trip_share: float = 0.12
    gravity_alpha: float = 1.2
    demand_noise_std: float = 0.1
    weekday_pattern: tuple[float, ...] = (0.3, 0.6, 1.8, 1.2, 1.6, 0.8)
    weekend_pattern: tuple[float, ...] = (0.2, 0.3, 0.8, 1.4, 1.5, 0.6)

    @classmethod
    def from_mapping(cls, mapping: dict[str, Any]) -> DemandParams:
        """Build from a mapping (e.g. a preset's ``[name.demand]`` table).

        Unknown keys raise ``ValueError``. Pattern fields are coerced to tuples.
        """
        known = {f.name for f in fields(cls)}
        unknown = set(mapping) - known
        if unknown:
            raise ValueError(
                f"Unknown demand parameter(s): {sorted(unknown)}. Known: {sorted(known)}."
            )
        kwargs = dict(mapping)
        for pattern_field in ("weekday_pattern", "weekend_pattern"):
            if pattern_field in kwargs:
                kwargs[pattern_field] = tuple(float(x) for x in kwargs[pattern_field])
        return cls(**kwargs)


def _pairwise_distances(centers: np.ndarray) -> np.ndarray:
    diff = centers[:, np.newaxis, :] - centers[np.newaxis, :, :]
    return np.sqrt((diff**2).sum(axis=2))


def _build_hotspot_intensity(
    centers: np.ndarray, rng: np.random.Generator, params: DemandParams
) -> np.ndarray:
    """Build spatial intensity from random hotspots.

    Parameters
    ----------
    centers : numpy.ndarray
        Array of shape (n_hexes, 2) with the lat/lng centre of each hex.
    rng : numpy.random.Generator
        Pre-seeded generator used to place hotspots and weight them.
    params : DemandParams
        Demand modifiers.

    Returns
    -------
    numpy.ndarray
        Intensity per hex normalized to a maximum of 1.0.
    """
    n_hexes = len(centers)
    centroid = centers.mean(axis=0)
    radius = np.sqrt(((centers - centroid) ** 2).sum(axis=1)).max()
    if radius == 0:
        return np.ones(n_hexes)

    n_hotspots = min(params.n_hotspots, n_hexes)
    # Anchor the first hotspot at the hex nearest the centroid, draw the rest.
    central_idx = int(np.argmin(((centers - centroid) ** 2).sum(axis=1)))
    other = rng.choice(n_hexes, size=n_hotspots - 1, replace=False)
    hotspot_idx = np.concatenate([[central_idx], other])
    hotspot_weights = rng.uniform(0.5, 1.0, size=n_hotspots)

    sigma = params.hotspot_decay * radius
    diff = centers[:, np.newaxis, :] - centers[hotspot_idx][np.newaxis, :, :]
    dist_to_hotspots = np.sqrt((diff**2).sum(axis=2))
    intensity = (hotspot_weights * np.exp(-((dist_to_hotspots / sigma) ** 2))).sum(
        axis=1
    )
    return intensity / intensity.max()


def _resample_pattern(base: list[float], n: int) -> list[float]:
    """Resample a base pattern to n buckets by linear interpolation."""
    if len(base) == n:
        return base
    x_old = np.linspace(0, 1, len(base))
    x_new = np.linspace(0, 1, n)
    return np.interp(x_new, x_old, base).tolist()


def create_synthetic_demand_file(
    hex_ids: list[str],
    dataset_dir: Path,
    temporal_resolution: int,
    rng: np.random.Generator,
    root: Path,
    params: DemandParams | None = None,
) -> None:
    """Create and write a synthetic demand file.

    Parameters
    ----------
    hex_ids : list of str
        H3 cells defining the candidate origin and destination zones.
    dataset_dir : Path
        Output directory; ``demand.parquet`` is written here.
    temporal_resolution : int
        Hours per time bucket; must evenly divide 24.
    rng : numpy.random.Generator
        Pre-seeded RNG used to place hotspots and draw per-bucket noise.
    root : Path
        Repository root, used only for nicer log paths.
    params : DemandParams or None
        Demand modifiers.
    """
    if params is None:
        params = DemandParams()

    n_buckets = 24 // temporal_resolution
    weekday = np.asarray(_resample_pattern(list(params.weekday_pattern), n_buckets))
    weekend = np.asarray(_resample_pattern(list(params.weekend_pattern), n_buckets))
    patterns = np.stack([weekday, weekend])

    n_hexes = len(hex_ids)
    if n_hexes < 2:
        raise ValueError("Need at least 2 hexes to generate demand.")

    centers = np.array([h3.cell_to_latlng(h) for h in hex_ids])
    intensity = _build_hotspot_intensity(centers, rng, params)
    distances = _pairwise_distances(centers)

    # Destination attractiveness: nearby, high-intensity hexes win. Self-trips are injected explicitly below.
    gravity = 1.0 / (distances + 0.001) ** params.gravity_alpha
    np.fill_diagonal(gravity, 0.0)
    weights = gravity * intensity
    off_diag_probs = weights / weights.sum(axis=1, keepdims=True)

    # Reserve self_trip_share of each origin's mass for the self-loop, then emit
    # the full square OD matrix (diagonal included) so probabilities sum to 1.
    probs = off_diag_probs * (1.0 - params.self_trip_share)
    np.fill_diagonal(probs, params.self_trip_share)

    noise = rng.normal(0.0, params.demand_noise_std, size=(2, n_buckets, n_hexes))
    lam = params.base_arrival_rate * patterns[:, :, None] * intensity[None, None, :]
    lam = np.maximum(lam * (1.0 + noise), params.min_arrival_rate)  # (2, B, n_hexes)

    origin_idx, dest_idx = np.where(np.ones((n_hexes, n_hexes), dtype=bool))
    probs_pairs = probs[origin_idx, dest_idx]
    n_pairs = origin_idx.size
    n_groups = 2 * n_buckets

    hex_arr = np.asarray(hex_ids, dtype=object)
    df = pd.DataFrame(
        {
            demand_schema.ORIGIN: hex_arr[np.tile(origin_idx, n_groups)],
            demand_schema.DESTINATION: hex_arr[np.tile(dest_idx, n_groups)],
            demand_schema.TIME_BUCKET: np.tile(
                np.repeat(np.arange(n_buckets), n_pairs), 2
            ),
            demand_schema.IS_WEEKEND: np.repeat(
                np.array([False, True]), n_buckets * n_pairs
            ),
            demand_schema.ORIGIN_ARRIVAL_RATE: lam[:, :, origin_idx].ravel(),
            demand_schema.DESTINATION_PROBABILITY: np.tile(probs_pairs, n_groups),
        }
    )

    out_path = dataset_dir / "demand.parquet"
    df.to_parquet(out_path, index=False)

    # Some metrics for logging.
    bucket_hours = temporal_resolution
    est_daily_trips = lam.sum(axis=(1, 2)).mean() * bucket_hours
    busy_hexes = int((lam.mean(axis=(0, 1)) > 2 * params.min_arrival_rate).sum())

    print(
        f"  Wrote {out_path.relative_to(root)} ({len(df)} rows, "
        f"{busy_hexes}/{n_hexes} busy hexes, ~{est_daily_trips:.0f} trips/day)"
    )
