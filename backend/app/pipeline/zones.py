"""Store layout: zones and counting lines, in normalised image coordinates.

Coordinates are normalised to ``[0, 1]`` so the same layout works regardless of
camera resolution. A real deployment would calibrate these per camera; here we
model a representative Purplle-style beauty retail floor.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Zone:
    name: str
    x0: float
    y0: float
    x1: float
    y1: float
    kind: str = "area"           # "area" | "queue" | "restricted"
    label: str = ""

    def contains(self, cx: float, cy: float) -> bool:
        return self.x0 <= cx <= self.x1 and self.y0 <= cy <= self.y1


@dataclass(frozen=True)
class CountingLine:
    """A vertical counting line at ``x`` used for directional footfall.

    Moving from left (x < line) to right (x > line) counts as ``in`` when
    ``inward_is_right`` is True; otherwise it counts as ``out``.
    """
    name: str
    x: float
    inward_is_right: bool = True


@dataclass
class StoreLayout:
    zones: list[Zone] = field(default_factory=list)
    lines: list[CountingLine] = field(default_factory=list)

    def zone_at(self, cx: float, cy: float) -> str | None:
        """Return the most specific zone containing the point (last match wins)."""
        hit: str | None = None
        for z in self.zones:
            if z.contains(cx, cy):
                hit = z.name
        return hit

    def zone(self, name: str) -> Zone | None:
        return next((z for z in self.zones if z.name == name), None)


# Default representative beauty-retail store layout.
DEFAULT_LAYOUT = StoreLayout(
    zones=[
        Zone("entrance", 0.00, 0.30, 0.18, 0.85, kind="area", label="Entrance"),
        Zone("skincare", 0.20, 0.05, 0.45, 0.45, kind="area", label="Skincare Aisle"),
        Zone("makeup", 0.20, 0.55, 0.45, 0.95, kind="area", label="Makeup Aisle"),
        Zone("fragrance", 0.48, 0.05, 0.72, 0.45, kind="area", label="Fragrance Aisle"),
        Zone("promo", 0.48, 0.55, 0.72, 0.95, kind="area", label="Promo Display"),
        Zone("checkout", 0.75, 0.30, 0.96, 0.95, kind="queue", label="Checkout"),
        Zone("stockroom", 0.75, 0.02, 0.98, 0.25, kind="restricted", label="Stock Room"),
    ],
    lines=[
        CountingLine("entrance_line", x=0.16, inward_is_right=True),
    ],
)

# Zones whose occupancy contributes to total store occupancy.
SALES_FLOOR_ZONES = ["skincare", "makeup", "fragrance", "promo", "checkout"]
QUEUE_ZONES = ["checkout"]
RESTRICTED_ZONES = ["stockroom"]
