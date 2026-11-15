from collections import defaultdict
from dataclasses import dataclass

from shapely import set_precision, union_all
from shapely.geometry import LineString, Point, Polygon
from shapely.geometry.base import BaseGeometry
from shapely.geometry.polygon import orient
from shapely.ops import polygonize, unary_union

from doom_geometry import Geometry, Sector


@dataclass(frozen=True)
class Surface:
    wall: str
    floor: str
    ceiling: str
    light: int = 208
    floor_height: int = 0
    ceiling_height: int = 384
    special: int = 0


@dataclass(frozen=True)
class Region:
    title: str
    polygon: BaseGeometry
    surface: Surface
    solid: bool = False


@dataclass
class CompiledVenue:
    geometry: Geometry
    faces: list[tuple[Polygon, int, Region]]
    regions: list[Region]
    walkable: BaseGeometry
    solids: BaseGeometry

    def clear_at(self, x, y, radius=16):
        return self.walkable.covers(Point(x, y).buffer(radius, quad_segs=8))

    def sector_at(self, x, y):
        point = Point(x, y)
        matches = [sector for polygon, sector, _ in self.faces if polygon.covers(point)]
        if not matches:
            raise ValueError(f"{self.geometry.name}: point outside map: {(x, y)}")
        return matches[0]


def compile_venue(name, footprint, base, regions):
    footprint = set_precision(footprint, 1)
    if footprint.is_empty or not footprint.is_valid or footprint.geom_type != "Polygon":
        raise ValueError(f"{name}: venue footprint must be one connected valid polygon")
    layers = [Region("Public grounds", footprint, base)]
    for region in regions:
        shape = set_precision(region.polygon.intersection(footprint), 1)
        if shape.is_empty:
            raise ValueError(f"{name}: region outside footprint: {region.title}")
        if not shape.is_valid:
            raise ValueError(f"{name}: invalid region: {region.title}")
        layers.append(Region(region.title, shape, region.surface, region.solid))
    boundaries = union_all([region.polygon.boundary for region in layers], grid_size=1)
    geometry = Geometry(name)
    faces = []
    sectors = {}
    edges = defaultdict(list)
    for face in polygonize(boundaries):
        point = face.representative_point()
        if not footprint.covers(point):
            continue
        region = next(region for region in reversed(layers) if region.polygon.covers(point))
        surface = region.surface
        if surface not in sectors:
            sectors[surface] = geometry.sector(Sector(
                surface.floor_height, surface.ceiling_height,
                surface.floor, surface.ceiling, surface.light, surface.special,
            ))
        sector = sectors[surface]
        face = orient(face, sign=-1)
        faces.append((face, sector, region))
        for ring in (face.exterior, *face.interiors):
            points = [(round(x), round(y)) for x, y in ring.coords]
            for a, b in zip(points, points[1:]):
                if a == b:
                    raise ValueError(f"{name}: collapsed polygon edge")
                edges[tuple(sorted((a, b)))].append((a, b, sector, surface.wall))
    for key, owners in edges.items():
        if len(owners) > 2:
            raise ValueError(f"{name}: non-manifold sector edge: {key}")
        a, b, front, texture = owners[0]
        if len(owners) == 1:
            geometry.line(a, b, front, texture)
        else:
            other_a, other_b, back, other_texture = owners[1]
            if (other_a, other_b) != (b, a):
                raise ValueError(f"{name}: shared sector edge has inconsistent winding")
            if front != back:
                # Raised solid cover uses its own material on the exposed lower wall.
                if geometry.sectors[back].floor > geometry.sectors[front].floor:
                    texture = other_texture
                geometry.line(a, b, front, texture, back)
    solids = unary_union([polygon for polygon, _, region in faces if region.solid])
    walkable = footprint.difference(solids)
    if walkable.geom_type != "Polygon":
        raise ValueError(f"{name}: cover disconnected the playable public grounds")
    return CompiledVenue(geometry, faces, layers, walkable, solids)


def add_exit(venue, a, b):
    midpoint = LineString((a, b)).interpolate(0.5, normalized=True)
    sector = venue.sector_at(midpoint.x, midpoint.y)
    if not venue.walkable.covers(LineString((a, b))):
        raise ValueError(f"{venue.geometry.name}: exit crosses solid cover")
    venue.geometry.line(a, b, sector, "-", sector, special=52)
