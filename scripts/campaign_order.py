"""Stable venue identities and their current sequential campaign slots."""

from dataclasses import dataclass


@dataclass(frozen=True)
class CampaignStop:
    source: str
    title: str
    sky: str


STOPS = (
    CampaignStop("E1M2", "Royal Ontario Museum", "TSKYROM"),
    CampaignStop("E1M8", "Queen's Park", "TSKYQPK"),
    CampaignStop("E1M4", "Sankofa Square", "TSKYSAN"),
    CampaignStop("E1M5", "Nathan Phillips Square", "TSKYNAT"),
    CampaignStop("E1M1", "Union Station", "TSKYUNI"),
    CampaignStop("E1M7", "Scotiabank Arena", "TSKYSCO"),
    CampaignStop("E1M6", "Rogers Centre", "TSKYROG"),
    CampaignStop("E1M9", "Toronto Islands", "TSKYISL"),
    CampaignStop("E1M3", "Toronto Zoo", "TSKYZOO"),
)
SOURCE_TO_SLOT = {stop.source: f"E1M{i}" for i, stop in enumerate(STOPS, 1)}
SLOT_TO_SOURCE = {slot: source for source, slot in SOURCE_TO_SLOT.items()}


def remap_resource(name):
    prefix, separator, source = name.partition("_")
    if separator and prefix in ("D", "O", "H") and source in SOURCE_TO_SLOT:
        return f"{prefix}_{SOURCE_TO_SLOT[source]}"
    return name
