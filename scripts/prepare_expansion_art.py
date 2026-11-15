import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageOps

from expansion_cast import NEW_ATTACK_SHEETS, ROLES


from project_paths import ASSETS, ART_SOURCES
CELL = 420
# Some source sheets include unrequested bonus poses beneath the sixteen used
# frames. These reviewed boundaries exclude them without squashing the atlas.
ROW_LIMITS = {"owl": 1082, "wolverine": 1080, "stag": 1335, "otter": 1045}


def clean_alpha(channel, minimum_area=32, threshold=250):
    mask = np.array(channel) >= threshold
    labels = []
    parents = []
    sizes = []

    def root(i):
        while parents[i] != i:
            parents[i] = parents[parents[i]]
            i = parents[i]
        return i

    previous = []
    for y, row in enumerate(mask):
        edges = np.flatnonzero(np.diff(np.r_[False, row, False].astype(np.int8)))
        current = []
        cursor = 0
        for a, b in zip(edges[::2], edges[1::2]):
            label = len(parents)
            parents.append(label)
            sizes.append(int(b - a))
            while cursor < len(previous) and previous[cursor][1] < a:
                cursor += 1
            k = cursor
            while k < len(previous) and previous[k][0] <= b:
                other = root(previous[k][2])
                this = root(label)
                if other != this:
                    parents[other] = this
                    sizes[this] += sizes[other]
                k += 1
            current.append((a, b, label))
            labels.append((y, a, b, label))
        previous = current
    cleaned = np.zeros(mask.shape, dtype=np.uint8)
    for y, a, b, label in labels:
        if sizes[root(label)] >= minimum_area:
            cleaned[y, a:b] = 255
    return Image.fromarray(cleaned)


def cuts(alpha, count, horizontal):
    mask = np.array(alpha) > 0
    projection = mask.any(axis=0 if horizontal else 1)
    length = len(projection)
    result = [0]
    for i in range(1, count):
        nominal = round(length * i / count)
        radius = round(length / count / 3)
        candidates = [p for p in range(max(result[-1] + 1, nominal - radius),
                                      min(length, nominal + radius + 1)) if not projection[p]]
        if not candidates:
            raise ValueError(f"No empty {'column' if horizontal else 'row'} gutter at {nominal}")
        result.append(min(candidates, key=lambda p: (abs(p - nominal), p)))
    return result + [length]


def source_tiles(path, columns, rows, limit=None, threshold=250):
    with Image.open(path) as source:
        image = source.convert("RGBA")
    if limit:
        image = image.crop((0, 0, image.width, limit))
    alpha = clean_alpha(image.getchannel("A"), threshold=threshold)
    image.putalpha(alpha)
    ys = cuts(alpha, rows, False)
    tiles = []
    for y0, y1 in zip(ys, ys[1:]):
        row = image.crop((0, y0, image.width, y1))
        xs = cuts(row.getchannel("A"), columns, True)
        for x0, x1 in zip(xs, xs[1:]):
            tile = row.crop((x0, 0, x1, row.height))
            bounds = tile.getbbox()
            if not bounds:
                raise ValueError(f"{path.name}: empty tile {len(tiles)}")
            tiles.append(tile.crop(bounds))
    return tiles


def resize(image, scale):
    return image.convert("RGBa").resize(
        (max(1, round(image.width * scale)), max(1, round(image.height * scale))),
        Image.Resampling.LANCZOS,
    ).convert("RGBA")


def atlas(tiles, columns, scale):
    output = Image.new("RGBA", (CELL * columns, CELL * (len(tiles) // columns)))
    for i, tile in enumerate(tiles):
        tile = resize(tile, scale)
        if tile.width > CELL - 32 or tile.height > CELL - 32:
            raise ValueError("Normalized character exceeds the reviewed cell margin")
        x, y = (i % columns) * CELL, (i // columns) * CELL
        output.alpha_composite(tile, (x + (CELL - tile.width) // 2, y + CELL - tile.height - 16))
    return output


def main():
    attack_tiles = {}
    manifest = {"alpha_core_threshold": 250, "minimum_component_pixels": 32, "cell": CELL, "sources": {}}
    for filename, prefixes in NEW_ATTACK_SHEETS:
        source = ART_SOURCES / filename.replace(".png", "_source.png")
        tiles = source_tiles(source, 3, 4)
        if "STAG" in prefixes:
            # The antlers have a softer matte than the opaque body. Recover
            # their connected silhouette without lowering other species' core.
            antlers = source_tiles(source, 3, 4, threshold=230)
            row = prefixes.index("STAG")
            tiles[row * 3:row * 3 + 3] = antlers[row * 3:row * 3 + 3]
        scale = min(370 / max(t.height for t in tiles), 380 / max(t.width for t in tiles))
        atlas(tiles, 3, scale).save(ASSETS / filename)
        for row, prefix in enumerate(prefixes):
            attack_tiles[prefix] = tiles[row * 3:row * 3 + 3]
        manifest["sources"][source.name] = {"sha256": hashlib.sha256(source.read_bytes()).hexdigest()}
    for _, _, prefix, slug, *_ in ROLES:
        source = ART_SOURCES / f"npc_{slug}_source.png"
        threshold = 230 if slug == "stag" else 250
        tiles = source_tiles(source, 4, 4, ROW_LIMITS.get(slug), threshold=threshold)
        standing_height = max(t.height for t in tiles[:4])
        if slug == "beaver":
            # The original last fall is lower than the two supplied settle
            # poses; order these by progression rather than standing back up.
            tiles = [tiles[i] for i in (*range(11), 12, 13, 11, 14, 15)]
        if slug == "squirrel":
            tiles[11], tiles[12] = tiles[12], tiles[11]
        if slug == "stag":
            tiles[12], tiles[13] = tiles[13], tiles[12]
        if slug == "fox":
            # Supplied idles sit down abruptly; use distinct standing reverses.
            tiles[14], tiles[15] = (ImageOps.mirror(tiles[i]) for i in (0, 2))
        if slug == "wolverine":
            # The source pain pose is waist-up. Build an intact full-body paint
            # reaction from the dedicated forward-aim source instead.
            tile = attack_tiles[prefix][0].copy()
            tile = resize(tile, standing_height / tile.height)
            paint = Image.new("RGBA", tile.size)
            draw = ImageDraw.Draw(paint)
            x, y = tile.width // 2, round(tile.height * 0.48)
            r = max(4, tile.height // 23)
            draw.ellipse((x - r, y - r, x + r, y + r), fill=(15, 195, 200, 255))
            for dx, dy in ((-2, -1), (2, 1), (-1, 2), (1, -2)):
                draw.line((x, y, x + dx * r, y + dy * r), fill=(15, 195, 200, 255), width=max(2, r // 2))
            paint.putalpha(Image.composite(paint.getchannel("A"), Image.new("L", tile.size), tile.getchannel("A")))
            tile.alpha_composite(paint)
            tiles[7] = tile
        for i in (14, 15):
            tiles[i] = resize(tiles[i], standing_height / tiles[i].height)
        scale = min(360 / max(t.height for t in tiles), 380 / max(t.width for t in tiles))
        atlas(tiles, 4, scale).save(ASSETS / f"npc_{slug}_actions.png")
        manifest["sources"][source.name] = {
            "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "reviewed_row_limit": ROW_LIMITS.get(slug),
            "alpha_threshold": threshold,
            "tile_sizes": [list(t.size) for t in tiles],
        }
        print(prefix, slug, "final/standing height", round(tiles[13].height / standing_height, 3),
              "final aspect", round(tiles[13].width / tiles[13].height, 3))
    (ART_SOURCES / "normalization.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="ascii")


if __name__ == "__main__":
    main()
