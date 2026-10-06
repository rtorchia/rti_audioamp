"""Number platform for RTI Audio Distribution Amp (volume, 0-100%)."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import RtiAudioAmpData
from .const import DOMAIN, MAX_VOLUME, MIN_VOLUME, NUM_ZONES
from .entity import RtiZoneEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    data: RtiAudioAmpData = hass.data[DOMAIN][entry.entry_id]

    entities = [
        RtiZoneVolumeNumber(data.coordinator, zone)
        for zone in range(1, NUM_ZONES + 1)
    ]
    async_add_entities(entities)


class RtiZoneVolumeNumber(RtiZoneEntity, NumberEntity):
    """Zone volume, expressed as a 0-100% level."""

    _attr_translation_key = "volume"
    _entity_key = "volume"
    _attr_native_min_value = MIN_VOLUME
    _attr_native_max_value = MAX_VOLUME
    _attr_native_step = 1
    _attr_native_unit_of_measurement = "%"
    _attr_mode = NumberMode.SLIDER
    _attr_icon = "mdi:volume-high"

    @property
    def native_value(self) -> float | None:
        # The device reports "vol" as dB attenuation (0 = full volume,
        # down to -75 = minimum/muted level; some firmware reports this
        # as a positive magnitude, e.g. "52" meaning -52 dB - the
        # conversion below handles both). Home Assistant shows/accepts
        # a plain 0-100% for this entity, so convert on the way in.
        raw = self._zone_data.get("volume")
        if raw is None:
            return None

        from .api import RtiAudioAmpApi

        percent = RtiAudioAmpApi.decibels_to_percent(raw)
        if percent is None:
            return None
        return max(0.0, min(100.0, float(percent)))

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.api.async_set_volume(self.zone, int(value))
        await self.coordinator.async_request_refresh()
