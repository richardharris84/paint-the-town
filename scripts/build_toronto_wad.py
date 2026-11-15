import os
import math
import struct
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw

from paintball_audio import ACTOR_SOUNDS, SAMPLE_RATE, SOUND_SPECS, sound_lumps
from toronto_music import music_lumps
from toronto_materials import material_lumps, zone_for
from toronto_enemies import ALL_ENEMIES, THIRD_ENEMIES, enemy_for, enemy_patch_lines
from project_paths import ART_SOURCES, ASSETS, ROOT


OUTPUT = ROOT / "Toronto_Realms.wad"
NPC_ANIMATIONS = (
    ("POSS", "npc_gunner_actions.png", 6, tuple(range(2, 23)) + (0, 1), (174, 175)),
    ("DRON", "npc_drone_actions.png", 4, tuple(range(16)), ()),
    ("DINO", "npc_dinosaur_actions.png", 4, tuple(range(16)), ()),
    ("BEAR", "npc_polarbear_actions.png", 4, tuple(range(16)), ()),
    ("PIGE", "npc_pigeon_actions.png", 4, tuple(range(16)), ()),
    ("ARMR", "npc_armour_actions.png", 4, tuple(range(11)) + (12, 11, 13, 14, 15), ()),
    ("WOLF", "npc_wolf_actions.png", 4, tuple(range(16)), ()),
)
NPC_ATTACK_SHEETS = (
    ("npc_attacks_original.png", ("POSS", "DRON", "DINO", "BEAR")),
    ("npc_attacks_new.png", ("PIGE", "ARMR", "WOLF")),
)
# Toughness and weapon threat define small / armed medium / durable heavy tiers.
# Values are DeHackEd thing number, standing height, and collision radius.
NPC_SIZES = {"POSS": (2, 56, 20),
             **{enemy.prefix: (enemy.thing, enemy.height, enemy.radius) for enemy in ALL_ENEMIES}}
WEAPON_FRAMES = {
    "PISG": (0, 1, 2, 3, 4),
    "SHTG": (4, 5, 6, 7, 4),
    "CHGG": (8, 9),
}
WEAPON_HEIGHTS = {"PISG": 42, "SHTG": 46, "CHGG": 54}
PICKUP_FRAMES = (
    ("SHOTA0", 10, 48),
    ("MGUNA0", 11, 68),
    ("CLIPA0", 12, 16),
    ("AMMOA0", 13, 30),
    ("SHELA0", 14, 22),
    ("SBOXA0", 15, 34),
)
CELL = 320
DOOR_WIDTH = 128


def edge(a, b):
    return tuple(sorted((a, b)))


MAPS = [
    {
        "name": "E1M1",
        "title": "Union Station",
        "rows": 5,
        "cols": 5,
        "start": (0, 2),
        "exit": edge((3, 4), (4, 4)),
        "open": [
            ((0, 2), (1, 2)),
            ((1, 2), (2, 2)),
            ((2, 2), (2, 1)),
            ((2, 1), (2, 0)),
            ((2, 2), (2, 3)),
            ((2, 3), (2, 4)),
            ((2, 1), (3, 1)),
            ((2, 2), (3, 2)),
            ((2, 3), (3, 3)),
            ((3, 1), (3, 0)),
            ((3, 1), (4, 1)),
            ((3, 2), (4, 2)),
            ((3, 3), (4, 3)),
            ((3, 3), (3, 4)),
            ((3, 4), (4, 4)),
        ],
        "gunner": [(2, 0), (3, 4), (4, 1)],
        "animal": [(2, 4), (3, 0), (4, 3)],
        "site_enemy": [(3, 0), (3, 3)],
        "weapons": [((2, 1), 2001), ((4, 2), 2002)],
        "ammo": [
            ((1, 2), 2007),
            ((2, 3), 2008),
            ((3, 2), 2048),
            ((4, 1), 2049),
        ],
        "health": [((1, 2), 2011), ((3, 1), 2012)],
    },
    {
        "name": "E1M2",
        "title": "Royal Ontario Museum",
        "rows": 5,
        "cols": 5,
        "start": (0, 2),
        "exit": edge((3, 2), (4, 2)),
        "open": [
            ((0, 2), (1, 2)),
            ((1, 2), (2, 2)),
            ((2, 2), (2, 1)),
            ((2, 1), (2, 0)),
            ((2, 2), (2, 3)),
            ((2, 3), (2, 4)),
            ((2, 2), (3, 2)),
            ((3, 2), (4, 2)),
            ((3, 2), (3, 1)),
            ((3, 1), (4, 1)),
            ((3, 2), (3, 3)),
            ((3, 3), (4, 3)),
            ((4, 1), (4, 0)),
            ((4, 3), (4, 4)),
        ],
        "gunner": [(2, 0), (3, 3), (4, 4)],
        "animal": [(1, 2), (2, 4), (4, 0)],
        "site_enemy": [(4, 1), (2, 3)],
        "weapons": [((2, 3), 2001), ((3, 1), 2002)],
        "ammo": [
            ((1, 2), 2007),
            ((2, 1), 2008),
            ((4, 1), 2048),
            ((3, 3), 2049),
        ],
        "health": [((2, 0), 2011), ((4, 3), 2012)],
    },
    {
        "name": "E1M3",
        "title": "Toronto Zoo",
        "rows": 6,
        "cols": 5,
        "start": (0, 2),
        "exit": edge((4, 2), (5, 2)),
        "open": [
            ((0, 2), (1, 2)),
            ((1, 2), (2, 2)),
            ((2, 2), (2, 1)),
            ((2, 1), (2, 0)),
            ((2, 0), (1, 0)),
            ((1, 0), (1, 1)),
            ((1, 1), (1, 2)),
            ((2, 2), (2, 3)),
            ((2, 3), (2, 4)),
            ((2, 4), (1, 4)),
            ((1, 4), (1, 3)),
            ((1, 3), (1, 2)),
            ((2, 0), (3, 0)),
            ((3, 0), (3, 1)),
            ((3, 1), (3, 2)),
            ((3, 2), (3, 3)),
            ((3, 3), (3, 4)),
            ((3, 4), (2, 4)),
            ((3, 0), (4, 0)),
            ((4, 0), (4, 1)),
            ((4, 1), (4, 2)),
            ((4, 2), (4, 3)),
            ((4, 3), (4, 4)),
            ((4, 2), (5, 2)),
        ],
        "gunner": [(2, 0), (3, 2), (4, 4)],
        "animal": [(2, 4), (3, 3), (4, 0), (4, 3)],
        "site_enemy": [(1, 4), (3, 4)],
        "weapons": [((3, 1), 2001), ((4, 2), 2002)],
        "ammo": [
            ((1, 2), 2007),
            ((2, 1), 2008),
            ((3, 4), 2048),
            ((4, 1), 2049),
        ],
        "health": [((1, 0), 2011), ((4, 3), 2012)],
    },
]


def pack_name(name):
    encoded = name.encode("ascii")
    if len(encoded) > 8:
        raise ValueError(f"WAD lump name is too long: {name}")
    return encoded.ljust(8, b"\0")


def pack_fixed_name(name):
    return pack_name(name)


def _validate_spec(spec):
    rows, cols = spec["rows"], spec["cols"]
    open_edges = {edge(*pair) for pair in spec["open"]}
    for pair in open_edges:
        (r1, c1), (r2, c2) = pair
        if not (0 <= r1 < rows and 0 <= r2 < rows and 0 <= c1 < cols and 0 <= c2 < cols):
            raise ValueError(f"{spec['name']}: opening outside map grid: {pair}")
        if abs(r1 - r2) + abs(c1 - c2) != 1:
            raise ValueError(f"{spec['name']}: opening is not between adjacent cells: {pair}")
    if spec["exit"] not in open_edges:
        raise ValueError(f"{spec['name']}: exit is not on an open passage")
    reachable = {spec["start"]}
    changed = True
    while changed:
        changed = False
        for pair in open_edges:
            a, b = pair
            if a in reachable and b not in reachable:
                reachable.add(b)
                changed = True
            if b in reachable and a not in reachable:
                reachable.add(a)
                changed = True
    for field in ("gunner", "animal", "site_enemy", "health", "ammo", "weapons"):
        cells = [item[0] if field in ("health", "ammo", "weapons") else item for item in spec[field]]
        if any(cell not in reachable for cell in cells):
            raise ValueError(f"{spec['name']}: {field} contains an unreachable cell")
    (er0, ec0), (er1, ec1) = spec["exit"]
    if er0 > er1 and ec0 == ec1:
        raise ValueError(f"{spec['name']}: exit must be crossed toward the north")
    if ec0 > ec1 and er0 == er1:
        raise ValueError(f"{spec['name']}: exit must be crossed toward the east")


def _texture_side(sector, wall=None):
    return struct.pack(
        "<hh8s8s8sh",
        0,
        0,
        pack_fixed_name("-"),
        pack_fixed_name("-"),
        pack_fixed_name(wall or "-"),
        sector,
    )


def _line_angle(v1, v2):
    x1, y1 = v1
    x2, y2 = v2
    return int(round((math.atan2(y2 - y1, x2 - x1) % (2 * math.pi)) * 65536 / (2 * math.pi))) & 0xFFFF


def _make_blockmap(vertices, linedefs, origin_x, origin_y, width, height):
    cells = [[] for _ in range(width * height)]
    for line_index, line in enumerate(linedefs):
        x1, y1 = vertices[line[0]]
        x2, y2 = vertices[line[1]]
        bx0 = max(0, (min(x1, x2) - origin_x) // 128 - 1)
        bx1 = min(width - 1, (max(x1, x2) - origin_x) // 128 + 1)
        by0 = max(0, (min(y1, y2) - origin_y) // 128 - 1)
        by1 = min(height - 1, (max(y1, y2) - origin_y) // 128 + 1)
        for by in range(by0, by1 + 1):
            for bx in range(bx0, bx1 + 1):
                cells[by * width + bx].append(line_index)

    words = [origin_x, origin_y, width, height] + [0] * len(cells)
    for index, line_list in enumerate(cells):
        offset = len(words)
        if offset > 32767:
            raise ValueError("Blockmap exceeds classic Doom's signed offset range")
        words[4 + index] = offset
        words.extend(line_list)
        words.append(-1)
    if any(value < -32768 or value > 32767 for value in words):
        raise ValueError("Blockmap contains a value outside classic Doom's signed-short range")
    return struct.pack(f"<{len(words)}h", *words)


def _build_nodes(rows, cols, x0, y0):
    nodes = []

    def leaf(row, col):
        return ("leaf", row * cols + col)

    def bbox(r0, r1, c0, c1):
        return [
            y0 + r1 * CELL,
            y0 + r0 * CELL,
            x0 + c0 * CELL,
            x0 + c1 * CELL,
        ]

    def build(r0, r1, c0, c1):
        if r1 - r0 == 1 and c1 - c0 == 1:
            return leaf(r0, c0)

        if c1 - c0 > 1 and (r1 - r0 == 1 or c1 - c0 >= r1 - r0):
            middle = (c0 + c1) // 2
            cut_x = x0 + middle * CELL
            west = build(r0, r1, c0, middle)
            east = build(r0, r1, middle, c1)
            children = (east, west)
            node = (cut_x, y0 + r0 * CELL, 0, (r1 - r0) * CELL, bbox(r0, r1, middle, c1), bbox(r0, r1, c0, middle), children)
        else:
            middle = (r0 + r1) // 2
            cut_y = y0 + middle * CELL
            south = build(r0, middle, c0, c1)
            north = build(middle, r1, c0, c1)
            children = (south, north)
            node = (x0 + c0 * CELL, cut_y, (c1 - c0) * CELL, 0, bbox(r0, middle, c0, c1), bbox(middle, r1, c0, c1), children)
        node_index = len(nodes)
        nodes.append(node)
        return ("node", node_index)

    root = build(0, rows, 0, cols)

    def encode(ref):
        return (0x8000 | ref[1]) if ref[0] == "leaf" else ref[1]

    packed = []
    for x, y, dx, dy, box0, box1, children in nodes:
        packed.append(
            struct.pack(
                "<4h8h2H",
                x,
                y,
                dx,
                dy,
                *(box0 + box1),
                encode(children[0]),
                encode(children[1]),
            )
        )
    return b"".join(packed), len(nodes), encode(root)


def _build_map(spec):
    _validate_spec(spec)
    rows, cols = spec["rows"], spec["cols"]
    width, height = cols * CELL, rows * CELL
    x0, y0 = -(width // 2), -(height // 2)
    open_edges = {edge(*pair) for pair in spec["open"]}

    vertices = []
    vertex_ids = {}

    def vertex(point):
        if point not in vertex_ids:
            vertex_ids[point] = len(vertices)
            vertices.append(point)
        return vertex_ids[point]

    sides = []
    lines = []
    line_bytes = []
    portal_lines = {}
    cell_edges = {(row, col): [[], [], [], []] for row in range(rows) for col in range(cols)}

    def add_line(start, end, front_cell, back_cell=None, special=0):
        front = len(sides)
        wall = zone_for(spec["name"], *front_cell).wall
        sides.append(_texture_side(front_cell[0] * cols + front_cell[1], None if back_cell else wall))
        if back_cell is None:
            back = -1
            flags = 1
        else:
            back = len(sides)
            sides.append(_texture_side(back_cell[0] * cols + back_cell[1]))
            flags = 4
        v1, v2 = vertex(start), vertex(end)
        line = (v1, v2, flags, special, 0, front, back)
        line_index = len(lines)
        lines.append(line)
        line_bytes.append(struct.pack("<7h", *line))
        return line_index

    for row in range(rows):
        for col in range(cols):
            bl = (x0 + col * CELL, y0 + row * CELL)
            tl = (bl[0], bl[1] + CELL)
            tr = (bl[0] + CELL, bl[1] + CELL)
            br = (bl[0] + CELL, bl[1])
            edge_data = [
                (bl, tl, (row, col - 1) if col > 0 else None),
                (tl, tr, (row + 1, col) if row + 1 < rows else None),
                (tr, br, (row, col + 1) if col + 1 < cols else None),
                (br, bl, (row - 1, col) if row > 0 else None),
            ]
            for edge_index, (start, end, neighbor) in enumerate(edge_data):
                cell = (row, col)
                if neighbor is None:
                    line_index = add_line(start, end, cell)
                    cell_edges[cell][edge_index].append((start, end, line_index, 0))
                    continue
                if edge(cell, neighbor) not in open_edges:
                    line_index = add_line(start, end, cell)
                    cell_edges[cell][edge_index].append((start, end, line_index, 0))
                    continue

                axis = 1 if start[0] == end[0] else 0
                low, high = sorted((start[axis], end[axis]))
                center = (low + high) // 2
                opening_low = center - DOOR_WIDTH // 2
                opening_high = center + DOOR_WIDTH // 2
                intervals = [
                    (low, opening_low, False),
                    (opening_low, opening_high, True),
                    (opening_high, high, False),
                ]
                increasing = end[axis] > start[axis]
                for interval_low, interval_high, is_portal in intervals:
                    if interval_low == interval_high:
                        continue
                    if increasing:
                        p1, p2 = list(start), list(start)
                        p1[axis], p2[axis] = interval_low, interval_high
                    else:
                        p1, p2 = list(start), list(start)
                        p1[axis], p2[axis] = interval_high, interval_low
                    p1, p2 = tuple(p1), tuple(p2)
                    if not is_portal:
                        line_index = add_line(p1, p2, cell)
                        cell_edges[cell][edge_index].append((p1, p2, line_index, 0))
                        continue

                    portal_key = (tuple(sorted((p1, p2))), edge(cell, neighbor))
                    if portal_key not in portal_lines:
                        special = 52 if edge(cell, neighbor) == spec["exit"] else 0
                        line_index = add_line(p1, p2, cell, neighbor, special)
                        portal_lines[portal_key] = (line_index, cell, neighbor)
                    line_index, front_cell, back_cell = portal_lines[portal_key]
                    side = 0 if cell == front_cell else 1
                    cell_edges[cell][edge_index].append((p1, p2, line_index, side))

    things = []
    start_cell = spec["start"]

    thing_slots = {}
    slot_offsets = [
        (0, 0),
        (-72, 0),
        (72, 0),
        (0, -72),
        (0, 72),
        (-72, -72),
        (72, -72),
        (-72, 72),
        (72, 72),
    ]

    def add_thing(cell, thing_type, dx=0, dy=0, angle=0):
        row, col = cell
        slot = thing_slots.get(cell, 0)
        if slot >= len(slot_offsets):
            raise ValueError(f"{spec['name']}: too many things in cell {cell}")
        thing_slots[cell] = slot + 1
        offset_x, offset_y = slot_offsets[slot]
        x = x0 + col * CELL + CELL // 2 + dx + offset_x
        y = y0 + row * CELL + CELL // 2 + dy + offset_y
        things.append((x, y, angle, thing_type, 7))

    add_thing(start_cell, 1, angle=90)
    for cell in spec["gunner"]:
        add_thing(cell, 3004)
    for cell in spec["animal"]:
        add_thing(cell, enemy_for(spec["name"], THIRD_ENEMIES).doomednum)
    for cell in spec["site_enemy"]:
        add_thing(cell, enemy_for(spec["name"]).doomednum)
    for cell, thing_type in spec["weapons"]:
        add_thing(cell, thing_type)
    for cell, thing_type in spec["ammo"]:
        add_thing(cell, thing_type)
    for cell, thing_type in spec["health"]:
        add_thing(cell, thing_type)

    subsectors = []
    seg_bytes = []
    for row in range(rows):
        for col in range(cols):
            cell = (row, col)
            first = len(seg_bytes)
            for segments in cell_edges[cell]:
                for start, end, line_index, side in segments:
                    angle = _line_angle(start, end)
                    if angle >= 32768:
                        angle -= 65536
                    v1, v2 = vertex(start), vertex(end)
                    seg_bytes.append(struct.pack("<6h", v1, v2, angle, line_index, side, 0))
            count = len(seg_bytes) - first
            if count < 4:
                raise ValueError(f"{spec['name']}: cell {cell} has fewer than four boundary segs")
            subsectors.append(struct.pack("<2h", count, first))

    sector_bytes = []
    for row in range(rows):
        for col in range(cols):
            zone = zone_for(spec["name"], row, col)
            sector_bytes.append(
                struct.pack(
                    "<hh8s8shhh",
                    0,
                    128,
                    pack_fixed_name(zone.floor),
                    pack_fixed_name(zone.ceiling),
                    zone.light,
                    0,
                    0,
                )
            )

    origin_x = math.floor(x0 / 128) * 128
    origin_y = math.floor(y0 / 128) * 128
    block_width = (x0 + width - origin_x) // 128 + 1
    block_height = (y0 + height - origin_y) // 128 + 1
    blockmap = _make_blockmap(vertices, lines, origin_x, origin_y, block_width, block_height)
    reject = bytes((rows * cols * rows * cols + 7) // 8)

    nodes, node_count, root = _build_nodes(rows, cols, x0, y0)
    if node_count != rows * cols - 1 or root != node_count - 1:
        raise ValueError(f"{spec['name']}: BSP tree is not in classic Doom root-at-last order")

    thing_data = b"".join(struct.pack("<5h", *thing) for thing in things)
    vertex_data = b"".join(struct.pack("<2h", *point) for point in vertices)
    return [
        (spec["name"], b""),
        ("THINGS", thing_data),
        ("LINEDEFS", b"".join(line_bytes)),
        ("SIDEDEFS", b"".join(sides)),
        ("VERTEXES", vertex_data),
        ("SEGS", b"".join(seg_bytes)),
        ("SSECTORS", b"".join(subsectors)),
        ("NODES", nodes),
        ("SECTORS", b"".join(sector_bytes)),
        ("REJECT", reject),
        ("BLOCKMAP", blockmap),
    ]


def _plot(canvas, x, y, color):
    height, width = len(canvas), len(canvas[0])
    if 0 <= x < width and 0 <= y < height:
        canvas[y][x] = color


def _ellipse(canvas, x1, y1, x2, y2, color):
    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
    rx, ry = max(0.5, (x2 - x1) / 2), max(0.5, (y2 - y1) / 2)
    for y in range(max(0, y1), min(len(canvas), y2 + 1)):
        for x in range(max(0, x1), min(len(canvas[0]), x2 + 1)):
            if ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1:
                _plot(canvas, x, y, color)


def _sprite_patch(canvas, offsets=None):
    height, width = len(canvas), len(canvas[0])
    header_size = 8 + width * 4
    columns = []
    offset = header_size
    for x in range(width):
        column = bytearray()
        y = 0
        while y < height:
            while y < height and canvas[y][x] is None:
                y += 1
            if y == height:
                break
            top = y
            pixels = []
            while y < height and canvas[y][x] is not None and len(pixels) < 254:
                pixels.append(canvas[y][x])
                y += 1
            column.extend((top, len(pixels), 0))
            column.extend(pixels)
            column.append(0)
        column.append(255)
        columns.append((offset, bytes(column)))
        offset += len(column)
    left, top = offsets if offsets is not None else (width // 2, height - 2)
    header = struct.pack("<hhhh", width, height, left, top)
    directory = b"".join(struct.pack("<I", column_offset) for column_offset, _ in columns)
    return header + directory + b"".join(column for _, column in columns)


@lru_cache(maxsize=1)
def _doom_iwad():
    candidates = []
    configured_iwad = os.environ.get("DOOM_IWAD")
    if configured_iwad:
        candidates.append(Path(configured_iwad))
    candidates.extend(
        (
            Path(r"C:\Program Files (x86)\Steam\steamapps\common\Ultimate Doom\base\DOOM.WAD"),
            Path(r"C:\Program Files (x86)\Steam\steamapps\common\Ultimate Doom\rerelease\doom.wad"),
        )
    )
    for path in candidates:
        if not path.is_file():
            continue
        data = path.read_bytes()
        if len(data) < 12:
            raise ValueError(f"IWAD is too short to contain a directory: {path}")
        signature, lump_count, directory_offset = struct.unpack_from("<4sii", data)
        directory_end = directory_offset + lump_count * 16
        if signature not in (b"IWAD", b"PWAD") or lump_count <= 0 or directory_offset < 12 or directory_end > len(data):
            raise ValueError(f"IWAD has an invalid WAD directory: {path}")
        lumps = {}
        for index in range(lump_count):
            offset, size, raw_name = struct.unpack_from("<ii8s", data, directory_offset + index * 16)
            if offset < 0 or size < 0 or (size and offset < 12) or offset + size > directory_offset:
                raise ValueError(f"IWAD has invalid lump bounds: {path}")
            lumps[raw_name.rstrip(b"\0").decode("ascii")] = data[offset:offset + size]
        if all(name in lumps for name in ("PLAYPAL", "PNAMES", "TEXTURE1")) and len(lumps["PLAYPAL"]) >= 768:
            return lumps
        raise ValueError(f"IWAD is missing its palette or texture directories: {path}")
    raise FileNotFoundError(
        "Could not find a DOOM IWAD palette. Set DOOM_IWAD to the path of your Steam DOOM.WAD."
    )


def _doom_palette():
    return _doom_iwad()["PLAYPAL"][:768]


def _resized_npc_body(character, scale):
    body = character.convert("RGBa").resize(
        (max(1, round(character.width * scale)), max(1, round(character.height * scale))),
        Image.Resampling.LANCZOS,
    ).convert("RGBA")
    core = body.getchannel("A").point(lambda value: 255 if value >= 128 else 0)
    bounds = core.getbbox()
    if bounds is None:
        raise ValueError("Resized NPC frame has no opaque body")
    body.putalpha(core)
    return body.crop(bounds)


def _npc_sprite_canvases(animations=NPC_ANIMATIONS, sizes=NPC_SIZES, attack_sheets=NPC_ATTACK_SHEETS,
                        campaign_weapons=False):
    palette = Image.new("P", (1, 1))
    palette.putpalette(_doom_palette())
    sprites = {}
    attacks = {}
    for filename, prefixes in attack_sheets:
        tiles = _weapon_tiles(filename, 3, 4)
        for row, prefix in enumerate(prefixes):
            attacks[prefix] = tiles[row * 3:row * 3 + 3]
        if filename == "npc_attacks_new.png":
            pigeon_defeat = tiles[10:12]
    for prefix, filename, columns, frame_indices, _ in animations:
        path = ASSETS / filename
        with Image.open(path) as source:
            image = source.convert("RGB")
            source_alpha = source.getchannel("A") if source.mode == "RGBA" else None
        alpha = (source_alpha.point(lambda value: 255 if value >= 250 else 0)
                 if source_alpha is not None else _chroma_alpha(image))
        width, height = image.size
        x_edges = _sheet_gutters(alpha, columns, horizontal=True)
        y_edges = _sheet_gutters(alpha, 4, horizontal=False)
        characters = []
        for row in range(4):
            for column in range(columns):
                cell_bounds = (x_edges[column], y_edges[row], x_edges[column + 1], y_edges[row + 1])
                cell = image.crop(cell_bounds).convert("RGBA")
                cell_alpha = alpha.crop(cell_bounds)
                bounds = cell_alpha.getbbox()
                if bounds is None:
                    raise ValueError(f"{filename}: empty animation tile {row * columns + column}")
                if (bounds[0] == 0 or bounds[1] == 0
                        or (column == columns - 1 and bounds[2] == cell.width)
                        or (row == 3 and bounds[3] == cell.height)):
                    raise ValueError(f"{filename}: clipped animation tile {row * columns + column}")
                cell.putalpha(cell_alpha)
                characters.append(cell.crop(bounds))

        # Scale the entire sequence together, keeping shrinking defeat poses on the ground.
        _, standing_height, _ = sizes[prefix]
        standing_frames = characters[:4] if source_alpha is not None else characters[:6]
        scale = standing_height / max(character.height for character in standing_frames)
        # Thin feet/ears can disappear during quantization. Calibrate actual
        # opaque body height, not the transparent resampling rectangle.
        for _ in range(6):
            visible_height = max(_resized_npc_body(character, scale).height for character in standing_frames)
            if abs(visible_height - standing_height) <= 1:
                break
            scale *= standing_height / visible_height
        else:
            raise ValueError(f"{prefix}: cannot preserve the requested visible body height")
        selected = [characters[index] for index in frame_indices]
        attack_scale = standing_height / attacks[prefix][0].height
        for index, tile in enumerate(attacks[prefix][:2 if prefix == "POSS" else 3], 4):
            selected[index] = tile.resize(
                (max(1, round(tile.width * attack_scale / scale)),
                 max(1, round(tile.height * attack_scale / scale))),
                Image.Resampling.LANCZOS,
            )
        if prefix == "PIGE":
            for index, tile in enumerate(pigeon_defeat, 12):
                # The supplied sheet's settling pose stands up; use intact low poses.
                selected[index] = tile.resize(
                    (max(1, round(tile.width * attack_scale / scale)),
                     max(1, round(tile.height * attack_scale / scale))),
                    Image.Resampling.LANCZOS,
                )
        target_width = max(round(character.width * scale) for character in selected) + 4
        target_height = max(round(character.height * scale) for character in selected) + 4
        frames = []
        for character in selected:
            character = _resized_npc_body(character, scale)
            aligned = Image.new("RGBA", (target_width, target_height))
            aligned.alpha_composite(character, ((target_width - character.width) // 2, target_height - character.height - 2))
            living_frames = (*range(7), 21, 22) if prefix == "POSS" else (*range(8), 14, 15)
            if campaign_weapons and len(frames) in living_frames:
                from npc_weapons import marker_receiver
                marker_receiver(aligned, prefix, standing_height, firing=len(frames) == 5)
            character_alpha = aligned.getchannel("A").point(lambda value: 255 if value >= 128 else 0)
            indexed = aligned.convert("RGB").quantize(palette=palette, dither=Image.Dither.NONE)
            pixels = indexed.tobytes()
            alpha_pixels = character_alpha.tobytes()
            frames.append([
                [pixels[y * target_width + x] if alpha_pixels[y * target_width + x] else None
                 for x in range(target_width)]
                for y in range(target_height)
            ])
        sprites[prefix] = frames
    return sprites


def _chroma_alpha(image):
    red, green, blue = image.split()
    magenta = ImageChops.multiply(
        ImageChops.multiply(
            red.point(lambda value: 255 if value > 170 else 0),
            green.point(lambda value: 255 if value < 90 else 0),
        ),
        blue.point(lambda value: 255 if value > 170 else 0),
    )
    return Image.eval(magenta, lambda value: 255 - value)


def _indexed_canvas(image, palette):
    alpha = image.getchannel("A").tobytes()
    pixels = image.convert("RGB").quantize(palette=palette, dither=Image.Dither.NONE).tobytes()
    return [
        [pixels[y * image.width + x] if alpha[y * image.width + x] >= 128 else None
         for x in range(image.width)]
        for y in range(image.height)
    ]


def _weapon_tiles(filename, columns, rows):
    path = ASSETS / filename
    with Image.open(path) as source:
        image = source.convert("RGB")
        source_alpha = source.getchannel("A") if source.mode == "RGBA" else None
    alpha = (source_alpha.point(lambda value: 255 if value >= 250 else 0)
             if source_alpha is not None else _chroma_alpha(image))
    x_edges = _sheet_gutters(alpha, columns, horizontal=True)
    y_edges = _sheet_gutters(alpha, rows, horizontal=False)
    tiles = []
    for row in range(rows):
        for column in range(columns):
            bounds = (x_edges[column], y_edges[row], x_edges[column + 1], y_edges[row + 1])
            tile = image.crop(bounds).convert("RGBA")
            tile.putalpha(alpha.crop(bounds))
            silhouette = tile.getbbox()
            if silhouette is None:
                raise ValueError(f"{path.name}: empty weapon tile {row * columns + column}")
            tiles.append(tile.crop(silhouette))
    return tiles


def _paintball_weapon_lumps():
    tiles = _weapon_tiles("paintball_weapons.png", 4, 4)
    starter_tiles = _weapon_tiles("paintball_starter.png", 3, 2)
    palette = Image.new("P", (1, 1))
    palette.putpalette(_doom_palette())
    lumps = []
    for prefix, indices in WEAPON_FRAMES.items():
        frames = starter_tiles if prefix == "PISG" else tiles
        scale = min(WEAPON_HEIGHTS[prefix] / max(frames[index].height for index in indices),
                    148 / max(frames[index].width for index in indices))
        for frame, index in enumerate(indices):
            tile = frames[index]
            resized = tile.convert("RGBa").resize(
                (max(1, round(tile.width * scale)), max(1, round(tile.height * scale))),
                Image.Resampling.LANCZOS,
            ).convert("RGBA")
            canvas = Image.new("RGBA", (160, 144))
            canvas.alpha_composite(resized, ((160 - resized.width) // 2, 112 - resized.height))
            # Continue the cropped sleeves below the status-bar edge, not the gun.
            sleeves = canvas.crop((0, 106, 160, 112)).resize((160, 38), Image.Resampling.BICUBIC)
            for y in range(38):
                width = round(160 * (1 + y / 37))
                sleeve_row = sleeves.crop((0, y, 160, y + 1)).resize((width, 1), Image.Resampling.BICUBIC)
                canvas.paste(sleeve_row, ((160 - width) // 2, 106 + y))
            # HUD offsets use Doom's 320x200 virtual screen, not world-sprite anchors.
            lumps.append((f"{prefix}{chr(65 + frame)}0", _sprite_patch(_indexed_canvas(canvas, palette), (-80, -24))))
    for name, index, width in PICKUP_FRAMES:
        tile = tiles[index]
        height = max(1, round(tile.height * width / tile.width))
        tile = tile.convert("RGBa").resize((width, height), Image.Resampling.LANCZOS).convert("RGBA")
        lumps.append((name, _sprite_patch(_indexed_canvas(tile, palette), (width // 2, height))))
    for prefix, count in (("PISF", 1), ("SHTF", 2), ("CHGF", 2)):
        for frame in range(count):
            canvas = _paint_puff(frame)
            lumps.append((f"{prefix}{chr(65 + frame)}0", _sprite_patch(canvas, (-148, -94))))
    lumps.extend(_mallet_weapon_lumps())
    return lumps


def _mallet_weapon_lumps():
    palette = Image.new("P", (1, 1))
    palette.putpalette(_doom_palette())
    source = ART_SOURCES / "weapons" / "mallet_straight_source.png"
    with Image.open(source) as sheet:
        if sheet.mode != "RGBA" or sheet.size != (1774, 887):
            raise ValueError("Mallet source must be the approved transparent four-pose sheet")
        sheet = sheet.copy()
    poses = (
        ((58, 170, 422, 840), (-90, -24)),
        ((510, 16, 806, 840), (-90, -24)),
        ((876, 50, 1210, 840), (-60, -24)),
        ((1305, 325, 1762, 840), (-80, -24)),
    )
    lumps = []
    for frame, (bounds, offsets) in enumerate(poses):
        pose = sheet.crop(bounds)
        pose = pose.crop(pose.getbbox())
        # A common scale preserves relative head size; compensate Doom's tall pixels.
        pose = pose.convert("RGBa").resize(
            (round(pose.width * .205), round(pose.height * .205 / 1.2)),
            Image.Resampling.LANCZOS,
        ).convert("RGBA")
        pose.putalpha(pose.getchannel("A").point(lambda value: 255 if value >= 128 else 0))
        pose = pose.crop(pose.getbbox())
        image = Image.new("RGBA", (160, 144))
        image.alpha_composite(pose, (160 - pose.width, 144 - pose.height))
        lumps.append((f"PUNG{chr(65 + frame)}0",
                      _sprite_patch(_indexed_canvas(image, palette), offsets)))
    return lumps


def _sheet_gutters(alpha, count, horizontal):
    width, height = alpha.size
    length = width if horizontal else height
    edges = [0]
    for index in range(1, count):
        nominal = round(length * index / count)
        radius = max(1, round(length / count / 8))
        candidates = []
        for position in range(nominal - radius, nominal + radius + 1):
            band = (position, 0, position + 1, height) if horizontal else (0, position, width, position + 1)
            candidates.append((sum(alpha.crop(band).tobytes()), abs(position - nominal), position))
        ink, _, position = min(candidates)
        if ink:
            raise ValueError(f"Animation sheet has no clear gutter near {nominal}")
        edges.append(position)
    return edges + [length]


def _animation_patch(animations=NPC_ANIMATIONS, enemies=ALL_ENEMIES, sizes=NPC_SIZES):
    lines = ["Patch File for DeHackEd v3.0", "", "Doom version = 19", "Patch format = 6", ""]
    for _, _, _, frame_indices, idle_states in animations:
        for frame_number, state in enumerate(idle_states, len(frame_indices) - 2):
            lines.extend((f"Frame {state}", f"Sprite subnumber = {frame_number}", ""))
    # Split the existing four-tic recoil; keep FirePistol and ReFire intact.
    lines.extend((
        "Frame 15", "Duration = 2", "Next frame = 1201", "",
        "Frame 1201", "Sprite number = 3", "Sprite subnumber = 3",
        "Duration = 2", "Next frame = 16", "",
        "Frame 16", "Sprite subnumber = 4", "",
        # FirePistol starts its flash after the stock sound. Replace that sound
        # on the same origin immediately, without changing the shared DSPISTOL.
        "Frame 17", "Duration = 0", "Next frame = 1200",
        "Args1 = 8", "Args2 = 0", "",
        "Frame 1200", "Sprite number = 4", "Sprite subnumber = 32768",
        "Duration = 7", "Next frame = 1", "",
        "[CODEPTR]", "FRAME 17 = WeaponSound", "FRAME 1200 = Light1",
        "FRAME 1201 = NULL", "",
    ))
    for thing, sounds in ACTOR_SOUNDS:
        lines.append(f"Thing {thing}")
        lines.extend(f"{field} = {slot}" for field, slot in sounds.items())
        _, height, radius = next(size for size in sizes.values() if size[0] == thing)
        lines.extend((f"Width = {radius * 65536}", f"Height = {height * 65536}"))
        lines.append("")
    lines.extend(enemy_patch_lines(enemies))
    lines.extend((
        "[STRINGS]",
        "GOTSHOTGUN = You got the pump paintball marker!",
        "GOTCHAINGUN = You got the automatic paintball marker!",
        "GOTCLIP = Picked up a paintball pod.",
        "GOTCLIPBOX = Picked up a case of paintball pods.",
        "GOTSHELLS = Picked up scatter-marker paintballs.",
        "GOTSHELLBOX = Picked up a crate of paintballs.",
        "",
    ))
    return "\n".join(lines).encode("ascii")


def _paint_splat(frame):
    canvas = [[None for _ in range(32)] for _ in range(32)]
    colors = (112, 144, 176)
    color = colors[frame % len(colors)]
    highlight = (160, 200, 208)[frame % 3]
    cx = 15 + (frame % 2)
    cy = 15
    _ellipse(canvas, cx - 8, cy - 7, cx + 8, cy + 7, color)
    for dx, dy, size in (
        (-10, -8, 2),
        (10, -8, 2),
        (-11, 3, 1),
        (10, 7, 2),
        (-5, 10, 1),
        (4, -11, 1),
    ):
        _ellipse(canvas, cx + dx - size, cy + dy - size, cx + dx + size, cy + dy + size, highlight)
    _ellipse(canvas, cx - 4, cy - 4, cx + 2, cy + 1, highlight)
    return canvas


def _paint_puff(frame):
    canvas = [[None for _ in range(24)] for _ in range(24)]
    color = (144, 176, 112, 160)[frame % 4]
    highlight = (200, 208, 176, 192)[frame % 4]
    cx, cy = 11, 11
    radius = 4 + (frame % 2)
    _ellipse(canvas, cx - radius, cy - radius, cx + radius, cy + radius, color)
    for dx, dy in ((-7, 0), (7, 0), (0, -7), (0, 7), (-5, -5), (5, 5)):
        _plot(canvas, cx + dx, cy + dy, highlight)
    return canvas


def _sprite_lumps(animations=NPC_ANIMATIONS, sizes=NPC_SIZES, attack_sheets=NPC_ATTACK_SHEETS,
                  campaign_weapons=False):
    lumps = [("S_START", b"")]
    npc_sprites = _npc_sprite_canvases(animations, sizes, attack_sheets, campaign_weapons)
    for prefix, frames in npc_sprites.items():
        for frame, canvas in enumerate(frames):
            name = f"{prefix}{chr(ord('A') + frame)}0"
            lumps.append((name, _sprite_patch(canvas)))
    for sprite, frame_count, painter in (
        ("BLUD", 3, _paint_splat),
        ("PUFF", 4, _paint_puff),
    ):
        for frame in range(frame_count):
            name = f"{sprite}{chr(ord('A') + frame)}0"
            lumps.append((name, _sprite_patch(painter(frame))))
    lumps.extend(_paintball_weapon_lumps())
    lumps.append(("S_END", b""))
    return lumps


def _write_wad(lumps):
    data = bytearray(b"PWAD" + struct.pack("<ii", len(lumps), 0))
    directory = []
    for name, lump_data in lumps:
        offset = len(data)
        data.extend(lump_data)
        directory.append((offset, len(lump_data), pack_name(name)))
    directory_offset = len(data)
    for offset, size, name in directory:
        data.extend(struct.pack("<ii8s", offset, size, name))
    struct.pack_into("<i", data, 8, directory_offset)
    OUTPUT.write_bytes(data)


def _validate_wad(path=OUTPUT, maps=MAPS, animations=NPC_ANIMATIONS,
                  enemies=ALL_ENEMIES, sound_specs=SOUND_SPECS, dehacked=None,
                  soundtrack=None):
    data = Path(path).read_bytes()
    if len(data) < 12:
        raise ValueError("WAD is shorter than its header")
    signature, lump_count, directory_offset = struct.unpack_from("<4sii", data)
    if signature != b"PWAD" or lump_count <= 0:
        raise ValueError("Output is not a valid PWAD header")
    directory_end = directory_offset + lump_count * 16
    if directory_offset < 12 or directory_end > len(data):
        raise ValueError("WAD directory lies outside the file")

    lumps = []
    by_name = {}
    for index in range(lump_count):
        offset, size, raw_name = struct.unpack_from("<ii8s", data, directory_offset + index * 16)
        name = raw_name.split(b"\0", 1)[0].decode("ascii")
        if offset < 12 or size < 0 or offset + size > directory_offset:
            raise ValueError(f"Invalid WAD lump bounds: {name}")
        lump_data = data[offset:offset + size]
        lumps.append((name, lump_data))
        by_name.setdefault(name, []).append(lump_data)

    map_sizes = {
        "THINGS": 10,
        "LINEDEFS": 14,
        "SIDEDEFS": 30,
        "VERTEXES": 4,
        "SEGS": 12,
        "SSECTORS": 4,
        "NODES": 28,
        "SECTORS": 26,
    }
    for spec in maps:
        marker = next((i for i, (name, _) in enumerate(lumps) if name == spec["name"]), None)
        if marker is None:
            raise ValueError(f"Missing map marker {spec['name']}")
        map_lumps = lumps[marker:marker + 11]
        expected = [spec["name"], "THINGS", "LINEDEFS", "SIDEDEFS", "VERTEXES", "SEGS", "SSECTORS", "NODES", "SECTORS", "REJECT", "BLOCKMAP"]
        if [name for name, _ in map_lumps] != expected:
            raise ValueError(f"{spec['name']}: invalid classic Doom map-lump order")
        map_data = dict(map_lumps)
        for name, record_size in map_sizes.items():
            if len(map_data[name]) == 0 or len(map_data[name]) % record_size:
                raise ValueError(f"{spec['name']}: invalid {name} record size")

        vertices = [struct.unpack_from("<2h", map_data["VERTEXES"], i) for i in range(0, len(map_data["VERTEXES"]), 4)]
        sides_data = map_data["SIDEDEFS"]
        sides_count = len(sides_data) // 30
        sector_count = len(map_data["SECTORS"]) // 26
        for side_offset in range(0, len(sides_data), 30):
            sector = struct.unpack_from("<h", sides_data, side_offset + 28)[0]
            if not 0 <= sector < sector_count:
                raise ValueError(f"{spec['name']}: sidedef references an invalid sector")
        line_data = map_data["LINEDEFS"]
        lines = [struct.unpack_from("<7h", line_data, i) for i in range(0, len(line_data), 14)]
        for v1, v2, flags, special, tag, side0, side1 in lines:
            if not (0 <= v1 < len(vertices) and 0 <= v2 < len(vertices) and 0 <= side0 < sides_count):
                raise ValueError(f"{spec['name']}: linedef references an invalid vertex or sidedef")
            if flags & 4 and not (0 <= side1 < sides_count):
                raise ValueError(f"{spec['name']}: two-sided line is missing its back sidedef")
            if not (flags & 4) and side1 != -1:
                raise ValueError(f"{spec['name']}: one-sided line has a back sidedef")
        seg_data = map_data["SEGS"]
        for v1, v2, angle, line_index, side, offset in (
            struct.unpack_from("<6h", seg_data, i) for i in range(0, len(seg_data), 12)
        ):
            if not (0 <= v1 < len(vertices) and 0 <= v2 < len(vertices)):
                raise ValueError(f"{spec['name']}: seg references an invalid vertex")
            if not (0 <= line_index < len(lines) and side in (0, 1)):
                raise ValueError(f"{spec['name']}: seg references an invalid linedef or side")
            if side == 1 and not (lines[line_index][2] & 4):
                raise ValueError(f"{spec['name']}: seg uses a nonexistent back side")

        subsectors = [struct.unpack_from("<2H", map_data["SSECTORS"], i) for i in range(0, len(map_data["SSECTORS"]), 4)]
        total_segs = len(seg_data) // 12
        for count, first in subsectors:
            if count < 1 or first + count > total_segs:
                raise ValueError(f"{spec['name']}: invalid subsector range")
        nodes_data = map_data["NODES"]
        nodes = [struct.unpack_from("<4h8h2H", nodes_data, i) for i in range(0, len(nodes_data), 28)]
        if len(nodes) != len(subsectors) - 1:
            raise ValueError(f"{spec['name']}: BSP node count does not match the subsector tree")
        for index, node in enumerate(nodes):
            for child in node[-2:]:
                if child & 0x8000:
                    if (child & 0x7FFF) >= len(subsectors):
                        raise ValueError(f"{spec['name']}: BSP leaf pointer is out of range")
                elif child >= index:
                    raise ValueError(f"{spec['name']}: BSP node pointer is not postordered")

        things = [struct.unpack_from("<5h", map_data["THINGS"], i) for i in range(0, len(map_data["THINGS"]), 10)]
        thing_types = [thing[3] for thing in things]
        exclusive = [enemy.doomednum for enemy in enemies if enemy.map_name == spec["name"]]
        if (thing_types.count(1) != 1 or 3004 not in thing_types or 3002 in thing_types
                or len(exclusive) != 2 or not all(kind in thing_types for kind in exclusive)
                or any(enemy.doomednum in thing_types for enemy in enemies
                       if enemy.map_name != spec["name"])):
            raise ValueError(f"{spec['name']}: invalid player or location-specific enemy roster")
        if not any(t in thing_types for t in (2001, 2002)):
            raise ValueError(f"{spec['name']}: missing a weapon pickup")
        if not any(t in thing_types for t in (2007, 2008, 2048, 2049)):
            raise ValueError(f"{spec['name']}: missing ammunition")
        if not any(t in thing_types for t in (2011, 2012)):
            raise ValueError(f"{spec['name']}: missing health")
        exit_lines = spec.get("exit_lines", 1)
        if sum(1 for line in lines if line[3] == 52) != exit_lines:
            raise ValueError(f"{spec['name']}: expected {exit_lines} walk-over exit lines")

        if len(map_data["BLOCKMAP"]) % 2:
            raise ValueError(f"{spec['name']}: blockmap has a partial word")
        words = list(struct.unpack(f"<{len(map_data['BLOCKMAP']) // 2}H", map_data["BLOCKMAP"]))
        if len(words) < 5:
            raise ValueError(f"{spec['name']}: blockmap is truncated")
        block_count = words[2] * words[3]
        if words[2] <= 0 or words[3] <= 0 or 4 + block_count > len(words):
            raise ValueError(f"{spec['name']}: blockmap dimensions are invalid")
        for offset in words[4:4 + block_count]:
            if offset < 4 + block_count or offset >= len(words):
                raise ValueError(f"{spec['name']}: blockmap list offset is invalid")
            cursor = offset
            while cursor < len(words) and words[cursor] != 65535:
                if not 0 <= words[cursor] < len(lines):
                    raise ValueError(f"{spec['name']}: blockmap references an invalid linedef")
                cursor += 1
            if cursor == len(words):
                raise ValueError(f"{spec['name']}: unterminated blockmap list")

    sprite_names = {name for name, _ in lumps}
    sprite_groups = tuple((prefix, len(indices)) for prefix, _, _, indices, _ in animations) + (("BLUD", 3), ("PUFF", 4))
    expected_sprites = [
        f"{prefix}{chr(65 + frame)}0"
        for prefix, count in sprite_groups
        for frame in range(count)
    ]
    expected_sprites.extend(name for name, _ in _paintball_weapon_lumps())
    for lump in expected_sprites:
        if lump not in sprite_names:
            raise ValueError(f"Missing custom sprite lump {lump}")
        patch = by_name[lump][-1]
        if len(patch) < 8:
            raise ValueError(f"Truncated custom sprite patch {lump}")
        width, height, left, top = struct.unpack_from("<4h", patch)
        if width <= 0 or height <= 0 or len(patch) < 8 + width * 4:
            raise ValueError(f"Invalid custom sprite dimensions {lump}")
        for column in range(width):
            column_offset = struct.unpack_from("<I", patch, 8 + column * 4)[0]
            if not 8 + width * 4 <= column_offset < len(patch):
                raise ValueError(f"Invalid custom sprite column offset {lump}")
            cursor = column_offset
            while cursor < len(patch) and patch[cursor] != 255:
                if cursor + 3 > len(patch):
                    raise ValueError(f"Truncated custom sprite post {lump}")
                post_top, post_height = patch[cursor:cursor + 2]
                if post_top + post_height > height:
                    raise ValueError(f"Custom sprite post exceeds patch height: {lump}")
                cursor += 3 + post_height + 1
                if cursor > len(patch):
                    raise ValueError(f"Truncated custom sprite pixels {lump}")
            if cursor == len(patch):
                raise ValueError(f"Unterminated custom sprite column {lump}")
    if not any(name == "S_START" for name, _ in lumps) or not any(name == "S_END" for name, _ in lumps):
        raise ValueError("Custom sprite namespace markers are missing")
    for prefix, _, _, frame_indices, _ in animations:
        patches = [by_name[f"{prefix}{chr(ord('A') + frame)}0"][-1] for frame in range(len(frame_indices))]
        if len(set(patches)) != len(patches):
            raise ValueError(f"{prefix}: animation contains duplicated sprite frames")
    expected_patch = _animation_patch(animations, enemies) if dehacked is None else dehacked
    if by_name.get("DEHACKED") != [expected_patch]:
        raise ValueError("Idle-frame and character-audio DeHackEd patch is missing or incorrect")
    for name, _, _, _ in sound_specs:
        audio = by_name.get(name)
        if not audio or len(audio) != 1 or len(audio[0]) < 40:
            raise ValueError(f"Missing or truncated paintball sound: {name}")
        audio = audio[0]
        encoding, rate, count = struct.unpack_from("<HHI", audio)
        if encoding != 3 or rate != SAMPLE_RATE or count != len(audio) - 8:
            raise ValueError(f"Invalid DMX paintball sound header: {name}")
        if audio[8:24] != bytes([128]) * 16 or audio[-16:] != bytes([128]) * 16:
            raise ValueError(f"Invalid DMX sound padding: {name}")
    for name, audio in music_lumps() if soundtrack is None else soundtrack:
        if by_name.get(name) != [audio]:
            raise ValueError(f"Missing or incorrect original soundtrack lump: {name}")

    return lump_count, len(data)


def build_three_map_reference():
    lumps = []
    for spec in MAPS:
        lumps.extend(_build_map(spec))
    lumps.extend(material_lumps(_doom_iwad(), _sprite_patch))
    lumps.extend(_sprite_lumps())
    lumps.append(("DEHACKED", _animation_patch()))
    lumps.extend(sound_lumps())
    lumps.extend(music_lumps())
    _write_wad(lumps)
    lump_count, size = _validate_wad()
    print(f"Built {OUTPUT}")
    print(f"Validated {len(MAPS)} maps, {lump_count} lumps, {size:,} bytes")
    for spec in MAPS:
        print(f"  {spec['name']}: {spec['title']}")


if __name__ == "__main__":
    from build_expansion import build, publish_candidate
    build()
    publish_candidate()
