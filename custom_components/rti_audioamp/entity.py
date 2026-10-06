"""Base entity for RTI Audio Distribution Amp zone entities."""

from __future__ import annotations

from homeassistant.const import CONF_HOST
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import RtiAudioAmpCoordinator


class RtiZoneEntity(CoordinatorEntity[RtiAudioAmpCoordinator]):
    """Common base for every entity that belongs to one amp zone."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: RtiAudioAmpCoordinator, zone: int) -> None:
        super().__init__(coordinator)
        self.zone = zone
        host = coordinator.entry.data[CONF_HOST]
        self._attr_unique_id = f"{host}_zone{zone}_{self._entity_key}"

        model = None
        if coordinator.device_info:
            model = coordinator.device_info.get("model")

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{host}_zone{zone}")},
            name=f"Zone {zone}",
            manufacturer=MANUFACTURER,
            model=model or "RTI Audio Amp Zone",
            # Link to the main amp device by its real registry ID
            # (created in __init__.py before entities are set up).
            # HA Core 2026.8+ removed the old via_device=(domain, id)
            # form from DeviceInfo entirely, requiring the resolved
            # device_id instead.
            via_device_id=coordinator.main_device_id,
        )

    @property
    def _entity_key(self) -> str:
        """Override in subclasses, e.g. 'power', 'volume'."""
        raise NotImplementedError

    @property
    def _zone_data(self) -> dict:
        return self.coordinator.zone_data(self.zone)

    @property
    def available(self) -> bool:
        return super().available and bool(self._zone_data)
