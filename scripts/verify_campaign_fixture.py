import argparse
from pathlib import Path

from doom_geometry import Geometry, Sector, build_nodes, write_wad


def fixture():
    lumps = []
    for number in range(1, 10):
        geometry = Geometry(f"E1M{number}")
        room = geometry.sector(Sector(0, 256, "FLOOR4_8", "CEIL3_5"))
        geometry.loop([(-128, -128), (-128, 384), (128, 384), (128, -128)], room, "STARTAN3")
        geometry.line((-128, 0), (128, 0), room, "STARTAN3", room, special=52)
        geometry.thing(0, -64, 1, angle=90)
        lumps.extend(geometry.lumps())
    lumps = build_nodes(lumps)
    mapinfo = []
    for number in range(1, 10):
        fields = [f'levelname = "Routing proof {number}"', "bossaction = clear",
                  "nointermission = false", f"endgame = {'true' if number == 9 else 'false'}"]
        if number < 9:
            fields += [f'next = "E1M{number + 1}"', f'nextsecret = "E1M{number + 1}"']
        mapinfo.append(f"map E1M{number}\n{{\n" + "\n".join(fields) + "\n}\n")
    lumps.append(("UMAPINFO", "\n".join(mapinfo).encode("ascii")))
    # Deterministic forward movement and alternating attack edges advance intermissions.
    demo = bytearray((109, 2, 1, 8, 0, 0, 0, 1, 0, 1, 0, 0, 0))
    for tic in range(1800):
        demo.extend((50, 0, 0, 1 if tic % 70 < 35 else 0))
    demo.append(128)
    lumps.append(("ROUTEDEM", bytes(demo)))
    return lumps


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build a separate KEX E1M8-to-E1M9 compatibility proof, not a release map.")
    parser.add_argument("output", type=Path)
    arguments = parser.parse_args()
    write_wad(arguments.output, fixture())
    print(arguments.output)
