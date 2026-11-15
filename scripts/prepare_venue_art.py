"""Normalize original AI atlases into reproducible, native-scale venue sprites."""

import hashlib
import json

from PIL import Image, ImageDraw, ImageEnhance, ImageOps

from prepare_expansion_art import clean_alpha, cuts, resize
from venue_art import DIRECTORY, HUMAN_SIZE
from venue_scenery import DECORATIONS


def tiles(filename, columns, rows, used, row_bounds=None, keyed=False):
    with Image.open(DIRECTORY / filename) as source:
        image = source.convert("RGBA")
    if keyed:
        # Solid-backdrop AI sheet: key the corner background colour to alpha.
        import numpy as np
        data = np.asarray(image, dtype=int)[:, :, :3]
        background = data[2, 2]
        alpha = np.where(np.abs(data - background).sum(axis=2) > 90, 255, 0)
        image.putalpha(Image.fromarray(alpha.astype("uint8")))
    image.putalpha(clean_alpha(image.getchannel("A"), threshold=230))
    ys = row_bounds or cuts(image.getchannel("A"), rows, False)
    result = []
    for row_index, (y0, y1) in enumerate(zip(ys, ys[1:])):
        row = image.crop((0, y0, image.width, y1))
        xs = cuts(row.getchannel("A"), columns, True)
        for col, (x0, x1) in enumerate(zip(xs, xs[1:])):
            if row_index * columns + col not in used:
                continue
            tile = row.crop((x0, 0, x1, row.height))
            bounds = tile.getbbox()
            if bounds is None:
                raise ValueError(f"{filename}: missing sprite in cell {row_index * columns + col}")
            result.append(tile.crop(bounds))
    return result


def breathing_pose(image):
    """Keep the feet planted while the upper body rises by one source pixel."""
    pose = image.copy()
    split = image.height * 2 // 3
    pose.paste((0, 0, 0, 0), (0, 0, image.width, split))
    pose.alpha_composite(image.crop((0, 0, image.width, split)), (0, -1))
    return pose


def _girl_frames(filename, row_count, row_index, picks, scrub=False):
    """Walk frames from a solid-background sheet, with brand text scrubbed."""
    import numpy as np
    from PIL import ImageFilter

    with Image.open(DIRECTORY / filename) as source:
        image = source.convert("RGB")
    data = np.asarray(image, dtype=int)
    background = data[2, 2]
    alpha = np.where(np.abs(data - background).sum(axis=2) > 90, 255, 0).astype(np.uint8)
    rgba = image.convert("RGBA")
    rgba.putalpha(Image.fromarray(alpha))
    rgba.putalpha(clean_alpha(rgba.getchannel("A"), threshold=230))
    ys = cuts(rgba.getchannel("A"), row_count, False)
    row = rgba.crop((0, ys[row_index], rgba.width, ys[row_index + 1]))
    xs = cuts(row.getchannel("A"), max(picks) + 1, True)
    frames = []
    for column in picks:
        frame = row.crop((xs[column], 0, xs[column + 1], row.height))
        frame = frame.crop(frame.getbbox())
        if scrub:
            # Replace licensed shirt lettering: bright pixels enclosed by the
            # dark shirt become plain shirt fabric; faces stay untouched.
            pixels = np.asarray(frame, dtype=int)
            dark = ((pixels[:, :, :3].max(axis=2) < 80) & (pixels[:, :, 3] > 0)).astype(np.uint8)
            blurred = np.asarray(Image.fromarray(dark * 255).filter(
                ImageFilter.BoxBlur(4)), dtype=int)
            lettering = (pixels[:, :, :3].max(axis=2) > 88) & (pixels[:, :, 3] > 0) & (blurred > 95)
            pixels[lettering] = (30, 30, 34, 255)
            frame = Image.fromarray(pixels.astype(np.uint8))
            # An original bold X-eyed smiley (face only, no arrows) spans the
            # detected torso band of the shirt on every frame.
            height = pixels.shape[0]
            band = dark[round(height * .42):round(height * .62)]
            torso_rows, torso_cols = np.nonzero(band)
            if len(torso_cols):
                cx = round(torso_cols.mean())
                cy = round(height * .42) + round(torso_rows.mean())
                radius = max(5, round((np.percentile(torso_cols, 90)
                                       - np.percentile(torso_cols, 10)) * .22))
                cy += radius // 3
                overlay = Image.new("RGBA", frame.size)
                draw = ImageDraw.Draw(overlay)
                white = (242, 242, 242, 255)
                draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius),
                             fill=(30, 30, 34, 255), outline=white, width=2)
                eye = max(2, radius * 2 // 5)
                for ex in (cx - radius * 2 // 5, cx + radius * 2 // 5):
                    ey = cy - radius * 3 // 10
                    draw.line((ex - eye // 2, ey - eye // 2, ex + eye // 2, ey + eye // 2),
                              fill=white, width=2)
                    draw.line((ex - eye // 2, ey + eye // 2, ex + eye // 2, ey - eye // 2),
                              fill=white, width=2)
                draw.arc((cx - radius * 3 // 5, cy - radius * 2 // 5,
                          cx + radius * 3 // 5, cy + radius * 7 // 10),
                         25, 155, fill=white, width=2)
                # Clip the logo to the dark shirt so it never covers skin or hair.
                clipped = np.asarray(overlay, dtype=np.uint8).copy()
                clipped[..., 3] = np.minimum(clipped[..., 3], dark * 255)
                frame.alpha_composite(Image.fromarray(clipped))
        frames.append(frame)
    return frames


def directional_groups(groups):
    from venue_scenery import BY_KIND, FAN_KINDS

    people = tiles("people-directions-source.png", 8, 8, set(range(64)))
    crowd = tiles("crowd-directions-source.png", 7, 11, set(range(77)),
                  (0, 123, 225, 330, 436, 538, 647, 748, 854, 953, 1067, 1172))
    animals = tiles("animals-directions-source.png", 5, 7, set(range(35)),
                    (0, 196, 443, 635, 807, 954, 1111, 1254))
    wildlife = tiles("wildlife-directions-source.png", 5, 7, set(range(35)),
                     (0, 233, 416, 595, 774, 986, 1131, 1254))
    vendors = tiles("vendors-directions-source.png", 5, 6, set(range(30)))
    scales = {}

    def install(kind, atlas, columns, rows, *, breathe=False):
        item = BY_KIND[kind]
        selected = [atlas[row * columns + column] for row in rows for column in range(5)]
        scale = min(item.width / max(f.width for f in selected),
                    item.height / max(f.height for f in selected))
        for rotation in range(1, 9):
            column = rotation - 1 if rotation <= 5 else 9 - rotation
            frames = []
            for frame in range(len(item.frame_tics)):
                source = atlas[rows[frame % len(rows)] * columns + column]
                if rotation > 5:
                    source = ImageOps.mirror(source)
                if breathe and frame % 2:
                    source = breathing_pose(source)
                frames.append(source)
            name = f"{kind}-r{rotation}"
            groups[name] = frames
            scales[name] = scale

    for kind, rows in (("hockey_blue", (0, 1)), ("hockey_red", (2, 3)),
                       ("referee", (4, 5)), ("guitarist", (6, 7))):
        install(kind, people, 8, rows)
    for kind, rows in (("drummer", (0, 1)), ("hotdog_vendor", (2, 3)),
                       ("icecream_vendor", (4, 5))):
        install(kind, vendors, 5, rows)
    for kind, row in zip(FAN_KINDS, (0, 2, 4, 5, 7, 8, 9, 10)):
        rows = (row, row + 1) if row in (0, 5) else (row,)
        install(kind, crowd, 7, rows, breathe=len(rows) == 1)
    for atlas, kinds in (
        (animals, ("elephant", "giraffe", "deer", "kangaroo", "tiger", "bison", "penguin")),
        (wildlife, ("orangutan", "tapir", "jaguar", "snow_leopard", "moose",
                    "polar_bear", "arctic_wolf")),
    ):
        for row, kind in enumerate(kinds):
            install(kind, atlas, 5, (row,), breathe=True)
    return scales


def normalize(frames, size, scale=None):
    width, height = size
    scale = scale or min(width / max(f.width for f in frames),
                         height / max(f.height for f in frames))
    result = []
    for source in frames:
        image = resize(source, scale)
        if image.width > width or image.height > height:
            raise ValueError("Sprite exceeds its reviewed native dimensions")
        image.putalpha(image.getchannel("A").point(lambda value: 255 if value >= 128 else 0))
        target = Image.new("RGBA", size)
        target.alpha_composite(image, ((width - image.width) // 2, height - image.height))
        result.append(target)
    return result


def prepare():
    output = DIRECTORY / "sprites"
    output.mkdir(parents=True, exist_ok=True)
    animals = tiles("animals-source.png", 4, 4, set(range(14)))
    scenery = tiles("scenery-source.png", 4, 3, set(range(10)))
    humans = tiles("sports-source.png", 5, 3, set(range(4)) | set(range(5, 15)))
    baseball = tiles("baseball-home-source.png", 5, 2, set(range(10)))
    additional = tiles("zoo-expansion-source.png", 4, 4, set(range(16)))
    life = tiles("venue-life-reviewed-source.png", 4, 4, set(range(16)))
    faceoff = tiles("faceoff-source.png", 4, 3, set(range(9)))
    pedestrians = tiles("pedestrian-walk-source.png", 8, 4, set(range(32)))
    bears = tiles("polar-bear-walk-source.png", 8, 4, set(range(32)))
    portals = tiles("portal-source.png", 4, 2, set(range(2, 8)))
    vendors = tiles("street-vendors-source.png", 2, 2, set(range(4)))
    with Image.open(DIRECTORY / "portal-key-source.png") as source:
        key = source.convert("RGBA")
    key.putalpha(clean_alpha(key.getchannel("A"), threshold=230))
    bounds = key.getchannel("A").getbbox()
    if bounds is None:
        raise ValueError("portal-key-source.png: no opaque key art")
    key = key.crop(bounds)
    brighter_key = ImageEnhance.Brightness(key.convert("RGB")).enhance(1.1).convert("RGBA")
    brighter_key.putalpha(key.getchannel("A"))
    groups = {kind: animals[index * 2:index * 2 + 2] for index, kind in enumerate(
        ("elephant", "giraffe", "deer", "kangaroo", "tiger", "bison", "penguin"))}
    groups.update({kind: [image] for kind, image in zip(
        ("vase", "figure", "mineral", "fossil", "maple", "oak", "pine", "speaker",
         "platform", "zoo_sign"), scenery)})
    groups.update(referee=faceoff[:4], pitcher=baseball[:5], catcher=baseball[5:])
    groups.update(hockey_blue=[ImageOps.mirror(image) for image in faceoff[4:8]],
                  hockey_red=faceoff[8:9], fans=life[8:12],
                  fans_alternate=life[10:12] + life[8:10],
                  guitarist=life[12:14], drummer=life[14:16],
                  portal=portals[2:], portal_key=[key, brighter_key],
                  portal_panel=portals[:2],
                  hotdog_vendor=vendors[:2], icecream_vendor=vendors[2:])
    groups.update({kind: additional[index * 2:index * 2 + 2]
                   for index, kind in enumerate(("orangutan", "tapir", "jaguar",
                                                 "snow_leopard", "moose", "polar_bear",
                                                 "arctic_wolf", "penguin"))})
    groups.update({f"walker-r{rotation}": [
        pedestrians[phase * 8 + rotation - 1] for phase in range(4)]
        for rotation in range(1, 9)})
    groups.update({f"polar_bear_walk-r{rotation}": [
        bears[phase * 8 + rotation - 1] for phase in range(4)]
        for rotation in range(1, 9)})
    # The park girl now has real eight-direction walk art (front, 3/4, side,
    # 3/4-back and back columns; opposite sides are mirrored) so she faces her
    # travel direction like the arena bear instead of moonwalking.
    girl_sheet = tiles("girl-green-directions-source.png", 5, 4, set(range(20)), keyed=True)
    for rotation in range(1, 9):
        column = rotation - 1 if rotation <= 5 else 9 - rotation
        frames = []
        for phase in range(4):
            source = girl_sheet[phase * 5 + column]
            if rotation > 5:
                source = ImageOps.mirror(source)
            frames.append(source)
        groups[f"girl_green_walk-r{rotation}"] = frames
    groups.update(girl_purple=_girl_frames("girl-purple-source.png", 5, 1, (0, 2, 4, 6),
                                           scrub=True))
    # Static baseball roster: infielder and batter, five reviewed views each.
    roster = tiles("baseball-roster-source.png", 5, 2, set(range(10)), keyed=True)
    for kind, row in (("baseman", 0), ("batter", 1)):
        for rotation in range(1, 9):
            column = rotation - 1 if rotation <= 5 else 9 - rotation
            source = roster[row * 5 + column]
            groups[f"{kind}-r{rotation}"] = [ImageOps.mirror(source) if rotation > 5
                                             else source]
    # Waiting Union commuters: original idle art — each man checks his watch
    # and taps his foot in place (no walking, bare hands).
    waiting = tiles("commuters-waiting-source.png", 4, 3, set(range(12)), keyed=True)
    for row, kind in enumerate(("commuter_teal", "commuter_red", "commuter_gold")):
        groups[kind] = waiting[row * 4:row * 4 + 4]
    # Paint-themed pickup items replacing the remaining stock Doom sprites.
    pickup_cells = tiles("pickups-source.png", 4, 3, set(range(12)), keyed=True)
    groups.update(pickup_stim=[pickup_cells[0]], pickup_medi=[pickup_cells[1]],
                  pickup_vial=[pickup_cells[2]], pickup_shard=[pickup_cells[3]],
                  pickup_vest=[pickup_cells[4]], pickup_vest2=[pickup_cells[5]],
                  pickup_pod=[pickup_cells[6]], pickup_case=[pickup_cells[7]],
                  pickup_pack=[pickup_cells[8]], paint_surge=[pickup_cells[9]])
    directional = {kind: tiles(f"{kind}-directions-source.png", 5, 5, set(range(25)))
                   for kind in ("pitcher", "catcher")}
    directional_scale = min(HUMAN_SIZE[1] / max(f.height for frames in directional.values() for f in frames),
                            HUMAN_SIZE[0] / max(f.width for frames in directional.values() for f in frames))
    for kind, frames in directional.items():
        for rotation in range(1, 9):
            column = rotation - 1 if rotation <= 5 else 9 - rotation
            selected = [frames[phase * 5 + column] for phase in range(5)]
            groups[f"{kind}-r{rotation}"] = [
                ImageOps.mirror(f) if rotation > 5 else f for f in selected]
    reviewed_scales = directional_groups(groups)
    faceoff_scale = min(HUMAN_SIZE[1] / max(frame.height for frame in faceoff),
                        HUMAN_SIZE[0] / max(frame.width for frame in faceoff))
    baseball_scale = min(HUMAN_SIZE[1] / max(frame.height for frame in baseball),
                         HUMAN_SIZE[0] / max(frame.width for frame in baseball))
    standing_life = life[:8] + life[12:14]
    life_scale = min(64 / max(frame.height for frame in standing_life),
                     80 / max(frame.width for frame in standing_life))
    walker_scale = min(64 / max(frame.height for frame in pedestrians),
                       80 / max(frame.width for frame in pedestrians))
    bear_walker_scale = min(80 / max(frame.height for frame in bears),
                            120 / max(frame.width for frame in bears))
    girl_frames = [frame for rotation in range(1, 9)
                   for frame in groups[f"girl_green_walk-r{rotation}"]]
    girl_scale = min(48 / max(frame.height for frame in girl_frames),
                     40 / max(frame.width for frame in girl_frames))
    roster_frames = [groups[f"{kind}-r{rotation}"][0]
                     for kind in ("baseman", "batter") for rotation in range(1, 9)]
    roster_scale = min(64 / max(frame.height for frame in roster_frames),
                       80 / max(frame.width for frame in roster_frames))
    commuter_frames = [frame for kind in ("commuter_teal", "commuter_red", "commuter_gold")
                       for frame in groups[kind]]
    commuter_scale = min(64 / max(frame.height for frame in commuter_frames),
                         80 / max(frame.width for frame in commuter_frames))
    sizes = {item.kind: (item.width, item.height) for item in DECORATIONS}
    sizes.update(pitcher=HUMAN_SIZE, catcher=HUMAN_SIZE)
    sizes.update(portal_key=(64, 96), portal_panel=(80, 80))
    sizes.update({kind: sizes.get(kind.split("-r")[0], HUMAN_SIZE)
                  for kind in groups if "-r" in kind})
    sizes.update({f"walker-r{rotation}": HUMAN_SIZE for rotation in range(1, 9)})
    sizes.update({f"polar_bear_walk-r{rotation}": (120, 80) for rotation in range(1, 9)})
    sizes.update({f"girl_green_walk-r{rotation}": (40, 48) for rotation in range(1, 9)})
    sizes.update(girl_purple=(40, 48))
    sizes.update(pickup_stim=(28, 20), pickup_medi=(30, 26), pickup_vial=(12, 18),
                 pickup_shard=(14, 18), pickup_vest=(26, 22), pickup_vest2=(26, 22),
                 pickup_pod=(12, 16), pickup_case=(28, 20), pickup_pack=(22, 26),
                 paint_surge=(26, 26))
    manifest = dict(alpha_threshold=230, ground_anchor="bottom center; 1 pixel = 1 Doom unit",
                    human_reference_height=64, sources={}, sprites=[])
    for kind, frames in groups.items():
        scale = None
        if kind in reviewed_scales:
            scale = reviewed_scales[kind]
        elif kind.startswith("walker-r"):
            scale = walker_scale
        elif kind.startswith("polar_bear_walk-r"):
            scale = bear_walker_scale
        elif kind.startswith("girl_green_walk-r"):
            scale = girl_scale
        elif kind.split("-r")[0] in ("baseman", "batter"):
            scale = roster_scale
        elif kind.startswith("commuter_"):
            scale = commuter_scale
        elif "-r" in kind:
            scale = directional_scale
        elif kind in ("pitcher", "catcher"):
            scale = baseball_scale
        elif kind in ("referee", "hockey_blue", "hockey_red"):
            scale = faceoff_scale
        elif kind == "guitarist":
            scale = life_scale
        elif kind == "portal_key":
            scale = .65 * min(sizes[kind][0] / max(f.width for f in frames),
                              sizes[kind][1] / max(f.height for f in frames))
        native_size = (48, 40) if kind == "mineral" else sizes[kind]
        for index, image in enumerate(normalize(frames, native_size, scale)):
            if kind == "mineral":
                specimen = image
                image = Image.new("RGBA", sizes[kind])
                stand = ImageDraw.Draw(image)
                stand.polygon(((5, 40), (43, 40), (39, 68), (9, 68)),
                              fill="#6c777b", outline="#ced6d2")
                stand.rectangle((3, 37, 44, 43), fill="#a4b9bf", outline="#e5eee2")
                stand.rectangle((7, 67, 41, 71), fill="#414c55", outline="#a4b9bf")
                stand.rectangle((17, 49, 31, 54), fill="#d5cdad")
                image.alpha_composite(specimen)
            if kind == "portal_key":
                halo = Image.new("RGBA", image.size)
                draw = ImageDraw.Draw(halo)
                for inset, color in ((0, (132, 95, 20, 255)),
                                     (3, (236, 183, 41, 255)),
                                     (6, (255, 239, 133, 255))):
                    draw.ellipse((4 + inset, 84 + inset // 3,
                                  60 - inset, 95 - inset // 3),
                                 outline=color, width=2 if index else 1)
                halo.alpha_composite(image)
                image = halo
            path = output / f"{kind}-{index}.png"
            image.save(path)
            manifest["sprites"].append(dict(file=path.name, size=list(image.size),
                                             alpha_bounds=list(image.getbbox()),
                                             sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    for path in sorted(DIRECTORY.glob("*-source.png")):
        manifest["sources"][path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    (DIRECTORY / "normalization.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Prepared {len(manifest['sprites'])} polished, ground-anchored sprites")


if __name__ == "__main__":
    prepare()
