import math
import struct
from dataclasses import dataclass, field, replace

from shapely import affinity
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union

from toronto_materials import ZONES
from venue_geometry import Region, Surface, add_exit, compile_venue
from campaign_order import STOPS


UNITS_PER_METRE = 32
UNITS_PER_FOOT = UNITS_PER_METRE * 0.3048


def material(name, *, ceiling_height=384, floor_height=0):
    zone = ZONES[name]
    return Surface(zone.wall, zone.floor, zone.ceiling, zone.light,
                   floor_height, ceiling_height)


def ellipse(x, y, rx, ry):
    return affinity.scale(Point(x, y).buffer(1, quad_segs=8), rx, ry)


def path(points, width):
    return LineString(points).buffer(width / 2, cap_style=2, join_style=2)


@dataclass(frozen=True)
class Encounter:
    center: tuple[int, int]
    facing: int
    roles: tuple[str, ...] = ("gunner", "primary", "secondary")


@dataclass
class VenueSpec:
    name: str
    title: str
    footprint: Polygon
    base: Surface
    start: tuple[int, int]
    exit_center: tuple[int, int]
    scale_note: str
    regions: list[Region] = field(default_factory=list)
    districts: dict[str, tuple[int, int]] = field(default_factory=dict)
    encounters: list[Encounter] = field(default_factory=list)
    # Polylines are deliberate principal routes, not generated cell corridors.
    routes: list[tuple[tuple[int, int], ...]] = field(default_factory=list)
    anchors: dict[str, float] = field(default_factory=dict)
    scenery: list[tuple[int, int, str]] = field(default_factory=list)
    scenery_angles: dict[tuple[int, int, str], int] = field(default_factory=dict)
    playable_outline: Polygon | None = None

    def decorate(self, x, y, kind, *, angle=0):
        self.scenery.append((x, y, kind))
        self.scenery_angles[(x, y, kind)] = angle % 360
        return self

    def area(self, title, shape, surface, *, solid=False):
        self.regions.append(Region(title, shape, surface, solid))
        if not solid:
            p = shape.intersection(self.footprint).representative_point()
            self.districts[title] = (round(p.x), round(p.y))
        return self

    def cover(self, title, x, y, width, depth, *, angle=0, height=144, surface=None):
        shape = box(x - width / 2, y - depth / 2, x + width / 2, y + depth / 2)
        if angle:
            shape = affinity.rotate(shape, angle, origin=(x, y))
        surface = replace(surface or self.base, floor_height=height)
        return self.area(title, shape, surface, solid=True)

    def encounter(self, x, y, facing=270, roles=("gunner", "primary", "secondary")):
        self.encounters.append(Encounter((x, y), facing, roles))
        return self

    def compile(self):
        venue = compile_venue(self.name, self.footprint, self.base, self.regions)
        if not venue.clear_at(*self.start, 34):
            raise ValueError(f"{self.name}: obstructed start")
        x, y = self.exit_center
        if not venue.clear_at(x, y, 34):
            raise ValueError(f"{self.name}: obstructed exit")
        checkpoint = next((region for region in self.regions if region.title == "Blue-key exit checkpoint"), None)
        if checkpoint is None:
            add_exit(venue, (x - 96, y), (x + 96, y))
        else:
            from portal_gates import install_gate
            install_gate(venue, self, checkpoint)
        if self.title == "Royal Ontario Museum":
            from venue_scenery import apply_gallery_panels
            apply_gallery_panels(venue)
        if self.title == "Rogers Centre":
            for index, line in enumerate(venue.geometry.lines):
                a, b, flags, special, tag, front, back = line
                p, q = venue.geometry.vertices[a], venue.geometry.vertices[b]
                if (back >= 0 and p[1] == q[1] == 84
                        and any(left <= min(p[0], q[0]) < max(p[0], q[0]) <= right
                                for left, right in ((-1120, -430), (430, 1120)))):
                    for side in (front, back):
                        xo, yo, upper, lower, _, sector = struct.unpack("<hh8s8s8sh", venue.geometry.sides[side])
                        venue.geometry.sides[side] = struct.pack("<hh8s8s8sh", xo, yo, upper, lower,
                                                               b"PTFENCE", sector)
                    venue.geometry.lines[index] = (a, b, flags | 1 | 16, special, tag, front, back)
        if self.title == "Toronto Islands":
            water_titles = {"Island lake basin", "Island open water horizon"}
            shoreline = [polygon for polygon, _, region in venue.faces
                         if region.title in water_titles]
            if shoreline:
                water = unary_union(shoreline)
                water_sectors = {sector for _, sector, region in venue.faces
                                 if region.title in water_titles}
                venue.walkable = venue.walkable.difference(water)
                for index, line in enumerate(venue.geometry.lines):
                    a, b, flags, special, tag, front, back = line
                    if back < 0:
                        continue
                    fs = struct.unpack_from("<h", venue.geometry.sides[front], 28)[0]
                    bs = struct.unpack_from("<h", venue.geometry.sides[back], 28)[0]
                    if (fs in water_sectors) != (bs in water_sectors):
                        venue.geometry.lines[index] = (a, b, flags | 1, special, tag, front, back)
        return venue


def union_station():
    plaza = material("union_plaza", ceiling_height=864)
    hall = material("union_hall", ceiling_height=864)
    concourse = material("union_concourse", ceiling_height=384)
    platforms = material("union_platform", ceiling_height=320)
    spec = VenueSpec(
        "E1M1", "Union Station", box(-3600, -1800, 3600, 2100), plaza,
        (0, -1570), (2820, 1840),
        "Great Hall length anchored at 250 ft (2438 units); 752 ft facade "
        "approximately 7335 units. Public connections are estimated, flattened "
        "and simplified, not a surveyed stacked-floor plan.",
        anchors={"great_hall_length_ft": 250, "facade_length_ft": 752},
    )
    spec.area("Front Street forecourt", box(-3600, -1800, 3600, -1180), plaza)
    # The first interior space wears the real Great Hall's arched limestone.
    spec.area("Great Hall", box(-1219, -1120, 1219, -300),
              replace(hall, wall="UGREATH", light=216))
    spec.area("West public connection", box(-3400, -1120, -1219, -300), concourse)
    spec.area("East public connection", box(1219, -1120, 3400, -300), concourse)
    spec.area("Public concourse loop", box(-3400, -300, 3400, 1060), concourse)
    spec.area("Platform approaches", box(-3400, 1060, 3400, 2100), platforms)
    # Facade wings leave three public entrances, rather than a solid maze wall.
    for x, width in ((-2840, 1120), (-1370, 820), (1370, 820), (2840, 1120)):
        spec.cover("Front facade wing", x, -1150, width, 160, height=864, surface=hall)
    for x in (-960, -480, 480, 960):
        for y in (-920, -460):
            spec.cover("Great Hall column", x, y, 96, 96, height=864, surface=hall)
    for x in (-2420, -1400, 1400, 2420):
        spec.cover("Concourse retail island", x, 360, 600, 400, height=384, surface=concourse)
    for x in (-2800, -1700, -600, 600, 1700):
        spec.cover("Platform approach screen", x, 1450, 130, 620, height=320, surface=platforms)
    for x, y, a in ((-400, -1360, 0), (400, -1360, 0), (0, 220, 0),
                    (-1800, -680, 90), (1800, -680, 90), (-900, 830, 0), (900, 830, 0)):
        spec.cover("Temporary event barrier", x, y, 300, 110, angle=a, surface=concourse)
    for x, y in ((-2000, -700), (2000, -700), (-2850, 800), (2850, 800),
                 (-1100, 1750), (1100, 1750), (2400, 1770)):
        spec.encounter(x, y)
    spec.routes = [
        ((0, -1570), (0, -700), (0, -30), (-3000, -30), (-3000, 950),
         (3000, 950), (3000, 1840), (2820, 1840)),
        ((0, -1570), (0, -700), (0, -150), (3000, -150), (3000, 950),
         (3000, 1840), (2820, 1840)),
    ]
    spec.regions = [replace(region, polygon=affinity.scale(region.polygon, yfact=-1, origin=(0, 0)))
                    for region in spec.regions if region.title != "Platform approach screen"]
    spec.footprint = affinity.scale(spec.footprint, yfact=-1, origin=(0, 0))
    spec.footprint = spec.footprint.union(box(-3600, 1100, 3600, 3880))
    spec.start = (spec.start[0], -spec.start[1])
    spec.exit_center = (spec.exit_center[0], -spec.exit_center[1])
    spec.routes = [tuple((x, -y) for x, y in route) for route in spec.routes]
    spec.encounters = [replace(e, center=(e.center[0], -e.center[1]), facing=(-e.facing) % 360)
                       for e in spec.encounters]
    spec.districts = {name: (x, -y) for name, (x, y) in spec.districts.items()}
    spec.area("Front Street north outlook", box(-3600, 1800, 3600, 3880),
              replace(plaza, ceiling_height=1664))
    road = replace(plaza, wall="ROADBED", floor="ASPHALT", ceiling_height=1664)
    spec.area("Front Street south asphalt lane", box(-3600, 2000, 3600, 2450), road)
    spec.area("Front Street cobblestone median", box(-3600, 2450, 3600, 2700),
              replace(road, wall="COBBLE", floor="COBBLEF"))
    spec.area("Front Street north asphalt lane", box(-3600, 2700, 3600, 3150), road)
    spec.area("Front Street level pedestrian crossing", box(-180, 2000, 180, 3150),
              replace(road, floor="CROSSWLK"))
    spec.scale_note += " North Front Street/Royal York frontage; southern railway platforms."
    hotel = Surface("RYWINDOW", "RYWINDOF", "F_SKY1", 224, 640, 1664)
    spec.area("Royal York north facade", box(-1160, 3720, 1160, 3880), hotel, solid=True)
    spec.area("Royal York stepped central roof", box(-650, 3736, 650, 3880),
              replace(hotel, wall="QROOF", floor="QROOFF", floor_height=800), solid=True)
    spec.area("Royal York central crown", box(-300, 3750, 300, 3880),
              replace(hotel, wall="QROOF", floor="QROOFF", floor_height=896), solid=True)
    for x in (-2200, -1100, 0, 1100, 2200):
        spec.area("South rail track", box(x - 110, -2080, x + 110, -1120),
                  replace(platforms, wall="RAILEDGE", floor="TRACKBED", floor_height=-8))
        for side in (-1, 1):
            edge_x = x + side * 122
            spec.area("Platform safety edge", box(edge_x - 6, -2080, edge_x + 6, -1120),
                      replace(platforms, floor="PLATSAFE"))
    for x in (-2600, -1500, -400, 700, 1800):
        spec.cover("Train shed platform pier", x, -1520, 64, 64, height=320, surface=platforms)
        spec.decorate(x + 170, -1570, "platform")
    # Commuters wait for the train on the south platforms instead of pacing.
    for x, kind in ((-550, "commuter_teal"), (550, "commuter_red"),
                    (1650, "commuter_gold")):
        spec.decorate(x, -1700, kind, angle=270)
    spec.cover("South train shed backdrop", 0, -2050, 5000, 80, height=320,
               surface=replace(platforms, wall="RAILEDGE"))
    return spec


def royal_ontario_museum():
    stone = material("rom_heritage", ceiling_height=448)
    modern = material("rom_crystal", ceiling_height=512)
    gallery = material("rom_gallery", ceiling_height=384)
    rotunda = material("rom_rotunda", ceiling_height=576)
    footprint = Polygon([(-2400, -2300), (1600, -2300), (2300, -1650),
                         (2300, 2100), (-2400, 2100)])
    spec = VenueSpec(
        "E1M2", "Royal Ontario Museum", footprint, stone,
        (0, -2040), (-1800, 1800),
        "Estimated 147 x 138 m public-floor envelope guided by visitor-map "
        "wing adjacency. Multiple public floors are a non-overlapping gallery "
        "anthology, not a surveyed single floor or complete interior.",
    )
    spec.area("Bloor forecourt", box(-2400, -2300, 2300, -1640),
              material("rom_forecourt", ceiling_height=576))
    spec.area("Crystal entrance", Polygon([(-1100, -1640), (1600, -1640),
                                          (1000, -700), (-650, -700)]), modern)
    spec.area("Heritage entrance", box(-2400, -1640, -1250, -700), stone)
    spec.area("Central rotunda", ellipse(0, -100, 650, 650), rotunda)
    spec.area("Earth and minerals wing", box(-2350, -600, -750, 900), gallery)
    spec.area("Life and biodiversity wing", box(750, -600, 2250, 900), gallery)
    spec.area("Fossil galleries", box(400, 900, 2250, 2050), gallery)
    spec.area("World cultures wing", box(-2350, 900, -400, 2050), stone)
    spec.area("North public cross-gallery", box(-400, 700, 400, 2050), modern)
    for x in (-800, 800):
        spec.cover("Crystal event screen", x, -1460, 440, 110, angle=25, surface=modern)
    for x in (-1480, 1480):
        spec.cover("Gallery dividing wall south", x, -620, 1080, 112, height=384, surface=gallery)
        spec.cover("Gallery dividing wall north", x, 920, 1080, 112, height=384, surface=gallery)
    for x in (-2200, -750, 750, 2200):
        spec.cover("North gallery screen", x, 1340, 110, 510, height=384, surface=gallery)
    # Freestanding feature wall hosting the large royal portrait (RMKING).
    spec.cover("Featured portrait wall", 0, 860, 480, 112, height=384, surface=gallery)
    for x, y, a in ((-1650, 150, 90), (1650, 150, 90),
                    (-1250, 1600, 0), (1250, 1600, 0)):
        spec.cover("Freestanding exhibit case", x, y, 480, 150, angle=a, surface=stone)
    for a in range(0, 360, 90):
        x, y = round(490 * math.cos(math.radians(a))), round(-100 + 490 * math.sin(math.radians(a)))
        spec.cover("Rotunda display plinth", x, y, 140, 140, surface=rotunda)
    for x, y in ((-1800, -100), (1800, -100), (-1800, 650), (1800, 650),
                 (-900, 1800), (900, 1800), (0, 1100)):
        spec.encounter(x, y)
    spec.routes = [
        ((0, -2040), (0, -1000), (230, -800), (230, -100), (0, -100),
         (-600, 600), (-600, 1100), (-600, 1800), (-1800, 1800)),
        ((0, -2040), (0, -1000), (230, -800), (230, -100), (0, -100),
         (600, 600), (600, 1100), (600, 1800),
         (0, 1800), (-600, 1800), (-1800, 1800)),
    ]
    for x, y, kind in (
        (-1900, -280, "vase"), (-1100, 380, "figure"), (1100, -280, "mineral"),
        (1920, 380, "fossil"), (-1920, 1110, "figure"), (-1100, 1800, "vase"),
        (1100, 1110, "fossil"), (1850, 1800, "mineral"),
        (-300, 300, "vase"), (300, 300, "figure"),
    ):
        spec.decorate(x, y, kind)
    return spec


ZOO_SPECIES = {
    "Indo-Malaya": ("orangutan", "tapir"),
    "Africa": ("elephant", "giraffe"),
    "Americas": ("bison", "jaguar"),
    "Australasia": ("kangaroo", "penguin"),
    "Eurasia": ("tiger", "snow_leopard"),
    "Canadian Domain": ("deer", "moose"),
    "Tundra Trek": ("polar_bear", "arctic_wolf"),
}


def toronto_zoo():
    grass = material("zoo_meadow", ceiling_height=512)
    trail = material("zoo_path", ceiling_height=512)
    habitat = material("zoo_habitat", ceiling_height=512)
    footprint = box(-2400, -2400, 2400, 2600)
    spec = VenueSpec(
        "E1M3", "Toronto Zoo", footprint, grass, (0, -2200), (0, 2400),
        "Seven-region 150 x 156 m anthology with entrance/Discovery Zone cues, "
        "close-set habitats and connected public loops. Official-map adjacency "
        "is compressed, not a 1:1 zoo or a reproduction of every enclosure.",
    )
    centers = {
        "Indo-Malaya": (-1150, -1250), "Africa": (-1150, 50),
        "Americas": (1150, 1350), "Australasia": (1150, 50),
        "Eurasia": (1150, -1250), "Canadian Domain": (-1150, 1350),
        "Tundra Trek": (0, 900),
    }
    loop = [(-1950, -1850), (-1950, 2100), (1950, 2100),
            (1950, -1850), (-1950, -1850)]
    spec.area("Main zoo loop", path(loop, 300), trail)
    spec.area("Entry plaza", box(-600, -2400, 600, -1850), material("zoo_entry", ceiling_height=512))
    spec.area("Discovery Zone", box(-550, -1800, 550, -900), trail)
    spec.area("Central visitor walk", path([(0, -2200), (0, 0)], 260), trail)
    for y in (-650, 650, 1950):
        spec.area("Cross-zoo public link", path([(-1950, y), (1950, y)], 240), trail)
    for index, (title, (x, y)) in enumerate(centers.items(), 1):
        half = 400 if title == "Tundra Trek" else 550
        ground = replace(habitat, floor="RINKICE") if title == "Tundra Trek" else habitat
        spec.area(title, box(x - half, y - 440, x + half, y + 440), ground)
        spec.area(title + " viewing path", path([(x - half, y - 320), (x + half, y - 320)], 160), trail)
        spec.cover(title + " grounded pavilion facade", x, y + 400, half * 2, 96,
                   height=192, surface=replace(habitat, wall=f"ZSIGN{index}"))
        for side in (-1, 1):
            spec.cover(title + " enclosure shelter wing", x + side * (half - 45), y + 120,
                       90, 460, height=160, surface=habitat)
        spec.cover(title + " planted viewing island", x - half + 150, y - 300, 160, 100,
                   height=128, surface=habitat)
        spec.area(title + " drinking pool", ellipse(x + 170, y + 160, 130, 90),
                  replace(grass, floor="RINKICE", floor_height=-8))
        for offset, animal in zip((-200, 190), ZOO_SPECIES[title]):
            spec.decorate(x + offset, y, animal, angle=270)
        spec.decorate(x - 180, y + 180, "pine" if title in ("Tundra Trek", "Canadian Domain") else "maple")
        spec.decorate(x + 270, y + 240, "oak")
        spec.encounter(x + 180, y - 220)
    for x in (-720, 720):
        spec.cover("Grounded entrance information pavilion", x, -2150, 220, 180,
                   height=192, surface=habitat)
    spec.decorate(-350, -2150, "zoo_sign")
    spec.decorate(350, -2150, "zoo_sign")
    spec.routes = [
        ((0, -2200), (0, -1900), (-2100, -1900), (-2100, 2100),
         (-1950, 2250), (0, 2250), (0, 2400)),
        ((0, -2200), (0, -1900), (2100, -1900), (2100, 2100),
         (1950, 2250), (0, 2250), (0, 2400)),
    ]
    return spec


def sankofa_square():
    stone = material("union_plaza", ceiling_height=1536)
    spec = VenueSpec(
        "E1M4", "Sankofa Square",
        box(-3100, -2200, 1500, 2000),
        stone, (-2240, -1600), (850, 670),
        "Irregular plaza approximately 4000 square metres at 32 units/metre. "
        "Outline and stage/fountain adjacency are estimates guided by official "
        "permit maps, not an extracted scale-bearing survey. Expanded estimated "
        "street envelope includes north/south Yonge, Dundas and a full-block "
        "south frontage near spawn; not a surveyed storefront reconstruction.",
    )
    spec.area("Full urban plaza", spec.footprint, stone)
    road = replace(stone, wall="ROADBED", floor="ASPHALT")
    spec.area("Yonge Street north and south approaches", box(-1900, -2200, -1350, 2000), road)
    spec.area("Dundas Street intersection", box(-3100, -1300, 1500, -950), road)
    spec.area("Yonge Dundas crosswalk", box(-2050, -1300, -1200, -950),
              replace(road, floor="CROSSWLK"))
    spec.area("South block sidewalk", box(-3100, -1880, 1500, -1310), stone)
    spec.cover("South block light-stone frontage", -800, -2060, 4600, 280,
               height=768, surface=replace(stone, wall="EATONHM"))
    spec.cover("Yonge north storefront block", -2780, 800, 560, 1450,
               height=1024, surface=replace(stone, wall="RYWINDOW"))
    spec.area("Dundas canopy and stage", box(-950, 510, 650, 900),
              replace(stone, ceiling="UFCOFFR", ceiling_height=320))
    spec.area("Flush fountain field", box(-600, -200, 150, 350), replace(stone, floor="NFTFOUNT"))
    spec.area("Yonge perimeter approach", box(-1200, -900, -950, 900), stone)
    spec.area("Victoria perimeter approach", box(950, -900, 1300, 900), stone)
    for x in (-820, -250, 320):
        spec.cover("Canopy support", x, 730, 64, 64, height=320)
    for x, y, a in ((-500, -540, 0), (460, -540, 0), (-770, 80, 90),
                    (500, 60, 90), (-600, 250, 0), (760, 420, 0)):
        spec.cover("Portable square tournament bunker", x, y, 270, 110, angle=a,
                   surface=replace(stone, wall="PBTEAL", floor="PBTEALF"))
    spec.cover("Central event wedge", 80, -130, 240, 240, angle=45,
               surface=replace(stone, wall="PBORANGE", floor="PBORNGF"))
    for x, y in ((400, -200), (-450, 160), (450, 550), (950, 250)):
        spec.encounter(x, y, roles=("gunner", "primary"))
    spec.encounter(-600, 600, roles=("secondary", "gunner"))
    spec.routes = [
        ((-2240, -1600), (-2100, -1600), (-2100, -1100), (-1620, -1100),
         (-1620, 1400), (-1200, 1400), (-950, 470), (-600, 510), (180, 510), (850, 670)),
        ((-2240, -1600), (-2100, -1600), (-1620, -1800), (-1620, -1400),
         (-950, -660), (-100, -760), (1020, -760), (1050, 200), (990, 600), (850, 670)),
    ]
    stage = replace(stone, wall="RAILEDGE", floor="STAGEFL", ceiling="UFCOFFR", ceiling_height=400)
    spec.area("Raised performance stage", box(-680, 590, 490, 870),
              replace(stage, floor_height=48))
    spec.area("Stage first step", box(-520, 530, 330, 560),
              replace(stage, ceiling="F_SKY1", ceiling_height=1536, floor_height=16))
    spec.area("Stage second step", box(-520, 560, 330, 590),
              replace(stage, ceiling="F_SKY1", ceiling_height=1536, floor_height=32))
    spec.cover("Stage rear backdrop", -100, 880, 1200, 40, height=400,
               surface=replace(stage, wall="STAGEBK"))
    for x in (-580, 400):
        spec.decorate(x, 720, "speaker")
    spec.decorate(-260, 690, "guitarist", angle=270)
    spec.decorate(40, 740, "drummer", angle=270)
    for x, y, w, d, height, sign in (
        (-2680, -215, 600, 580, 896, "SBILL1"),
        (1300, -50, 360, 500, 1152, "SBILL3"),
        (470, 980, 300, 300, 960, "SBILL4"),
    ):
        spec.cover("Surrounding billboard building", x, y, w, d, height=height,
                   surface=replace(stone, wall=sign))
    return spec


def nathan_phillips_square():
    stone = material("union_plaza", ceiling_height=1792)
    spec = VenueSpec(
        "E1M5", "Nathan Phillips Square", box(-2500, -2700, 2500, 2300),
        stone, (-2100, -2500), (2100, 1950),
        "Estimated 156 x 131 m civic-square envelope; pool, arches, pavilion "
        "and City Hall exterior arranged from official visitor descriptions. "
        "City Hall is a simplified exterior landmark, no invented interior.",
    )
    spec.area("Civic plaza", spec.footprint, stone)
    road = replace(stone, wall="ROADBED", floor="ASPHALT")
    spec.area("Queen Street roadway", box(-2500, -2580, 2500, -2180), road)
    spec.area("Queen Street north sidewalk", box(-2500, -2180, 2500, -1900), stone)
    spec.area("Queen Street pedestrian crossing", box(-2240, -2580, -1980, -2180),
              replace(road, floor="CROSSWLK"))
    spec.decorate(-1000, -2030, "hotdog_vendor", angle=270)
    spec.decorate(1000, -2030, "icecream_vendor", angle=270)
    spec.area("Reflecting pool / skating footprint", box(-1500, -1450, 1300, -300),
              replace(stone, floor="NPSICE"))
    spec.area("West pavilion", box(-2500, -500, -1650, 900),
              replace(stone, ceiling="UFCOFFR", ceiling_height=256))
    spec.cover("Pavilion skate rental facade", -2460, 200, 80, 900, height=256,
               surface=replace(stone, wall="SKATERNT", ceiling="UFCOFFR", ceiling_height=256))
    spec.area("City Hall forecourt", box(-1700, 900, 1900, 1700), stone)
    for x in (-1000, -100, 800):
        # Classic sectors cannot span a beam above walkable space. These paired
        # piers indicate the arches; their upper spans belong in the sky art.
        for y in (-1350, -400):
            spec.cover("Freedom Arch visible pier", x, y, 90, 130, height=512)
    spec.area("City Hall single cylindrical tower", ellipse(0, 1900, 660, 350),
              replace(stone, wall="CITYRIB", floor="CITYBASF", floor_height=1344), solid=True)
    spec.area("City Hall council chamber", ellipse(0, 1480, 400, 120),
              replace(stone, wall="CITYBASE", floor="CITYBASF", floor_height=192), solid=True)
    spec.area("Council chamber saucer roof", ellipse(0, 1480, 340, 95),
              replace(stone, wall="CITYBASE", floor="CITYBASF", floor_height=240), solid=True)
    spec.area("Rink snow edge south", box(-1500, -1474, 1300, -1450),
              replace(stone, floor="NPSSNOW", floor_height=8))
    spec.area("Rink snow edge north", box(-1500, -300, 1300, -276),
              replace(stone, floor="NPSSNOW", floor_height=8))
    for x in (-1512, 1312):
        spec.area("Rink snow edge side", box(x - 12, -1450, x + 12, -300),
                  replace(stone, floor="NPSSNOW", floor_height=8))
    for x, y, a in ((-1800, -900, 90), (1700, -900, 90), (-1100, 200, 0),
                    (900, 220, 0), (-400, 750, 0), (1500, 950, 90)):
        spec.cover("Civic event wall", x, y, 480, 140, angle=a)
    spec.cover("Central planter", 0, 300, 420, 400, height=160)
    for x, y in ((-2000, 100), (1800, -100), (-1300, 900), (600, 1200), (2100, 1300)):
        spec.encounter(x, y)
    spec.routes = [
        ((-2100, -2500), (-2100, -1560), (-2100, -1200), (-1500, -1700), (2100, -1700),
         (2100, -100), (2100, 1300), (2100, 1950)),
        ((-2100, -2500), (-2100, -1560), (-2200, -300), (-1400, -50), (-1400, 700),
         (0, 1200), (1100, 1200), (1800, 1400), (2100, 1400), (2100, 1950)),
    ]
    return spec


def rogers_centre():
    grass = Surface("STADWALL", "STADGRAS", "F_SKY1", 224, ceiling_height=768)
    dirt = replace(grass, floor="STADDIRT")
    concrete = material("union_concourse", ceiling_height=768)
    # Coordinates are anchored at home plate; the outfield is intentionally
    # asymmetric and follows the current published 328/368/400/359/328 distances.
    def polar(feet, degrees):
        r = feet * UNITS_PER_FOOT
        return round(r * math.cos(math.radians(degrees))), round(r * math.sin(math.radians(degrees)))
    field_points = [(0, 0), polar(328, 135), polar(368, 112.5), polar(400, 90),
                    polar(359, 67.5), polar(328, 45)]
    field_shape = Polygon(field_points)
    footprint = field_shape.buffer(600, join_style=2)
    footprint = unary_union((footprint, box(-1220, -430, -350, 160),
                             box(350, -430, 1220, 160)))
    spec = VenueSpec(
        "E1M6", "Rogers Centre", footprint, concrete, (0, -640), (0, 4230),
        "Playing-field anchors at 32 units/metre: 328 ft foul lines, 400 ft "
        "centre, 368/359 ft alleys. Foul territory, dugouts and lower-bowl "
        "circulation are simplified estimates. No official sports branding.",
        anchors={"foul_line_ft": 328, "left_alley_ft": 368, "centre_field_ft": 400,
                 "right_alley_ft": 359, "base_path_ft": 90},
    )
    spec.area("Complete playing field", field_shape, grass)
    diamond = Polygon([(0, 0), polar(90, 45), polar(90 * math.sqrt(2), 90), polar(90, 135)])
    spec.area("Infield diamond", diamond.buffer(120, join_style=2), dirt)
    spec.area("Infield grass", diamond.buffer(-120, join_style=2), grass)
    chalk = replace(grass, floor="SPORTWH")
    for angle in (45, 135):
        spec.area("Foul-line chalk", path([(0, 0), polar(328, angle)], 6), chalk)
    for point in ((0, 0), polar(90, 45), polar(90 * math.sqrt(2), 90), polar(90, 135)):
        x, y = point
        spec.area("Base marker", box(x - 15, y - 15, x + 15, y + 15), chalk)
    spec.area("Home plate circle", Point(0, 0).buffer(170, quad_segs=8), dirt)
    spec.area("Pitcher mound", Point(0, round(60.5 * UNITS_PER_FOOT)).buffer(90, quad_segs=8),
              replace(dirt, floor_height=8))
    spec.area("Left dugout approach", box(-1150, -400, -400, 120), concrete)
    spec.area("Right dugout approach", box(400, -400, 1150, 120), concrete)
    spec.area("Outfield lower-bowl circuit", path([polar(360, 140), polar(420, 112.5),
                                                  polar(435, 90), polar(411, 67.5), polar(360, 40)], 280),
              concrete)
    bunker = replace(grass, wall="PBTEAL", floor="PBTEALF")
    for side in (-1, 1):
        x = side * 775
        spec.area("Walk-in dugout interior", box(x - 345, -350, x + 345, 60),
                  replace(concrete, floor_height=-16, ceiling_height=160))
        spec.cover("Dugout protective lower wall", x, 72, 690, 24, height=72,
                   surface=replace(concrete, wall="PTFRAME"))
        spec.cover("Dugout back wall", x, -370, 730, 40, height=192,
                   surface=replace(concrete, wall="PTFRAME"))
        spec.cover("Dugout bench", x, -295, 540, 40, height=8,
                   surface=replace(concrete, wall="ZWCEDAR"))
    for x, y, a in ((-1100, 1500, 90), (1100, 1500, 90),
                    (-1650, 2300, 90), (1650, 2300, 90), (-900, 3000, 0), (900, 3000, 0),
                    (-550, 3650, 0), (550, 3650, 0)):
        spec.cover("Tournament lane bunker", x, y, 380, 140, angle=a, surface=bunker)
    spec.cover("Central tournament wedge", 0, 1950, 450, 450, angle=45,
               surface=replace(bunker, wall="PBORANGE", floor="PBORNGF"), height=192)
    # Static roster: pitcher and catcher face each other and never rotate;
    # basemen hold first, second and third; a batter waits in the box.
    spec.decorate(0, 590, "pitcher", angle=270)
    spec.decorate(0, -100, "catcher", angle=90)
    spec.decorate(52, 24, "batter", angle=180)
    first, second, third = polar(90, 45), polar(90 * math.sqrt(2), 90), polar(90, 135)
    spec.decorate(first[0] + 40, first[1] + 40, "baseman", angle=225)
    spec.decorate(second[0], second[1] + 50, "baseman", angle=270)
    spec.decorate(third[0] - 40, third[1] + 40, "baseman", angle=315)
    for x, y in ((-800, 1000), (800, 1000), (-1400, 2500), (1400, 2500),
                 (-450, 3100), (450, 3100), (0, 3800)):
        spec.encounter(x, y)
    spec.routes = [
        ((0, -640), (0, -300), (-300, -250), (-300, 0), (-300, 200),
         (-1600, 1000), (-2200, 1800),
         (-2300, 2800), (-1500, 3650), (-1000, 4000), (0, 4230)),
        ((0, -640), (0, -300), (300, -250), (300, 0), (300, 200),
         (1600, 1000), (2200, 1800),
         (2300, 2800), (1500, 3650), (1000, 4000), (0, 4230)),
    ]
    from venue_scenery import FAN_KINDS
    clearances = unary_union([
        *(LineString(route).buffer(96, join_style=2) for route in spec.routes),
        box(-1330, -510, 1330, 250), Point(spec.exit_center).buffer(250),
    ])
    for row in range(4):
        outer = footprint.buffer(-row * 90, join_style=2)
        inner = footprint.buffer(-(row + 1) * 90, join_style=2)
        seating = outer.difference(inner).difference(clearances)
        spec.area(f"Ascending seating row {4 - row}", seating,
                  replace(grass, wall="RINKSEAT", floor="RINKSEAF",
                          floor_height=240 - row * 48), solid=True)
        centerline = footprint.buffer(-(row * 90 + 45), join_style=2).boundary
        for index in range(math.floor(centerline.length / 170)):
            point = centerline.interpolate(index * 170)
            x, y = round(point.x), round(point.y)
            if not seating.covers(Point(x, y).buffer(12)):
                continue
            angle = round(math.degrees(math.atan2(1800 - y, -x))) % 360
            spec.decorate(x, y, FAN_KINDS[(index + row * 3) % len(FAN_KINDS)],
                          angle=angle)
    return spec


def scotiabank_arena():
    ice = Surface("RINKBRDS", "RINKICE", "RINKROOF", 232, ceiling_height=640)
    concourse = material("union_concourse", ceiling_height=640)
    # Standard NHL 200 x 85 ft, 28-ft rounded-corner radius; model long axis N-S.
    hx, hy, radius = (round(value * UNITS_PER_FOOT) for value in (42.5, 100, 28))
    rink = box(-hx + radius, -hy + radius, hx - radius, hy - radius).buffer(radius, quad_segs=6)
    footprint = box(-1400, -1900, 1400, 1900)
    spec = VenueSpec(
        "E1M7", "Scotiabank Arena", footprint, concourse, (350, -1660), (0, 1650),
        "Standard NHL rink 200 x 85 ft with 28 ft corner radius at "
        "32 units/metre. Lower bowl, benches and concourse estimated and "
        "flattened. No skating/slip mechanic or licensed branding.",
        anchors={"rink_length_ft": 200, "rink_width_ft": 85, "corner_radius_ft": 28},
    )
    tunnels = unary_union([box(-180, -1840, 180, -900),
                           box(250, -1840, 450, -760),
                           box(-180, 900, 180, 1840)])
    spec.area("Spectator-only upper bowl", footprint,
              replace(ice, wall="RINKSEAT", floor="RINKSEAF", floor_height=320), solid=True)
    for row in reversed(range(5)):
        bowl = rink.buffer(24 + (row + 1) * 110, quad_segs=6).difference(tunnels)
        spec.area(f"Ascending seating row {row + 1}", bowl,
                  replace(ice, wall="RINKSEAT", floor="RINKSEAF",
                          floor_height=96 + row * 48), solid=True)
    spec.area("Rink perimeter hockey boards", rink.buffer(24, quad_segs=6).difference(tunnels),
              replace(ice, floor_height=64), solid=True)
    spec.area("Complete hockey rink", rink, ice)
    # Players can step through board gates beside both blue lines.
    for side in (-1, 1):
        for line_y in (-round(25 * UNITS_PER_FOOT), round(25 * UNITS_PER_FOOT)):
            x0, x1 = sorted((side * (hx - 30), side * (hx + 118)))
            spec.area("Blue-line board gate", box(x0, line_y - 40, x1, line_y + 40),
                      replace(concourse, ceiling="RINKROOF"))
    red, blue = replace(ice, floor="SPORTRED"), replace(ice, floor="SPORTBLU")
    spec.area("Centre red line", box(-hx, -6, hx, 6).intersection(rink), red)
    for y in (-round(25 * UNITS_PER_FOOT), round(25 * UNITS_PER_FOOT)):
        spec.area("Zone blue line", box(-hx, y - 6, hx, y + 6).intersection(rink), blue)
    circle_radius = 15 * UNITS_PER_FOOT
    spec.area("Centre faceoff circle", Point(0, 0).buffer(circle_radius, quad_segs=12)
              .boundary.buffer(4), blue)
    for side in (-1, 1):
        y = round(side * 69 * UNITS_PER_FOOT)
        for x in (-round(22 * UNITS_PER_FOOT), round(22 * UNITS_PER_FOOT)):
            spec.area("End-zone faceoff circle", Point(x, y).buffer(circle_radius, quad_segs=12)
                      .boundary.buffer(4), red)
            spec.area("Faceoff dot", Point(x, y).buffer(10, quad_segs=4), red)
    # A static scoreboard hangs from the roof directly above centre ice.
    spec.area("Centre-ice scoreboard", box(-120, -84, 120, 84),
              replace(ice, wall="VSCOR", ceiling="STAGEFL", ceiling_height=544))
    spec.area("South rink tunnel", box(-180, -1840, 180, -900), concourse)
    spec.area("East rink entrance tunnel", box(250, -1840, 450, -760), concourse)
    spec.area("North rink tunnel", box(-180, 900, 180, 1840), concourse)
    spec.area("Continuous walkable rinkside bear route",
              rink.buffer(116, quad_segs=6).difference(rink.buffer(42, quad_segs=6)),
              replace(concourse, wall="RINKBRDS", ceiling="RINKROOF"))
    for y in (-650, -360, 360, 650):
        spec.cover("Rink padded tournament barrier", 0, y, 240, 80,
                   surface=replace(ice, wall="PBTEAL", floor="PBTEALF"))
    spec.decorate(0, 0, "referee", angle=270)
    spec.decorate(24, 64, "hockey_blue", angle=249)
    spec.decorate(-24, -64, "hockey_red", angle=69)
    from venue_scenery import FAN_KINDS
    for row in range(4):
        centerline = rink.buffer(185 + row * 110, quad_segs=6).boundary
        for index in range(math.floor(centerline.length / 145)):
            point = centerline.interpolate(index * 145)
            if tunnels.buffer(80).covers(point) or not footprint.buffer(-40).covers(point):
                continue
            x, y = round(point.x), round(point.y)
            spec.decorate(x, y, FAN_KINDS[(index + row * 3) % len(FAN_KINDS)],
                          angle=round(math.degrees(math.atan2(-y, -x))))
    for x, y in ((-240, -500), (240, -500), (-240, 500), (240, 500), (0, 1150)):
        spec.encounter(x, y, roles=("gunner", "secondary"))
    spec.encounter(0, 850, roles=("primary",))
    spec.routes = [
        ((350, -1660), (350, -900), (-250, -750), (-300, -450),
         (-300, 450), (-250, 750), (0, 1000), (0, 1650)),
        ((350, -1660), (350, -900), (250, -750), (300, -450),
         (300, 450), (250, 750), (0, 1000), (0, 1650)),
    ]
    return spec


def queens_park():
    grass = material("zoo_meadow", ceiling_height=1792)
    trail = material("union_plaza", ceiling_height=1792)
    footprint = ellipse(0, 0, 2450, 3900)
    spec = VenueSpec(
        "E1M8", "Queen's Park", footprint, grass, (0, -3550), (0, 3500),
        "Estimated 153 x 244 m game oval preserves north park / southern "
        "legislative-ground relationship. Long walks compressed; building "
        "exterior only. Monuments are context, not destructible objectives.",
    )
    spec.area("North park lawns", box(-2400, 500, 2400, 3900), grass)
    spec.area("Southern legislative grounds", box(-2400, -3900, 2400, 500), grass)
    oval = ellipse(0, 500, 1750, 2700).boundary.buffer(150, join_style=2)
    spec.area("Oval public walk", oval, trail)
    for title, points in (
        ("Southern approach", [(0, -3800), (0, -1900)]),
        ("West legislative path", [(-1900, -2200), (-1900, 600), (0, 2900)]),
        ("East legislative path", [(1900, -2200), (1900, 600), (0, 2900)]),
        ("North cross path", [(-2100, 1600), (2100, 1600)]),
        ("Northern approach", [(0, 1500), (0, 3800)]),
    ):
        spec.area(title, path(points, 230), trail)
    legislature = unary_union([box(-1200, -1700, 1200, -800), box(-1550, -1750, -850, -500),
                               box(850, -1750, 1550, -500)])
    spec.area("Legislative building exterior", legislature,
              Surface("QWINDOW", "RFMARBL", "F_SKY1", 208, 640, 1792), solid=True)
    facade = Surface("QWINDOW", "QROOFF", "F_SKY1", 208, 864, 1792)
    for x in (-1110, 1110):
        spec.cover("Legislature stone tower", x, -1370, 300, 480, height=960, surface=facade)
        spec.cover("Legislature copper dome", x, -1370, 224, 390, height=1088,
                   surface=replace(facade, wall="QROOF"))
        spec.cover("Legislature dome crown", x, -1370, 112, 220, height=1152,
                   surface=replace(facade, wall="QROOF"))
    spec.cover("Legislature central entrance", 0, -1560, 620, 280, height=800,
               surface=replace(facade, wall="QENTRY"))
    spec.cover("Legislature slate roof", 0, -1240, 1500, 400, height=832,
               surface=replace(facade, wall="QROOF"))
    spec.cover("Legislature central gable", 0, -1240, 800, 220, height=944,
               surface=replace(facade, wall="QROOF"))
    timber = replace(grass, wall="ZWCEDAR", floor="ZFEARTH")
    for x, y, a in ((-1200, 400, 20), (1200, 400, -20), (-650, 1800, 0),
                    (650, 1800, 0), (-1300, -2700, 0), (1300, -2700, 0),
                    (-500, 2800, 90), (500, 2800, 90)):
        spec.cover("Temporary park timber shield", x, y, 360, 140, angle=a, surface=timber)
    for x, y in ((-700, 700), (700, 700), (-1800, 1200), (1800, 1200),
                 (-900, 2400), (900, 2400), (0, -2500)):
        if y == -2500:
            spec.cover("Southern stone planter", x, y, 300, 180, height=128,
                       surface=replace(grass, wall="QSTONE"))
        else:
            spec.cover("Solid trunk cluster", x, y, 180, 180, height=320, surface=timber)
    for x, y in ((-1800, -1800), (1800, -1800), (-1600, 100), (1600, 100),
                 (-1000, 2000), (1000, 2000), (0, 3100)):
        spec.encounter(x, y)
    spec.routes = [
        ((0, -3550), (-1000, -3100), (-1550, -2850), (-1850, -2300),
         (-1900, 600), (-2100, 1100), (-1900, 1850), (-1400, 2700), (0, 3400), (0, 3500)),
        ((0, -3550), (1000, -3100), (1550, -2850), (1850, -2300),
         (1900, 600), (2100, 1100), (1900, 1850), (1400, 2700), (0, 3400), (0, 3500)),
    ]
    for index, (x, y) in enumerate((
        (-420, -2800), (420, -2800), (-940, -2400), (940, -2400),
        (-1450, -2100), (1450, -2100), (-2100, -800), (2100, -800),
        (-2250, 100), (2250, 100), (-1350, 800), (1350, 800),
        (-450, 1000), (450, 1000), (-850, 1300), (850, 1300),
        (-1450, 1900), (1450, 1900), (-300, 2150), (300, 2150),
        (-1000, 2800), (1000, 2800), (-600, 3150), (600, 3150),
        (-1100, 600), (1100, 600), (-1500, 2200), (1500, 2200),
    )):
        spec.decorate(x, y, ("maple", "oak", "pine")[index % 3])
    return spec


def toronto_islands():
    grass = material("zoo_meadow", ceiling_height=640)
    timber = material("zoo_habitat", ceiling_height=640)
    trail = material("zoo_path", ceiling_height=640)
    hanlan = ellipse(-3400, -100, 1250, 2400)
    centre = ellipse(0, -200, 2100, 1800)
    wards = affinity.rotate(ellipse(3450, 400, 1900, 850), 15)
    bridges = [path([(-2500, 300), (-1700, 300)], 260),
               path([(1700, 500), (2500, 500)], 260),
               path([(-2500, -700), (-1600, -700)], 260),
               path([(1600, -400), (2500, -400)], 260)]
    footprint = unary_union([hanlan, centre, wards, *bridges])
    # Small channels are represented by unwalkable holes and visible shore walls.
    spec = VenueSpec(
        "E1M9", "Toronto Islands", footprint, grass, (-3400, 1900), (4750, 700),
        "Compressed west-to-east Hanlan's / Centre / Ward's districts with "
        "two bridge routes per channel. Shoreline is a deliberate game-scale "
        "silhouette, not licensed geodata. Airport/private interiors omitted.",
    )
    for title, shape in (("Hanlan's Point", hanlan), ("Centre Island", centre), ("Ward's Island", wards)):
        spec.area(title, shape, grass)
    for index, bridge in enumerate(bridges, 1):
        spec.area(f"Public bridge {index}", bridge, replace(timber, floor="ZFROOF"))
    spec.area("Hanlan's ferry node", box(-3800, 1400, -3000, 2250), trail)
    spec.area("Centre ferry node", box(-550, 1000, 550, 1700), trail)
    spec.area("Ward's ferry node", box(4300, 400, 5150, 1050), trail)
    spec.area("Centre beach edge", path([(-1500, -1100), (0, -1650), (1400, -1100)], 300),
              replace(timber, floor="BEACHSND"))
    spec.area("Hanlan's public lakeshore", path([(-4100, 900), (-4300, -700), (-3550, -2000)], 270),
              replace(timber, floor="BEACHSND"))
    spec.area("Centre avenue", path([(0, 1500), (0, -1300)], 270), trail)
    for x, y, a in ((-3650, 900, 0), (-3200, -600, 90), (-2900, 900, 90),
                    (-1100, 300, 90), (700, 600, 0), (-600, -800, 0),
                    (1100, -750, 90), (2900, 750, 0), (3400, -100, 90), (4100, 450, 0)):
        spec.cover("Island timber event screen", x, y, 380, 140, angle=a, surface=timber)
    for x, y in ((-3400, 300), (-400, 300), (3300, 500)):
        spec.cover("Boathouse-style equipment shelter", x, y, 520, 360,
                   height=256, surface=timber)
    for x, y in ((-3400, 1100), (-3400, -900), (-1400, 700), (-1000, -600),
                 (1000, 900), (1100, -1000), (2900, 300), (4000, 800)):
        spec.encounter(x, y)
    spec.routes = [
        ((-3400, 1900), (-2700, 1100), (-2650, 700), (-2500, 300), (-1700, 300),
         (-1400, 800), (1500, 800), (1700, 500), (2500, 500),
         (2800, 200), (4400, 200), (4500, 700), (4750, 700)),
        ((-3400, 1900), (-4000, 900), (-4000, -1000), (-2700, -1000), (-2500, -700), (-1600, -700),
         (-1300, -1200), (1300, -1200), (1600, -400), (2500, -400),
         (3000, 200), (4400, 200), (4500, 700), (4750, 700)),
    ]
    spec.playable_outline = spec.footprint
    spec.footprint = spec.footprint.buffer(640, join_style=2)
    spec.area("Island lake basin", spec.footprint.difference(spec.playable_outline),
              replace(grass, floor="ISLLAKE", floor_height=-24))
    return spec


def venue_specs():
    original = {spec.name: spec for spec in (factory() for factory in (
        union_station, royal_ontario_museum, toronto_zoo, sankofa_square,
        nathan_phillips_square, rogers_centre, scotiabank_arena, queens_park, toronto_islands,
    ))}
    specs = tuple(replace(original[stop.source], name=f"E1M{i}")
                  for i, stop in enumerate(STOPS, 1))
    for spec in specs:
        venue = spec.compile()
        boundary = spec.footprint.difference(spec.footprint.buffer(-64))
        if spec.title == "Toronto Islands":
            # Adjacent sky ceilings hide the upper wall. The outside wall ends
            # below eye height; the inner water edge is explicitly blocking.
            spec.area("Island open water horizon", boundary,
                      replace(spec.base, floor="ISLLAKE", floor_height=-64, ceiling_height=0))
        for polygon, _, region in venue.faces:
            if spec.title == "Toronto Islands":
                continue
            if region.solid or region.surface.ceiling != "F_SKY1":
                continue
            edge = polygon.intersection(boundary)
            if edge.is_empty or edge.area < 1:
                continue
            # Adjacent sky ceilings hide their height difference in classic
            # Doom, leaving a human-scale perimeter rather than a giant box.
            spec.area("Low outdoor perimeter", edge,
                      replace(region.surface, ceiling_height=region.surface.floor_height + 160))
        routes = unary_union([LineString(route) for route in spec.routes])
        choices = []
        for polygon, _, region in venue.faces:
            if region.solid or region.title in {"Island lake basin", "Island open water horizon"}:
                continue
            inset = polygon.buffer(-150)
            if inset.is_empty:
                continue
            point = inset.representative_point()
            if point.distance(Point(spec.start)) < 500 or point.distance(Point(spec.exit_center)) < 300:
                continue
            choices.append((point.distance(routes), point.x, point.y, region.surface))
        if spec.title == "Scotiabank Arena":
            cache = box(138, -112, 362, 112)
            if not venue.walkable.covers(cache):
                raise ValueError(f"{spec.name}: rink-side supply cache is obstructed")
            rink_surface = next(region.surface for region in spec.regions
                                if region.title == "Complete hockey rink")
            choices = [(0, 250, 0, rink_surface)]
        if not choices:
            raise ValueError(f"{spec.name}: no reachable side-route supply cache")
        _, x, y, surface = max(choices, key=lambda item: item[:3])
        # The cache is an open, brighter supply alcove: the campaign has no
        # hidden areas, so it no longer carries the "secret" sector special.
        spec.area("Optional supply cache", box(round(x) - 112, round(y) - 112,
                                              round(x) + 112, round(y) + 112),
                  replace(surface, light=min(255, surface.light + 16)))
        x, y = spec.exit_center
        checkpoint = next((box(x - half, y - half, x + half, y + half)
                           for half in (144, 112, 96, 80, 64)
                           if (venue.walkable.covers(box(x - half, y - half, x + half, y + half))
                               and venue.clear_at(x, y - half - 40, 34))), None)
        if checkpoint is None:
            raise ValueError(f"{spec.name}: exit checkpoint intersects solid cover")
        face = next(region for polygon, _, region in venue.faces
                    if polygon.covers(Point(x, y)))
        spec.area("Low sky checkpoint approach",
                  checkpoint.buffer(64, join_style=2).intersection(venue.walkable)
                  .intersection(spec.footprint.buffer(-64)),
                  replace(face.surface, ceiling_height=288))
        spec.area("Blue-key exit checkpoint", checkpoint,
                  replace(spec.base, wall="PBKEYDR", ceiling="PBTEALF",
                          floor_height=0, ceiling_height=0))
        spec.area("Exit checkpoint interior", checkpoint.buffer(-32, join_style=2), spec.base)
    return specs
