"""Reviewed AI art sources and native-size, ground-anchored venue artwork."""

from functools import lru_cache

from PIL import Image

from project_paths import ART_SOURCES
from toronto_materials import _tile_edges


DIRECTORY = ART_SOURCES / "polish"
HUMAN_SIZE = (80, 64)


@lru_cache(maxsize=64)
def _sprite(kind, frame):
    with Image.open(DIRECTORY / "sprites" / f"{kind}-{frame}.png") as source:
        image = source.convert("RGBA")
    if not image.getchannel("A").getbbox():
        raise ValueError(f"Empty polished sprite: {kind}-{frame}")
    return image


def sprite(kind, frame=0):
    return _sprite(kind, frame).copy()


@lru_cache(maxsize=64)
def _material(index, size, seamless):
    with Image.open(DIRECTORY / "materials-source.png") as source:
        column, row = index % 4, index // 4
        image = source.crop((round(column * source.width / 4), round(row * source.height / 4),
                             round((column + 1) * source.width / 4),
                             round((row + 1) * source.height / 4)))
        image = image.convert("RGB").resize(size, Image.Resampling.LANCZOS)
    if seamless:
        image = _tile_edges(image, True)
    return image


def material(index, size=(128, 128), seamless=True):
    return _material(index, size, seamless).copy()


@lru_cache(maxsize=64)
def _site_material(filename, index, size, seamless, vertical):
    from project_paths import ASSETS

    with Image.open(ASSETS / filename) as source:
        image = source.convert("RGB")
    cell_width, cell_height = image.width / 4, image.height / 2
    column, row = index % 4, index // 4
    # A fixed inset keeps the atlas divider lines out of every reviewed cell.
    inset = 10
    image = image.crop((round(column * cell_width) + inset, round(row * cell_height) + inset,
                        round((column + 1) * cell_width) - inset,
                        round((row + 1) * cell_height) - inset))
    image = image.resize(size, Image.Resampling.LANCZOS)
    if seamless:
        image = _tile_edges(image, vertical)
    return image


def site_material(filename, index, size=(128, 128), seamless=True, vertical=True):
    """One reviewed cell of a high-definition 4-by-2 site texture atlas."""
    return _site_material(filename, index, size, seamless, vertical).copy()
