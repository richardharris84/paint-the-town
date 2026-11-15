import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps, ImageStat

from build_mod_previews import INK, MUTED, ORANGE, SIZE, TEAL, base, font, paste_fit, patch, text
from doom_geometry import read_wad
from expansion_cast import CAMPAIGN_ENEMIES
from toronto_venues import venue_specs


from project_paths import ROOT, ART_SOURCES, RELEASE
OUTPUT = ROOT / "mod_preview" / "expansion"
WAD = RELEASE


def plan_card(image, spec, box):
    x, y, width, height = box
    venue = spec.compile()
    xmin, ymin, xmax, ymax = spec.footprint.bounds
    scale = min((width - 32) / (xmax - xmin), (height - 90) / (ymax - ymin))
    ox = x + (width - (xmax - xmin) * scale) / 2
    oy = y + 32 + (height - 90 - (ymax - ymin) * scale) / 2

    def screen(point):
        px, py = point
        return round(ox + (px - xmin) * scale), round(oy + (ymax - py) * scale)

    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((x, y, x + width, y + height), radius=16, fill="#192b3a")
    for polygon, _, region in venue.faces:
        color = ("#a98157" if region.solid else "#355a4d")
        if not region.solid and region.surface.ceiling != "F_SKY1":
            color = "#465569"
        if region.surface.floor in ("RINKICE", "NFPOOL", "NPSICE"):
            color = "#89aeb2"
        if region.surface.floor == "STADDIRT":
            color = "#9c7951"
        if region.title == "Blue-key exit checkpoint":
            color = "#666bd0"
        if region.title == "Optional supply cache":
            color = "#f4ce79"
        draw.polygon([screen(p) for p in polygon.exterior.coords], fill=color)
        for hole in polygon.interiors:
            draw.polygon([screen(p) for p in hole.coords], fill="#192b3a")
    for route, color in zip(spec.routes, (TEAL, ORANGE)):
        draw.line([screen(p) for p in route], fill=color, width=3)
    for point, color in ((spec.start, "#efffff"), (spec.exit_center, "#858cff")):
        px, py = screen(point)
        draw.ellipse((px - 5, py - 5, px + 5, py + 5), fill=color)
    text(image, (x + 18, y + height - 46), f"{spec.name}  {spec.title}", 25, bold=True)


def map_sheet(specs, title):
    image = base("NINE-VENUE EXPANSION / MAP DIAGRAMS", title,
                 "Actual generated geometry and two routes per venue. Diagrams, not gameplay.")
    count = len(specs)
    width = (1792 - (count - 1) * 24) // count
    for i, spec in enumerate(specs):
        plan_card(image, spec, (64 + i * (width + 24), 260, width, 640))
    text(image, (64, 948), "Teal / orange: alternate routes     Gold: open supply alcove     Blue: key-locked exit",
         24, MUTED)
    return image


def cast_sheet(assets):
    image = base("NINETEEN ORIGINAL OPPONENT TYPES", "MEET THE TORONTO RIVALS",
                 "Embedded Doom-palette artwork. Sporting paintball equipment. Not gameplay.")
    roster = [("POSS", "Raccoon gunner")] + [(e.prefix, e.title) for e in CAMPAIGN_ENEMIES]
    for row, entries in enumerate((roster[:7], roster[7:13], roster[13:])):
        width = 1792 // len(entries)
        for col, (prefix, title) in enumerate(entries):
            x, y = 64 + col * width, 250 + row * 248
            paste_fit(image, patch(f"{prefix}E0", assets), (x + 18, y, width - 36, 188))
            label = title if len(title) <= 23 else title.replace("Animated ", "").replace("Corrupted ", "")
            text(image, (x + 8, y + 198), label, 18, TEAL, True)
    return image


def toronto_marker(image, x, y):
    """A map-pin location marker naming the real-world setting."""
    draw = ImageDraw.Draw(image)
    draw.polygon(((x - 13, y + 22), (x + 13, y + 22), (x, y + 46)), fill=ORANGE)
    draw.ellipse((x - 16, y, x + 16, y + 32), fill=ORANGE)
    draw.ellipse((x - 6, y + 10, x + 6, y + 22), fill=INK)
    text(image, (x + 28, y + 4), "TORONTO, CANADA", 29, bold=True)


def preview_image(header):
    preview = header.copy()
    draw = ImageDraw.Draw(preview)
    draw.rectangle((0, 960, 1920, 1080), fill=INK)
    draw.text((64, 981), "9 VENUES  /  19 RIVAL TYPES  /  ORIGINAL MUSIC",
              font=font(43, True), fill=TEAL)
    toronto_marker(preview, 1480, 992)
    return preview


def header_image():
    with Image.open(ART_SOURCES / "expansion_header_source.png") as source:
        artwork = source.convert("RGB")
        # Keep the painted title and Toronto marker near the top; crop rock below.
        artwork = ImageOps.fit(artwork, (1920, 980), method=Image.Resampling.LANCZOS,
                               centering=(0.5, 0.1))
    header = Image.new("RGB", SIZE, INK)
    header.paste(artwork, (0, 0))
    text(header, (64, 1002), "PAINT THE TOWN", 40, TEAL, True)
    return header


def build(output=OUTPUT):
    from build_expansion import CANDIDATE
    if WAD.read_bytes() != CANDIDATE.read_bytes():
        raise ValueError("Source geometry is unpublished; use --candidate for revision previews")
    output.mkdir(parents=True, exist_ok=True)
    assets = dict(read_wad(WAD))
    header = header_image()
    preview = preview_image(header)
    specs = venue_specs()
    images = {
        "01_preview.png": preview,
        "02_header.png": header,
        "03_north_and_sankofa.png": map_sheet(specs[:3], "MUSEUM, PARK & SANKOFA"),
        "04_civic_and_transit.png": map_sheet(specs[3:6], "CITY HALL, UNION & ARENA"),
        "05_stadium_islands_zoo.png": map_sheet(specs[6:], "DIAMOND, ISLANDS & ZOO"),
        "06_full_cast.png": cast_sheet(assets),
    }
    capture = ROOT / "runtime_validation" / "overworld-01-entering.png"
    proof = json.loads((ROOT / "runtime_validation" / "overworld-results.json").read_text())
    if proof.get("wad_sha256") != hashlib.sha256(WAD.read_bytes()).hexdigest():
        raise ValueError("Overworld preview requires native evidence for the published WAD")
    with Image.open(capture) as image:
        if image.size != SIZE:
            raise ValueError("Native overworld capture must retain its original 1920x1080 size")
        images["07_native_overworld.png"] = image.convert("RGB")
    manifest = []
    for name, image in images.items():
        target = output / name
        image.convert("RGB").save(target, optimize=True)
        with Image.open(target) as check:
            check.load()
            if check.format != "PNG" or check.mode != "RGB" or check.size != SIZE:
                raise ValueError(f"{name}: invalid upload image format or dimensions")
            if sum(ImageStat.Stat(check).var) <= 100:
                raise ValueError(f"{name}: blank upload image")
        if target.stat().st_size >= 6_000_000:
            raise ValueError(f"{name}: exceeds conservative uploader size limit")
        manifest.append({"file": name, "size": list(image.size), "mode": "RGB",
                         "bytes": target.stat().st_size, "gameplay_capture": False,
                         "native_intermission_capture": name == "07_native_overworld.png"})
        print(f"{name}: {target.stat().st_size:,} bytes")
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    for name in ("03_original_venues.png", "04_squares_and_stadium.png", "05_arena_park_islands.png"):
        (output / name).unlink(missing_ok=True)


def build_candidate():
    from build_expansion import CANDIDATE
    output = ROOT / "mod_preview" / "candidate_revisions"
    evidence = ROOT / "runtime_validation" / "candidate-revisions"
    proof = json.loads((evidence / "scene-results.json").read_text())
    digest = hashlib.sha256(CANDIDATE.read_bytes()).hexdigest()
    if proof["candidate_sha256"] != digest:
        raise ValueError("Candidate previews require matching native scene evidence")
    output.mkdir(parents=True, exist_ok=True)
    published = RELEASE.exists() and hashlib.sha256(RELEASE.read_bytes()).hexdigest() == digest
    names = ("hud-stress", "nathan-single-tower", "arena-referee-point",
             "rogers-dugouts", "baseball-side", "islands-start", "zoo-entry",
             "zoo-indo-malaya", "zoo-africa", "zoo-canadian-domain", "zoo-giraffe-scale",
             "zoo-eurasia", "referee-scale-near", "referee-scale-far",
             "rom-gallery", "park-woodland")
    files = []
    for name in names:
        source = evidence / f"{name}.png"
        target = output / source.name
        target.write_bytes(source.read_bytes())
        files.append(dict(file=target.name, native_capture=True))
    overview = base("HIGH-QUALITY AI ART / NATIVE KEX CAPTURES",
                    "PUBLISHED REVISION SCENES" if published else "UNPUBLISHED ART CANDIDATE",
                    "Real in-game materials and species-scaled sprites. "
                    + ("These bytes are the published release."
                       if published else "Release held pending verification."))
    for (name, label), (x, y) in zip(
        (("rom-gallery", "Museum artwork and artifacts"), ("zoo-eurasia", "Wildlife and habitat materials"),
         ("referee-scale-near", "Human scale / eye-height crosshair"), ("park-woodland", "Dimensional foliage")),
        ((64, 250), (984, 250), (64, 650), (984, 650))
    ):
        with Image.open(evidence / f"{name}.png") as source:
            paste_fit(overview, source.convert("RGBA"), (x, y, 872, 330))
        text(overview, (x, y + 335), label, 23, TEAL, True)
    ImageDraw.Draw(overview).rectangle((1000, 1030, 1919, 1079), fill=INK)
    text(overview, (1080, 1040), "REAL KEX GAMEPLAY / CONTACT SHEET", 22, MUTED)
    overview.save(output / "quality-overview.png")
    files.append(dict(file="quality-overview.png", native_capture=False,
                      native_capture_contact_sheet=True))
    specs = venue_specs()
    for name, venues in (("civic-sports", specs[3:7]), ("islands-zoo", specs[7:])):
        target = output / f"{name}-layout.png"
        map_sheet(venues, "PUBLISHED REVISION" if published
                  else "UNPUBLISHED REVISION CANDIDATE").save(target)
        files.append(dict(file=target.name, native_capture=False))
    manifest = dict(candidate_sha256=digest, published=published,
                    publication_held=not published, files=files)
    if not published:
        manifest["blocker"] = "Native verification incomplete for these candidate bytes"
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    status = "published-revision" if published else "unpublished candidate"
    print(f"Generated {len(files)} {status} previews: {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build published or explicitly unpublished candidate previews")
    parser.add_argument("--candidate", action="store_true")
    args = parser.parse_args()
    build_candidate() if args.candidate else build()
