import os
import re
import struct
import subprocess
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory


MAP_LUMPS = ("THINGS", "LINEDEFS", "SIDEDEFS", "VERTEXES", "SEGS",
             "SSECTORS", "NODES", "SECTORS", "REJECT", "BLOCKMAP")
from project_paths import ROOT

NODEBUILDER = ROOT / "tools" / "zdbsp" / "zdbsp.exe"


def resource_name(value):
    encoded = value.encode("ascii")
    if not encoded or len(encoded) > 8:
        raise ValueError(f"Invalid Doom resource name: {value}")
    return encoded


def read_wad(path):
    resolved = Path(path).resolve()
    stat = resolved.stat()
    key = (str(resolved), stat.st_mtime_ns, stat.st_size)
    cached = _WAD_CACHE.get(key)
    if cached is None:
        cached = tuple(_read_wad_uncached(resolved))
        _WAD_CACHE.clear()  # one WAD at a time; parses are large
        _WAD_CACHE[key] = cached
    # Callers may extend/filter the list; hand each one a fresh copy.
    return list(cached)


_WAD_CACHE = {}


def _read_wad_uncached(path):
    data = Path(path).read_bytes()
    if len(data) < 12:
        raise ValueError(f"{path}: truncated WAD header")
    signature, count, directory = struct.unpack_from("<4sii", data)
    if signature not in (b"PWAD", b"IWAD") or count < 0 or directory < 12 or directory + count * 16 != len(data):
        raise ValueError(f"{path}: invalid WAD directory")
    lumps = []
    for index in range(count):
        offset, size, name = struct.unpack_from("<ii8s", data, directory + index * 16)
        if size < 0 or offset < 0 or (size and offset < 12) or offset + size > directory:
            raise ValueError(f"{path}: invalid lump bounds")
        lumps.append((name.rstrip(b"\0").decode("ascii"), data[offset:offset + size]))
    return lumps


def write_wad(path, lumps):
    data = bytearray(b"PWAD" + struct.pack("<ii", len(lumps), 0))
    directory = bytearray()
    for name, payload in lumps:
        encoded = resource_name(name)
        directory.extend(struct.pack("<ii8s", len(data), len(payload), encoded))
        data.extend(payload)
    struct.pack_into("<i", data, 8, len(data))
    Path(path).write_bytes(data + directory)


def build_nodes(lumps, executable=NODEBUILDER):
    if not Path(executable).is_file():
        raise FileNotFoundError(f"Missing ZDBSP node builder: {executable}; see tools\\nodebuilder.json")
    with TemporaryDirectory(prefix="toronto-nodes-") as directory:
        source, target = Path(directory) / "source.wad", Path(directory) / "nodes.wad"
        write_wad(source, lumps)
        result = subprocess.run(
            [str(executable), "-q", "-R", "-t", "-w", "-o", str(target), str(source)],
            capture_output=True, text=True, check=True,
        )
        diagnostics = [line.strip() for line in result.stderr.splitlines()
                       if line.strip() and not re.fullmatch(r"BSP:\s+\d+\.\d+%", line.strip())]
        diagnostics.extend(line.strip() for line in result.stdout.splitlines()
                           if re.search(r"\b(?:warning|error)\b", line, re.IGNORECASE))
        if diagnostics:
            raise ValueError(f"ZDBSP reported an error: {'; '.join(diagnostics)}")
        if not target.is_file():
            raise ValueError(f"ZDBSP did not produce output: {result.stdout}")
        return read_wad(target)


@dataclass(frozen=True)
class Sector:
    floor: int
    ceiling: int
    floor_texture: str
    ceiling_texture: str
    light: int = 208
    special: int = 0
    tag: int = 0

    def pack(self):
        if self.floor > self.ceiling:
            raise ValueError("Sector floor exceeds ceiling")
        return struct.pack("<hh8s8shhh", self.floor, self.ceiling,
                           resource_name(self.floor_texture), resource_name(self.ceiling_texture),
                           self.light, self.special, self.tag)


class Geometry:
    def __init__(self, name):
        self.name = name
        self.vertices = []
        self.vertex_ids = {}
        self.sides = []
        self.lines = []
        self.sectors = []
        self.things = []

    def sector(self, value):
        value.pack()
        self.sectors.append(value)
        return len(self.sectors) - 1

    def vertex(self, point):
        point = tuple(point)
        if len(point) != 2 or any(not isinstance(value, int) or not -32768 <= value <= 32767 for value in point):
            raise ValueError(f"Invalid classic Doom vertex: {point}")
        if point not in self.vertex_ids:
            self.vertex_ids[point] = len(self.vertices)
            self.vertices.append(point)
        return self.vertex_ids[point]

    def side(self, sector, middle="-", upper="-", lower="-", offset=0):
        if not 0 <= sector < len(self.sectors):
            raise ValueError("Sidedef references missing sector")
        self.sides.append(struct.pack("<hh8s8s8sh", offset, 0, resource_name(upper),
                                      resource_name(lower), resource_name(middle), sector))
        return len(self.sides) - 1

    def line(self, a, b, front, texture, back=None, special=0, tag=0, blocking=False):
        if a == b:
            raise ValueError("Zero-length linedef")
        front_side = self.side(front, texture if back is None else "-", texture, texture)
        back_side = -1 if back is None else self.side(back, "-", texture, texture)
        flags = (1 if back is None or blocking else 0) | (4 if back is not None else 0)
        self.lines.append((self.vertex(a), self.vertex(b), flags, special, tag, front_side, back_side))

    def loop(self, points, front, texture, back=None):
        if len(points) < 3:
            raise ValueError("Sector loop needs at least three vertices")
        for a, b in zip(points, points[1:] + points[:1]):
            self.line(a, b, front, texture, back)

    def thing(self, x, y, kind, angle=0, skills=7):
        if not skills & 7:
            raise ValueError("Thing must appear on at least one skill")
        if any(not -32768 <= value <= 32767 for value in (x, y, kind)):
            raise ValueError("Thing lies outside classic Doom range")
        self.things.append((x, y, angle, kind, skills))

    def lumps(self):
        if not self.sectors or not self.lines or not self.things:
            raise ValueError(f"{self.name}: incomplete map geometry")
        if max(len(self.vertices), len(self.sides), len(self.lines), len(self.sectors)) >= 32767:
            raise ValueError(f"{self.name}: exceeds conservative classic map index limits")
        data = {
            "THINGS": b"".join(struct.pack("<5h", *thing) for thing in self.things),
            "LINEDEFS": b"".join(struct.pack("<7h", *line) for line in self.lines),
            "SIDEDEFS": b"".join(self.sides),
            "VERTEXES": b"".join(struct.pack("<2h", *point) for point in self.vertices),
            "SECTORS": b"".join(sector.pack() for sector in self.sectors),
        }
        return [(self.name, b"")] + [(name, data.get(name, b"")) for name in MAP_LUMPS]


def replace_validated(path, lumps, validator):
    path = Path(path)
    staged = path.with_suffix(".staged.wad")
    try:
        write_wad(staged, lumps)
        result = validator(staged)
        os.replace(staged, path)
        return result
    finally:
        if staged.exists():
            staged.unlink()
