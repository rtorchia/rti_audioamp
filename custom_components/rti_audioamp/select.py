"""Select platform for RTI Audio Distribution Amp (source, group)."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import RtiAudioAmpData
from .const import DOMAIN, GROUP_LABELS, NUM_ZONES
from .entity import RtiZoneEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    data: RtiAudioAmpData = hass.data[DOMAIN][entry.entry_id]

    entities: list[RtiZoneEntity] = []
    for zone in range(1, NUM_ZONES + 1):
        entities.append(RtiZoneSourceSelect(data.coordinator, zone))
        entities.append(RtiZoneGroupSelect(data.coordinator, zone))

    async_add_entities(entities)


class RtiZoneSourceSelect(RtiZoneEntity, SelectEntity):
    """Choose the audio source for this zone, shown by friendly name."""

    _attr_translation_key = "source"
    _entity_key = "source"
    _attr_icon = "mdi:audio-input-rca"

    def __init__(self, coordinator, zone: int) -> None:
        super().__init__(coordinator, zone)
        # name -> number and number -> name, built from the user's
        # configured source names (e.g. {"Sonos": 2, 2: "Sonos"}).
        self._name_to_num = {
            name: num for num, name in coordinator.source_names.items()
        }

    @property
    def options(self) -> list[str]:
        return list(self.coordinator.source_names.values())

    @property
    def current_option(self) -> str | None:
        value = self._zone_data.get("source")
        if value is None:
            return None
        try:
            num = int(value)
        except (TypeError, ValueError):
            return None
        # Inactive zones can report 0 (no source assigned) - not a
        # writable/named option, so surface as unknown rather than error.
        return self.coordinator.source_names.get(num)

    async def async_select_option(self, option: str) -> None:
        source_num = self._name_to_num.get(option)
        if source_num is None:
            return
        await self.coordinator.api.async_set_source(self.zone, source_num)
        await self.coordinator.async_request_refresh()


class RtiZoneGroupSelect(RtiZoneEntity, SelectEntity):
    """Choose the group for this zone; group 0 is shown as 'None'."""

    _attr_translation_key = "group"
    _entity_key = "group"
    _attr_icon = "mdi:speaker-multiple"

    _label_to_num = {label: num for num, label in GROUP_LABELS.items()}

    @property
    def options(self) -> list[str]:
        return list(GROUP_LABELS.values())

    @property
    def current_option(self) -> str | None:
        value = self._zone_data.get("group")
        if value is None:
            return None
        try:
            num = int(value)
        except (TypeError, ValueError):
            return None
        return GROUP_LABELS.get(num)

    async def async_select_option(self, option: str) -> None:
        group_num = self._label_to_num.get(option)
        if group_num is None:
            return
        await self.coordinator.api.async_set_group(self.zone, group_num)
        await self.coordinator.async_request_refresh()
