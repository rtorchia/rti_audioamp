"""DataUpdateCoordinator for the RTI Audio Distribution Amp."""

from __future__ import annotations

import logging
import time
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import RtiAudioAmpApi, RtiAudioAmpError
from .const import DOMAIN, NUM_ZONES

_LOGGER = logging.getLogger(__name__)

# How long to keep showing a commanded value while waiting for the amp
# to report it back before trusting the amp's reading instead.
GRACE_SECONDS = 12.0


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
        self._confirm_unsub: CALLBACK_TYPE | None = None
        # (zone, field) -> (expected value, monotonic deadline)
        self._expected: dict[tuple[int, str], tuple[str, float]] = {}

    async def _async_update_data(self) -> dict[int, dict]:
        try:
            if self.device_info is None:
                self.device_info = await self.api.async_get_device_info()
            data = await self.api.async_get_all_zone_status(NUM_ZONES)
        except RtiAudioAmpError as err:
            raise UpdateFailed(f"Error updating RTI amp status: {err}") from err
        return self._reconcile_expected(data)

    def _reconcile_expected(self, data: dict[int, dict]) -> dict[int, dict]:
        """Hold recently-commanded values steady while the amp catches up.

        If the amp still reports the old value shortly after a command,
        keep showing the commanded value and re-check soon. If it never
        agrees within the grace window, log it and show the amp's value.
        """
        now = time.monotonic()
        for key, (expected, deadline) in list(self._expected.items()):
            zone, field = key
            actual = data.get(zone, {}).get(field)
            if actual is None or str(actual) == expected:
                del self._expected[key]
            elif now < deadline:
                data[zone][field] = expected  # amp hasn't caught up yet
            else:
                _LOGGER.warning(
                    "Zone %s %s was commanded to %s but the amp still "
                    "reports %s after %.0fs - the amp is not applying "
                    "this change (or something is reverting it)",
                    zone, field, expected, actual, GRACE_SECONDS,
                )
                del self._expected[key]
        if self._expected:
            self.schedule_confirm_refresh(2.0)
        return data

    def zone_data(self, zone: int) -> dict:
        """Convenience accessor with a safe default."""
        if not self.data:
            return {}
        return self.data.get(zone, {})

    # ------------------------------------------------------------------
    # Optimistic updates
    # ------------------------------------------------------------------
    # The amp can take a moment to settle after a command (e.g. powering
    # a zone down). Polling it immediately returns the *old* state and
    # makes the switch snap back. So after a write we show the expected
    # value right away, then confirm with the amp after a short delay.
    def apply_optimistic(self, zone: int, field: str, value: str) -> None:
        """Reflect a just-written value immediately in the UI."""
        self._expected[(zone, field)] = (value, time.monotonic() + GRACE_SECONDS)
        if self.data and zone in self.data:
            new_data = {z: dict(d) for z, d in self.data.items()}
            new_data[zone][field] = value
            self.async_set_updated_data(new_data)
        self.schedule_confirm_refresh(2.0)

    def schedule_confirm_refresh(self, delay: float = 2.0) -> None:
        """Re-poll the amp after it has had time to apply a change."""
        self._cancel_confirm()

        async def _confirm(_now) -> None:
            self._confirm_unsub = None
            await self.async_request_refresh()

        self._confirm_unsub = async_call_later(self.hass, delay, _confirm)

    def _cancel_confirm(self) -> None:
        if self._confirm_unsub is not None:
            self._confirm_unsub()
            self._confirm_unsub = None

    async def async_shutdown(self) -> None:
        self._cancel_confirm()
        await super().async_shutdown()
