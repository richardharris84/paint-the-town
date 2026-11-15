"""Campaign-only NPC marker tiers, native attack states and front receivers."""

import math
from dataclasses import dataclass

from PIL import Image, ImageDraw


NPC_SOUND_SPECS = (("DSFRE048", "marker", .15, 3),)
ATTACK_BASE = 2600
ATTACK_STRIDE = 16


@dataclass(frozen=True)
class AttackTier:
    pellets: int
    rounds: int
    recovery_tics: int
    sound: int
    aim_tics: int = 10
    shot_tics: int = 4

    @property
    def chain_tics(self):
        return self.aim_tics + self.rounds * self.shot_tics + self.recovery_tics

    @property
    def expected_damage_per_minute(self):
        return self.pellets * self.rounds * 10 * 2100 / self.chain_tics


ATTACK_TIERS = {
    2: AttackTier(1, 1, 8, 8),
    3: AttackTier(7, 1, 42, 2),
    4: AttackTier(1, 6, 8, 548),
}


def attack_start(index):
    return ATTACK_BASE + index * ATTACK_STRIDE


def weapon_sounds():
    from paintball_audio import synthesize_sound
    return [(name, synthesize_sound(kind, duration, seed))
            for name, kind, duration, seed in NPC_SOUND_SPECS]


def weapon_slot(height):
    return 2 if height <= 54 else 3 if height < 88 else 4


def attack_lumps(enemies):
    actors = [(2, 29, 184, 176, 56)]
    actors.extend((enemy.thing, enemy.sprite, enemy.state + 6, enemy.state + 2, enemy.height)
                  for enemy in enemies)
    lines, pointers = [], []
    for index, (thing, sprite, _, chase, height) in enumerate(actors):
        start = attack_start(index)
        slot = weapon_slot(height)
        tier = ATTACK_TIERS[slot]
        lines.extend((f"Thing {thing}", f"Far attack frame = {start}", ""))
        sequence = [(4, tier.aim_tics, start + 1, "FaceTarget")]
        for shot in range(tier.rounds):
            sound_state = start + 1 + shot * 2
            sequence.extend((
                (5, 0, sound_state + 1, "PlaySound"),
                (32773, tier.shot_tics, sound_state + 2, "MonsterBulletAttack"),
            ))
        sequence.append((4 if thing == 2 else 6, tier.recovery_tics, chase, "FaceTarget"))
        if len(sequence) > ATTACK_STRIDE:
            raise ValueError(f"NPC tier {slot} exceeds its state allocation")
        for offset, (frame, duration, next_state, action) in enumerate(sequence):
            number = start + offset
            lines.extend((f"Frame {number}", f"Sprite number = {sprite}",
                          f"Sprite subnumber = {frame}", f"Duration = {duration}",
                          f"Next frame = {next_state}"))
            if action == "PlaySound":
                lines.extend((f"Unknown 1 = {tier.sound}", "Unknown 2 = 0"))
            elif action == "MonsterBulletAttack":
                lines.extend((f"Args1 = {round(5.625 * 65536)}", "Args2 = 0",
                              f"Args3 = {tier.pellets}", "Args4 = 5", "Args5 = 3"))
            lines.append("")
            pointers.append(f"FRAME {number} = {action}")
    return ("\n".join((*lines, "[CODEPTR]", *pointers, "")) + "\n").encode("ascii")


MUZZLES = {
    "POSS": (.50, .40), "DRON": (.50, .74), "DINO": (.52, .42),
    "BEAR": (.50, .35), "PIGE": (.50, .30), "ARMR": (.50, .32),
    "WOLF": (.45, .36), "BVER": (.50, .38), "RFOX": (.50, .44),
    "GOOS": (.50, .48), "CHIP": (.50, .55), "BJAY": (.50, .40),
    "GHOG": (.50, .38), "SOWL": (.50, .48), "WOLV": (.50, .38),
    "BLSQ": (.52, .48), "STAG": (.50, .43), "SWAN": (.50, .46),
    "OTTR": (.50, .42),
}


def marker_receiver(image, prefix, height, firing=False):
    """Refit the existing front-facing paint marker at its species-specific mount."""
    bounds = image.getbbox()
    if bounds is None:
        raise ValueError(f"{prefix}: empty NPC frame")
    x0, y0, x1, y1 = bounds
    mx, my = MUZZLES[prefix]
    cx, cy = round(x0 + (x1 - x0) * mx), round(y0 + (y1 - y0) * my)
    slot = weapon_slot(height)
    radius = max(2, round(height * .045))
    draw = ImageDraw.Draw(image)
    dark, blue, orange, green = "#121b25", "#263d91", "#ec7d29", "#87c449"
    if slot == 2:
        draw.rectangle((cx - radius, cy - radius, cx + radius, cy + radius * 2),
                       fill=dark, outline=blue)
        draw.line((cx - radius, cy - radius, cx + radius, cy - radius), fill=green)
        draw.ellipse((cx - 1, cy - 1, cx + 1, cy + 1), fill=orange)
    elif slot == 3:
        draw.rounded_rectangle((cx - radius - 1, cy - radius - 1,
                                cx + radius + 1, cy + radius * 2),
                               radius=1, fill="#7a807d", outline=dark)
        draw.rectangle((cx - radius, cy + radius, cx + radius, cy + radius * 2),
                       fill=orange, outline=dark)
        draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=dark, outline=orange)
    else:
        draw.ellipse((cx - radius - 1, cy - radius - 1, cx + radius + 1, cy + radius + 1),
                     fill=blue, outline=orange)
        for angle in range(0, 360, 60):
            x = cx + round(radius * .65 * math.cos(math.radians(angle)))
            y = cy + round(radius * .65 * math.sin(math.radians(angle)))
            draw.point((x, y), fill=dark)
        draw.point((cx, cy), fill=green)
    if firing:
        draw.line((cx + radius + 1, cy, cx + radius + 3, cy), fill="#59d9c7")
    return image
