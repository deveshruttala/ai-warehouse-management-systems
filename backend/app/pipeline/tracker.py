"""A lightweight multi-object tracker (greedy IoU association).

Used by the YOLO source to assign stable ``track_id`` values to per-frame
person detections. It is intentionally dependency-free; for heavy production
workloads you would swap in ByteTrack/BoT-SORT (bundled with Ultralytics).
"""
from __future__ import annotations

from dataclasses import dataclass, field


def _iou(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    ix0, iy0 = max(ax0, bx0), max(ay0, by0)
    ix1, iy1 = min(ax1, bx1), min(ay1, by1)
    iw, ih = max(0.0, ix1 - ix0), max(0.0, iy1 - iy0)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    area_a = (ax1 - ax0) * (ay1 - ay0)
    area_b = (bx1 - bx0) * (by1 - by0)
    return inter / (area_a + area_b - inter)


@dataclass
class _Track:
    track_id: int
    box: tuple[float, float, float, float]
    misses: int = 0


@dataclass
class IoUTracker:
    iou_threshold: float = 0.3
    max_misses: int = 15
    _next_id: int = 1
    _tracks: dict[int, _Track] = field(default_factory=dict)

    def update(
        self, boxes: list[tuple[float, float, float, float]]
    ) -> list[tuple[int, tuple[float, float, float, float]]]:
        """Associate ``boxes`` (x0,y0,x1,y1) with existing tracks.

        Returns a list of ``(track_id, box)`` for the current frame.
        """
        assigned: dict[int, tuple[float, float, float, float]] = {}
        used_tracks: set[int] = set()

        # Greedy match each detection to the best unused track.
        for box in boxes:
            best_id, best_iou = None, self.iou_threshold
            for tid, tr in self._tracks.items():
                if tid in used_tracks:
                    continue
                score = _iou(box, tr.box)
                if score >= best_iou:
                    best_id, best_iou = tid, score
            if best_id is None:
                best_id = self._next_id
                self._next_id += 1
            used_tracks.add(best_id)
            assigned[best_id] = box
            self._tracks[best_id] = _Track(best_id, box, misses=0)

        # Age out unmatched tracks.
        for tid in list(self._tracks):
            if tid not in used_tracks:
                self._tracks[tid].misses += 1
                if self._tracks[tid].misses > self.max_misses:
                    del self._tracks[tid]

        return list(assigned.items())
