from dataclasses import replace

from toronto_enemies import ALL_ENEMIES, SiteEnemy
from campaign_order import SOURCE_TO_SLOT


CAMPAIGN_DIMENSIONS = {
    "POSS": (56, 20), "DRON": (56, 22), "DINO": (128, 34),
    "BEAR": (104, 34), "PIGE": (40, 16), "ARMR": (88, 30),
    "WOLF": (48, 24), "BVER": (64, 24), "RFOX": (54, 20),
    "GOOS": (50, 20), "CHIP": (30, 12), "BJAY": (38, 14),
    "GHOG": (66, 26), "SOWL": (48, 18), "WOLV": (76, 28),
    "BLSQ": (34, 12), "STAG": (108, 34), "SWAN": (54, 22),
    "OTTR": (52, 20),
}


# Existing actors and sound slots remain unchanged; new types use disjoint
# DEHEXTRA allocations, including its DSFRE000..DSFRE047 sound namespace.
ROLES = (
    ("E1M4", "Beaver engineer", "BVER", "beaver", 94, 32, 160, 7, "SPosAttack", (13, 10, 13)),
    ("E1M4", "Urban red fox", "RFOX", "fox", 74, 24, 70, 14, "PosAttack", (4, 4, 5)),
    ("E1M5", "Armoured Canada goose", "GOOS", "goose", 88, 30, 140, 8, "SPosAttack", (12, 10, 12)),
    ("E1M5", "Chipmunk", "CHIP", "chipmunk", 58, 18, 25, 14, "PosAttack", (5, 5, 6)),
    ("E1M6", "Blue jay", "BJAY", "bluejay", 70, 22, 65, 12, "PosAttack", (4, 4, 5)),
    ("E1M6", "Groundhog catcher", "GHOG", "groundhog", 98, 34, 200, 6, "SPosAttack", (14, 12, 16)),
    ("E1M7", "Snowy owl", "SOWL", "owl", 82, 26, 100, 10, "SPosAttack", (9, 8, 10)),
    ("E1M7", "Wolverine", "WOLV", "wolverine", 102, 34, 230, 8, "SPosAttack", (12, 10, 14)),
    ("E1M8", "Black squirrel", "BLSQ", "squirrel", 60, 18, 35, 16, "PosAttack", (3, 3, 5)),
    ("E1M8", "Armoured stag", "STAG", "stag", 110, 34, 260, 6, "SPosAttack", (16, 12, 16)),
    ("E1M9", "Swan", "SWAN", "swan", 86, 28, 120, 10, "SPosAttack", (10, 9, 10)),
    ("E1M9", "River otter", "OTTR", "otter", 76, 24, 85, 12, "PosAttack", (6, 5, 6)),
)

_NEW_ENEMIES = tuple(
    SiteEnemy(map_name, title, prefix, 155 + i, 15007 + i, 206 + i, 1600 + 40 * i,
              height, radius, health, speed, tuple(range(500 + i * 4, 504 + i * 4)), attack, tics)
    for i, (map_name, title, prefix, _, height, radius, health, speed, attack, tics) in enumerate(ROLES)
)
CAMPAIGN_ENEMIES = tuple(
    replace(enemy, map_name=SOURCE_TO_SLOT[enemy.map_name],
            height=CAMPAIGN_DIMENSIONS[enemy.prefix][0],
            radius=CAMPAIGN_DIMENSIONS[enemy.prefix][1],
            health=180 if enemy.prefix == "DINO" else enemy.health)
    for enemy in ALL_ENEMIES + _NEW_ENEMIES
)
NEW_ENEMIES = CAMPAIGN_ENEMIES[len(ALL_ENEMIES):]
NEW_ANIMATIONS = tuple(
    (prefix, f"npc_{slug}_actions.png", 4, tuple(range(16)), ())
    for _, _, prefix, slug, *_ in ROLES
)
NEW_ATTACK_SHEETS = (
    ("npc_attacks_squares.png", ("BVER", "RFOX", "GOOS", "CHIP")),
    ("npc_attacks_sports.png", ("BJAY", "GHOG", "SOWL", "WOLV")),
    ("npc_attacks_parks.png", ("BLSQ", "STAG", "SWAN", "OTTR")),
)


def map_enemies(map_name):
    enemies = tuple(enemy for enemy in CAMPAIGN_ENEMIES if enemy.map_name == map_name)
    if len(enemies) != 2:
        raise ValueError(f"{map_name}: expected two exclusive venue opponents")
    return enemies
