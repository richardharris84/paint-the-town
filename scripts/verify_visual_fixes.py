"""Checksum-bound native views and world-facing actor checks for visual revisions."""

import hashlib
import json
import math
import struct
import time

from shapely.geometry import LineString

from build_expansion import CANDIDATE
from project_paths import ROOT
from toronto_venues import venue_specs
from venue_scenery import BY_KIND, FAN_KINDS
from verify_campaign_feedback import OwnedGame
from verify_venue_scenery import build_fixture
from verify_venue_walkers import walker_records


OUTPUT = ROOT / "runtime_validation" / "visual-fixes"
VIEWS = (
    (1, "museum-hud", -1800, -450, 90),
    (2, "park-exit", 0, 3180, 90),
    (9, "zoo-exit", 0, 2080, 90),
    (3, "sankofa-spawn-frontage", -2240, -1600, 315),
    (3, "sankofa-stage-access", -250, -360, 90),
    (5, "union-hotel", 0, 3300, 90),
    (5, "union-great-hall", 0, 1000, 270),
    (5, "union-platform-commuters", 550, -1350, 270),
    (6, "arena-south", 0, -240, 90),
    (6, "arena-east", 260, 0, 180),
    (6, "arena-north", 0, 240, 270),
    (7, "baseball-south", 0, -640, 90),
    (7, "baseball-east", 600, 250, 180),
    (7, "baseball-north", 0, 900, 270),
    (7, "rogers-stands", 0, 3200, 0),
    (4, "nathan-square", 0, 700, 90),
    (8, "islands-shore", -3400, 1900, 0),
    (9, "zoo-polar-bear-front", -200, 700, 90),
    (9, "zoo-polar-bear-back", -200, 1020, 270),
)


def gallery_views(spec):
    venue = spec.compile()
    geometry = venue.geometry
    result = []
    for a, b, _, _, _, front, back in geometry.lines:
        for side in (front, back):
            if side < 0:
                continue
            data = struct.unpack("<hh8s8s8sh", geometry.sides[side])
            if not data[3].startswith((b"RMART", b"RMKING")):
                continue
            p, q = geometry.vertices[a], geometry.vertices[b]
            mx, my = (p[0] + q[0]) / 2, (p[1] + q[1]) / 2
            length = math.dist(p, q)
            sign = 1 if side == front else -1
            nx, ny = sign * (q[1] - p[1]) / length, sign * (p[0] - q[0]) / length
            for distance, lateral in ((d, offset) for d in (700, 600, 500, 400, 300)
                                      for offset in (0, -140, 140)):
                x = round(mx + nx * distance - ny * lateral)
                y = round(my + ny * distance + nx * lateral)
                sight = LineString(((mx + nx * 4, my + ny * 4), (x, y))).buffer(3)
                if venue.clear_at(x, y, 24) and venue.walkable.covers(sight):
                    angle = round(math.degrees(math.atan2(-ny, -nx))) % 360
                    label = data[3].rstrip(b"\0").decode().lower()
                    result.append((1, f"painting-{label}", x, y, angle))
                    break
            else:
                raise ValueError(f"No clear native viewpoint for {data[3]!r}")
    if len(result) != 13:
        raise ValueError(f"Expected the royal portrait plus twelve painting walls, got {len(result)}")
    return result


ROSTERS = {
    "Scotiabank Arena": ("hockey_blue", "hockey_red", "referee"),
    "Rogers Centre": ("pitcher", "catcher", "batter", "baseman"),
}


def scene_actors(save, spec):
    result = {}
    for kind in ROSTERS.get(spec.title, ()):
        item = BY_KIND[kind]
        placements = [(x, y) for x, y, k in spec.scenery if k == kind]
        actors = walker_records(save, item.sprite, item.thing - 1, (0, item.height))
        if len(actors) != len(placements):
            raise AssertionError(f"Expected {len(placements)} native {kind}, got {len(actors)}")
        for position in placements:
            expected_angle = spec.scenery_angles[(*position, kind)] // 45 * 45
            matches = [actor for actor in actors
                       if (round(actor["x"]), round(actor["y"])) == position]
            if len(matches) != 1 or abs(matches[0]["angle_degrees"] - expected_angle) > .01:
                raise AssertionError(f"Native {kind} position/facing changed with the viewer: {actors}")
        result[kind] = actors
    return result


def verify():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    proof_path = OUTPUT / "scene-results.json"
    proof_path.unlink(missing_ok=True)
    digest = hashlib.sha256(CANDIDATE.read_bytes()).hexdigest()
    specs = venue_specs()
    results = []
    for number, label, x, y, angle in (*VIEWS, *gallery_views(specs[0])):
        fixture = OUTPUT / f"{label}-fixture.wad"
        build_fixture(fixture, number, x, y, angle)
        try:
            with OwnedGame(fixture, number) as game:
                game.tap(0x57, .04)
                time.sleep(1)
                game.capture(OUTPUT / f"{label}.png")
                row = dict(map=f"E1M{number}", label=label, start=[x, y], view_angle=angle,
                           capture=f"{label}.png")
                if number in (6, 7):
                    save = OUTPUT / f"{label}.sav"
                    game.snapshot(save)
                    row["actors"] = scene_actors(save, specs[number - 1])
                    time.sleep(1)
                    game.capture(OUTPUT / f"{label}-animated.png")
                if label == "museum-hud":
                    game.tap(0x09)
                    time.sleep(1)
                    game.capture(OUTPUT / "tab-map.png")
                    row["automap"] = "tab-map.png"
                results.append(row)
                print(f"Native visual fixture: {label}", flush=True)
        finally:
            fixture.unlink(missing_ok=True)
    if hashlib.sha256(CANDIDATE.read_bytes()).hexdigest() != digest:
        raise AssertionError("Candidate changed during visual checks")
    proof = dict(
        candidate_sha256=digest,
        scope="Actual geometry and decorations; fixtures remove combat/pickups and reposition the viewer",
        captures=results,
        crowd_counts={spec.title: sum(kind in FAN_KINDS for _, _, kind in spec.scenery)
                      for spec in specs if spec.title in ("Scotiabank Arena", "Rogers Centre")},
        native_world_facing_checks=True,
        visual_review="Required: inspect full captures, the royal portrait, all twelve paintings, "
                      "referee clothing, Great Hall walls, platform commuters, baseball roster, "
                      "scoreboard, ground panel/gold outline, typography, exits and all views. "
                      "This report alone does not assert visual acceptance.",
    )
    proof_path.write_text(json.dumps(proof, indent=2) + "\n")
    print(f"Native visual evidence saved to {proof_path}")


if __name__ == "__main__":
    verify()
