from dataclasses import dataclass


@dataclass(frozen=True)
class SiteEnemy:
    map_name: str
    title: str
    prefix: str
    thing: int
    doomednum: int
    sprite: int
    state: int
    height: int
    radius: int
    health: int
    speed: int
    sounds: tuple[int, int, int, int]
    attack: str = "SPosAttack"
    attack_tics: tuple[int, int, int] = (10, 10, 10)


SITE_ENEMIES = (
    SiteEnemy("E1M1", "Corrupted transit drone", "DRON", 3, 9, 202, 1300, 72, 24, 60, 8, (42, 28, 65, 76)),
    SiteEnemy("E1M2", "Dinosaur skeleton", "DINO", 150, 15002, 200, 1340, 84, 28, 100, 8, (44, 26, 67, 78)),
    SiteEnemy("E1M3", "Polar bear", "BEAR", 151, 15003, 201, 1380, 96, 34, 180, 8, (45, 30, 68, 79)),
)

THIRD_ENEMIES = (
    SiteEnemy("E1M1", "Armoured pigeon", "PIGE", 152, 15004, 203, 1420, 64, 22, 40, 12,
              (46, 27, 69, 80), "PosAttack", (3, 3, 3)),
    SiteEnemy("E1M2", "Animated medieval armour", "ARMR", 153, 15005, 204, 1460, 100, 34, 220, 5,
              (47, 53, 70, 84), "SPosAttack", (16, 12, 16)),
    SiteEnemy("E1M3", "Arctic wolf", "WOLF", 154, 15006, 205, 1500, 78, 26, 80, 14,
              (48, 54, 71, 85), "PosAttack", (6, 6, 6)),
)
ALL_ENEMIES = SITE_ENEMIES + THIRD_ENEMIES


def enemy_for(map_name, enemies=SITE_ENEMIES):
    for enemy in enemies:
        if enemy.map_name == map_name:
            return enemy
    raise ValueError(f"No location enemy for {map_name}")


def enemy_patch_lines(enemies=ALL_ENEMIES):
    lines = ["[SPRITES]", *(f"{enemy.sprite} = {enemy.prefix}" for enemy in enemies), ""]
    pointers = []
    for enemy in enemies:
        start = enemy.state
        # Idle, four-step chase, aim/fire/recover, pain, six intact defeat poses.
        sequence = (
            (14, 10, 1, "Look"), (15, 10, 0, "Look"),
            (0, 6, 3, "Chase"), (1, 6, 4, "Chase"),
            (2, 6, 5, "Chase"), (3, 6, 2, "Chase"),
            (4, enemy.attack_tics[0], 7, "FaceTarget"),
            (32773, enemy.attack_tics[1], 8, enemy.attack),
            (6, enemy.attack_tics[2], 2, "FaceTarget"), (7, 6, 2, "Pain"),
            (8, 5, 11, "NULL"), (9, 5, 12, "Scream"),
            (10, 5, 13, "Fall"), (11, 5, 14, "NULL"),
            (12, 5, 15, "NULL"), (13, -1, 0, "NULL"),
        )
        for offset, (frame, duration, next_offset, action) in enumerate(sequence):
            number = start + offset
            lines.extend((f"Frame {number}", f"Sprite number = {enemy.sprite}",
                          f"Sprite subnumber = {frame}", f"Duration = {duration}",
                          f"Next frame = {0 if duration == -1 else start + next_offset}", ""))
            pointers.append(f"FRAME {number} = {action}")
        lines.extend((
            f"Thing {enemy.thing}", f"ID # = {enemy.doomednum}",
            f"Initial frame = {start}", f"Hit points = {enemy.health}",
            f"First moving frame = {start + 2}", "Reaction time = 8",
            f"Injury frame = {start + 9}", "Pain chance = 170",
            "Close attack frame = 0", f"Far attack frame = {start + 6}",
            f"Death frame = {start + 10}", f"Exploding frame = {start + 10}",
            f"Speed = {enemy.speed}", f"Width = {enemy.radius * 65536}",
            f"Height = {enemy.height * 65536}", "Mass = 100",
            "Missile damage = 0", "Bits = 4194310", "Respawn frame = 0",
        ))
        for field, slot in zip(("Alert sound", "Pain sound", "Death sound", "Action sound"), enemy.sounds):
            lines.append(f"{field} = {slot}")
        lines.append("")
    lines.extend(("[CODEPTR]", *pointers, ""))
    return lines
