"""DataUpdateCoordinator for the RTI Audio Distribution Amp."""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import RtiAudioAmpApi, RtiAudioAmpError
from .const import DOMAIN, NUM_ZONES

_LOGGER = logging.getLogger(__name__)


class RtiAudioAmpCoordinator(DataUpdateCoordinator[dict[int, dict]]):
    """Polls the amp on an interval and hands out per-zone status."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        api: RtiAudioAmpApi,
        scan_interval: int,
        source_names: dict[int, str],
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )
        self.api = api
        self.entry = entry
        self.device_info: dict | None = None
        self.source_names = source_names
        self.main_device_id: str | None = None

    async def _async_update_data(self) -> dict[int, dict]:
        try:
            if self.device_info is None:
                self.device_info = await self.api.async_get_device_info()
            return await self.api.async_get_all_zone_status(NUM_ZONES)
        except RtiAudioAmpError as err:
            raise UpdateFailed(f"Error updating RTI amp status: {err}") from err

    def zone_data(self, zone: int) -> dict:
        """Convenience accessor with a safe default."""
        if not self.data:
            return {}
        return self.data.get(zone, {})
