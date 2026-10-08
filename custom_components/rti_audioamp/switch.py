"""Switch platform for RTI Audio Distribution Amp (power, mute)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import RtiAudioAmpData
from .const import DOMAIN, NUM_ZONES
from .entity import RtiZoneEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    data: RtiAudioAmpData = hass.data[DOMAIN][entry.entry_id]

    entities: list[RtiZoneEntity] = []
    for zone in range(1, NUM_ZONES + 1):
        entities.append(RtiZonePowerSwitch(data.coordinator, zone))
        entities.append(RtiZoneMuteSwitch(data.coordinator, zone))

    async_add_entities(entities)


def _as_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(int(value))
    if isinstance(value, str):
        return value.strip() in ("1", "true", "True", "on", "ON")
    return None


class RtiZonePowerSwitch(RtiZoneEntity, SwitchEntity):
    """Zone power on/off."""

    _attr_translation_key = "power"
    _entity_key = "power"
    _attr_device_class = SwitchDeviceClass.SWITCH

    @property
    def is_on(self) -> bool | None:
        return _as_bool(self._zone_data.get("power"))

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.api.async_set_power(self.zone, True)
        self.coordinator.apply_optimistic(self.zone, "power", "1")

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.api.async_set_power(self.zone, False)
        self.coordinator.apply_optimistic(self.zone, "power", "0")


class RtiZoneMuteSwitch(RtiZoneEntity, SwitchEntity):
    """Zone mute on/off."""

    _attr_translation_key = "mute"
    _entity_key = "mute"
    _attr_entity_category = None  # shown as a normal control
    _attr_device_class = SwitchDeviceClass.SWITCH

    @property
    def is_on(self) -> bool | None:
        return _as_bool(self._zone_data.get("mute"))

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.api.async_set_mute(self.zone, True)
        self.coordinator.apply_optimistic(self.zone, "mute", "1")

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.api.async_set_mute(self.zone, False)
        self.coordinator.apply_optimistic(self.zone, "mute", "0")
