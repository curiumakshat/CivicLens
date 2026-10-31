"""Ward and alert scoring helpers for the CivicLens admin queue."""

from collections.abc import Iterable, Mapping
from datetime import datetime, timedelta, timezone


# These values are intentionally centralized so the corporation can replace
# them with official ward-boundary and census data later.
DEFAULT_WARD = "Ward 7"
CATEGORY_SEVERITY = {
    "roads & potholes": 4,
    "garbage & sanitation": 3,
    "streetlights": 2,
    "water supply": 4,
    "drainage & flooding": 5,
}


def ward_for_coordinates(latitude: float, longitude: float) -> str:
    """Resolve the current Jaipur pilot area to a ward label.

    The pilot currently covers Ward 7. Coordinates outside the Jaipur pilot
    box are kept visible as Unmapped instead of silently assigning a ward.
    """
    if 26.70 <= latitude <= 27.10 and 75.55 <= longitude <= 76.05:
        return DEFAULT_WARD
    return "Unmapped"


def severity_for_category(category: str) -> int:
    return CATEGORY_SEVERITY.get(category.strip().lower(), 3)


def build_alerts(
    reports: Iterable,
    wards: Mapping[str, object],
    window_days: int,
    now: datetime | None = None,
) -> list[dict]:
    """Aggregate Neon reports using normalized, explainable factors."""
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=window_days)
    groups: dict[tuple[str, str], list] = {}
    for report in reports:
        created_at = report.created_at.replace(tzinfo=timezone.utc) if report.created_at.tzinfo is None else report.created_at
        if created_at < cutoff:
            continue
        ward = ward_for_coordinates(report.latitude, report.longitude)
        groups.setdefault((ward, report.category), []).append(report)

    max_frequency = max((len(items) for items in groups.values()), default=1)
    populations = {
        name: getattr(ward, "population", None)
        for name, ward in wards.items()
        if getattr(ward, "population", None) is not None
    }
    max_population = max(populations.values(), default=1)
    alerts = []
    for (ward, category), items in groups.items():
        frequency = len(items)
        assigned_severities = [item.severity for item in items if item.severity is not None]
        severity = round(sum(assigned_severities) / len(assigned_severities), 2) if assigned_severities else severity_for_category(category)
        severity_source = "admin_assigned" if assigned_severities else "configured_category_suggestion"
        population = populations.get(ward)
        frequency_score = round((frequency / max_frequency) * 100, 1)
        severity_score = round((severity / 5) * 100, 1)
        population_score = round((population / max_population) * 100, 1) if population is not None else None
        score = round((frequency_score * 0.5) + (severity_score * 0.3) + ((population_score or 0) * 0.2), 1)
        level = "Critical" if score >= 75 else "High" if score >= 50 else "Medium"
        alerts.append({
            "ward": ward,
            "category": category,
            "reports": frequency,
            "severity": severity,
            "severity_source": severity_source,
            "population": population,
            "population_source": getattr(wards.get(ward), "population_source", None),
            "window_days": window_days,
            "score": score,
            "level": level,
            "score_breakdown": {
                "frequency_score": frequency_score,
                "severity_score": severity_score,
                "population_score": population_score,
                "weights": {"frequency": 0.5, "severity": 0.3, "population": 0.2},
            },
            "latest_report_id": max(items, key=lambda item: item.created_at).id,
        })
    return sorted(alerts, key=lambda alert: alert["score"], reverse=True)
