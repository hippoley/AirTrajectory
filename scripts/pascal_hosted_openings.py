"""Host CAD openings on measured wall segments and carve non-overlapping spans.

This module is geometry-only. Pascal scene-node mapping is deliberately separate:
an unmatched opening MUST NOT be serialized as a floating native door/window.
Coordinates use the same units as the incoming CAD source.
"""
from dataclasses import dataclass
from math import hypot, isfinite
from typing import Iterable

@dataclass(frozen=True)
class Wall:
    id: str
    start: tuple[float, float]
    end: tuple[float, float]
    thickness: float

@dataclass(frozen=True)
class Opening:
    id: str
    kind: str
    center: tuple[float, float]
    width: float
    orientation_deg: float | None = None

def _project(wall: Wall, point: tuple[float, float]):
    ax, ay = wall.start
    dx, dy = wall.end[0]-ax, wall.end[1]-ay
    length = hypot(dx, dy)
    if not length or not isfinite(length):
        raise ValueError("zero-length wall")
    ux, uy = dx/length, dy/length
    along = (point[0]-ax)*ux+(point[1]-ay)*uy
    signed = (point[0]-ax)*(-uy)+(point[1]-ay)*ux
    return along, signed, length, (ux, uy)

def host_openings(walls: Iterable[Wall], openings: Iterable[Opening], *,
                  max_offset: float = 0.3, ambiguity_margin: float = 0.02,
                  end_clearance: float = 0.05):
    """Return native-ready hosted placements and wall solid segments.

    Reject ambiguous hosts, invalid geometry, overlaps and outside-wall holes.
    A wall's solid segments are wall-axis intervals with the holes subtracted.
    """
    walls = list(walls)
    openings = list(openings)
    if len({w.id for w in walls}) != len(walls) or len({o.id for o in openings}) != len(openings):
        raise ValueError("duplicate wall/opening ID")
    if not all(isfinite(v) and v >= 0 for v in (max_offset, ambiguity_margin, end_clearance)):
        raise ValueError("invalid matching tolerance")
    spans = {w.id: [] for w in walls}
    hosted = []
    for w in walls:
        if w.thickness <= 0 or not isfinite(w.thickness):
            raise ValueError("invalid wall thickness")
        _project(w, w.start)
    for o in openings:
        if o.kind not in ("door", "window") or not isfinite(o.width) or o.width <= 0:
            raise ValueError("invalid opening")
        if not all(isfinite(v) for v in o.center):
            raise ValueError("nonfinite opening center")
        candidates = []
        for w in walls:
            along, signed, length, direction = _project(w, o.center)
            left, right = along-o.width/2, along+o.width/2
            if abs(signed) <= max_offset and left >= end_clearance and right <= length-end_clearance:
                candidates.append((abs(signed), w.id, w, along, left, right, direction))
        candidates.sort(key=lambda row: (row[0], row[1]))
        if not candidates:
            raise ValueError("unhosted opening: " + o.id)
        if len(candidates) > 1 and candidates[1][0]-candidates[0][0] <= ambiguity_margin:
            raise ValueError("ambiguous host for opening: " + o.id)
        _, _, w, along, left, right, direction = candidates[0]
        spans[w.id].append((left, right, o.id))
        hosted.append({"id": o.id, "kind": o.kind, "host_wall_id": w.id,
                       "center_t": along/_project(w, w.start)[2], "width": o.width,
                       "center": [w.start[0]+direction[0]*along,
                                  w.start[1]+direction[1]*along],
                       "orientation_deg": o.orientation_deg})
    solids = {}
    for w in walls:
        length = _project(w, w.start)[2]
        cursor = 0.0
        segments = []
        for left, right, oid in sorted(spans[w.id]):
            if left < cursor-1e-9:
                raise ValueError("overlapping wall holes: " + w.id + "/" + oid)
            if left > cursor:
                segments.append([cursor, left])
            cursor = right
        if cursor < length:
            segments.append([cursor, length])
        solids[w.id] = segments
    return {"schema": "hosted-openings-v1", "openings": hosted, "wall_solids": solids,
            "wall_holes": {wid: [{"start": a, "end": b, "opening_id": oid}
                                for a, b, oid in sorted(values)]
                           for wid, values in spans.items()}}
