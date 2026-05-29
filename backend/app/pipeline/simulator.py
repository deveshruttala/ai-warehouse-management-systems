"""High-fidelity shopper simulator.

Produces the same :class:`Observation` stream as the YOLO source, but generated
from an agent-based model of shoppers moving through the store. This lets the
entire platform (streaming, analytics, anomaly detection, dashboard) be demoed
end-to-end without any CCTV footage — which, per the challenge rules, must not
be committed to the repository.

The model also injects occasional realistic *scenarios* (a checkout rush, a
crowd surge in an aisle, a restricted-zone intrusion, an abandoned-dwell), so
the anomaly detector has meaningful signal to surface.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Iterator

from .detector import Observation
from .zones import DEFAULT_LAYOUT, StoreLayout, Zone

# Plausible per-shopper bounding-box footprint (normalised).
BBOX_W = 0.045
BBOX_H = 0.11


def _zone_center(z: Zone) -> tuple[float, float]:
    return (z.x0 + z.x1) / 2, (z.y0 + z.y1) / 2


def _rand_point_in(z: Zone, pad: float = 0.02) -> tuple[float, float]:
    return (
        random.uniform(z.x0 + pad, z.x1 - pad),
        random.uniform(z.y0 + pad, z.y1 - pad),
    )


@dataclass
class _Agent:
    track_id: int
    x: float
    y: float
    speed: float
    plan: list[tuple[float, float]]
    dwell_ticks: int = 0
    wait: int = 0
    done: bool = False
    target_zone: str | None = None

    def step(self) -> None:
        if self.wait > 0:
            self.wait -= 1
            return
        if not self.plan:
            self.done = True
            return
        tx, ty = self.plan[0]
        dx, dy = tx - self.x, ty - self.y
        dist = math.hypot(dx, dy)
        if dist < self.speed:
            self.x, self.y = tx, ty
            self.plan.pop(0)
            self.wait = self.dwell_ticks
        else:
            self.x += self.speed * dx / dist
            self.y += self.speed * dy / dist


class SimulatorSource:
    """Agent-based shopper simulator."""

    name = "simulator"

    def __init__(
        self,
        layout: StoreLayout = DEFAULT_LAYOUT,
        population: int = 18,
        speed: float = 1.0,
        seed: int | None = None,
    ):
        self.layout = layout
        self.population = population
        self.speed_mult = speed
        self.rng = random.Random(seed)
        random.seed(seed)
        self._agents: dict[int, _Agent] = {}
        self._next_id = 1
        self._tick = 0
        # Aisle zones a shopper might browse.
        self._aisles = [z for z in layout.zones if z.kind == "area" and z.name != "entrance"]

    # ------------------------------------------------------------------ #
    def _spawn(self, target_zone: str | None = None, dwell: int = 0, leave_fast: bool = False) -> None:
        tid = self._next_id
        self._next_id += 1
        # Enter from just left of the entrance counting line.
        x = self.rng.uniform(0.01, 0.04)
        y = self.rng.uniform(0.4, 0.75)
        plan: list[tuple[float, float]] = [(0.10, y)]  # cross entrance line inward

        n_browse = 1 if leave_fast else self.rng.randint(1, 3)
        chosen: list[Zone] = []
        if target_zone:
            z = self.layout.zone(target_zone)
            if z:
                chosen.append(z)
        chosen += self.rng.sample(self._aisles, k=min(n_browse, len(self._aisles)))
        for z in chosen:
            plan.append(_rand_point_in(z))

        # Most shoppers visit checkout before leaving.
        if self.rng.random() < 0.75:
            ck = self.layout.zone("checkout")
            if ck:
                plan.append(_rand_point_in(ck))
        # Exit to the left, crossing the entrance line outward.
        plan.append((0.02, self.rng.uniform(0.4, 0.75)))

        self._agents[tid] = _Agent(
            track_id=tid,
            x=x,
            y=y,
            speed=self.rng.uniform(0.012, 0.022) * self.speed_mult,
            plan=plan,
            dwell_ticks=dwell or self.rng.randint(4, 16),
            target_zone=target_zone,
        )

    # ------------------------------------------------------------------ #
    def _maybe_inject_scenario(self) -> None:
        """Occasionally inject anomalous crowd behaviour."""
        roll = self.rng.random()
        # Checkout rush: a burst of shoppers heading straight to checkout.
        if roll < 0.010:
            for _ in range(self.rng.randint(6, 9)):
                self._spawn(target_zone="checkout", dwell=self.rng.randint(20, 40))
        # Crowd surge in a single aisle.
        elif roll < 0.018:
            z = self.rng.choice(self._aisles)
            for _ in range(self.rng.randint(7, 10)):
                self._spawn(target_zone=z.name, dwell=self.rng.randint(15, 30))
        # Restricted stock-room intrusion.
        elif roll < 0.024:
            tid = self._next_id
            self._next_id += 1
            sr = self.layout.zone("stockroom")
            if sr:
                cx, cy = _zone_center(sr)
                self._agents[tid] = _Agent(
                    track_id=tid,
                    x=0.6,
                    y=0.2,
                    speed=0.02 * self.speed_mult,
                    plan=[_rand_point_in(sr), (cx, cy), (0.02, 0.5)],
                    dwell_ticks=self.rng.randint(20, 40),
                )
        # Abandoned dwell: someone lingers in an aisle a very long time.
        elif roll < 0.030:
            z = self.rng.choice(self._aisles)
            self._spawn(target_zone=z.name, dwell=self.rng.randint(220, 320))

    # ------------------------------------------------------------------ #
    def _observations(self) -> list[Observation]:
        obs: list[Observation] = []
        for a in self._agents.values():
            cx = min(max(a.x, 0.0), 1.0)
            cy = min(max(a.y, 0.0), 1.0)
            obs.append(
                Observation(
                    track_id=a.track_id,
                    cx=cx,
                    cy=cy,
                    x=max(0.0, cx - BBOX_W / 2),
                    y=max(0.0, cy - BBOX_H / 2),
                    w=BBOX_W,
                    h=BBOX_H,
                    confidence=round(self.rng.uniform(0.78, 0.97), 3),
                )
            )
        return obs

    def frames(self) -> Iterator[list[Observation]]:
        while True:
            self._tick += 1
            # Maintain baseline population.
            deficit = self.population - len(self._agents)
            if deficit > 0 and self.rng.random() < 0.5:
                self._spawn()
            self._maybe_inject_scenario()

            for a in list(self._agents.values()):
                a.step()
                if a.done:
                    del self._agents[a.track_id]

            yield self._observations()
