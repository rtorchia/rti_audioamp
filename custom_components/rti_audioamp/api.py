"""Async client for talking to an RTI audio distribution amp (e.g. AD-4x).

This is an async re-implementation of the user's original ``rtiaudioamp.py``
script, adapted to use aiohttp (required inside Home Assistant's event loop
instead of urllib) and wrapped in a class.

Confirmed live response shape from ``rti_status.cgi`` (AD-4x, firmware as
tested):

    {
      "zones": [
        {"zone": {"pwr": "0", "mut": "0", "src": "1", "vol": "30", "grp": "1"}},
        ... one entry per zone, in order (index 0 == zone 1) ...
      ],
      "seq": "0"
    }

``vol`` is already a plain 0-100 percentage (not dB) when read back from
this endpoint - the dB conversion in the original script only applies to
the *write* side (``/rti_zvs.cgi``). Inactive zones (e.g. zones 5-8 on a
4-zone AD-4x) report ``"src": "0"`` and zeroed-out values.

WRITE ENDPOINTS AND "seq": the status JSON includes a top-level "seq"
field. The original script always sent "&s=0" on every write call
(rti_zp*.cgi, rti_zm*.cgi, rti_zi.cgi, rti_zg.cgi, rti_zvs.cgi), which
only works while the device's sequence number happens to stay at 0.
This client instead fetches the current status first and echoes back
its real "seq" value as "s=" on every write, since the amp appears to
reject/ignore writes whose sequence number doesn't match its current
state - which is the most likely explanation for writes silently not
taking effect once "seq" has advanced past 0.

``_remove_html_comments`` is kept as a harmless no-op safety net in case a
different firmware version still emits the templated ``<!--#znN-->`` form
mentioned in the original script.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)

# Candidate key names to look for within each zone's status dict.
# The first match found is used. "pwr"/"mut"/"src"/"vol"/"grp" are the
# confirmed real keys; the rest are kept as fallbacks for other firmware.
_FIELD_CANDIDATES: dict[str, list[str]] = {
    "power": ["pwr", "power", "pw", "on"],
    "mute": ["mut", "mute", "mt"],
    "source": ["src", "source", "input", "i"],
    "volume": ["vol", "volume", "v"],
    "group": ["grp", "group", "g"],
}


class RtiAudioAmpError(Exception):
    """Generic error talking to the RTI audio amp."""


class RtiAudioAmpConnectionError(RtiAudioAmpError):
    """Raised when the device can't be reached."""


class RtiAudioAmpApi:
    """Thin async wrapper around the RTI amp's CGI endpoints."""

    def __init__(
        self,
        host: str,
        password: str,
        session: aiohttp.ClientSession,
        port: int = 80,
        timeout: int = 10,
    ) -> None:
        """Create the API client.

        Note: the device's CGI endpoints (rti_status.cgi, rti_zp0.cgi,
        etc.) respond over plain HTTP with no authentication required -
        confirmed by querying /rti_status.cgi directly with no password.
        ``password`` is accepted and stored on the config entry for
        possible future use (e.g. if a firmware update starts requiring
        it, or for gating the device's own web UI), but it is not
        currently sent with any request.

        Requests are serialized (one in flight at a time) and sent with
        "Connection: close", because the amp's embedded web server has
        been observed returning corrupted/truncated JSON when requests
        overlap or reuse a kept-alive connection - a common limitation
        of small embedded HTTP servers.
        """
        self._session = session
        self._timeout = timeout
        self._password = password
        self._base_url = f"http://{host}:{port}" if port != 80 else f"http://{host}"
        # Serialize all requests to the device: its embedded web server
        # appears not to handle overlapping requests reliably.
        self._request_lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Low level helpers
    # ------------------------------------------------------------------
    async def _get(self, path: str) -> str:
        url = self._base_url + path
        _LOGGER.debug("RTI amp request: %s", url)
        async with self._request_lock:
            try:
                async with asyncio.timeout(self._timeout):
                    async with self._session.get(
                        url,
                        headers={"Connection": "close"},
                    ) as resp:
                        resp.raise_for_status()
                        text = await resp.text()
                        _LOGGER.debug(
                            "RTI amp response (%s): %s", resp.status, text[:200]
                        )
                        return text
            except (aiohttp.ClientError, asyncio.TimeoutError) as err:
                raise RtiAudioAmpConnectionError(
                    f"Error communicating with RTI amp at {self._base_url}: {err}"
                ) from err

    @staticmethod
    def _remove_html_comments(data: str) -> str:
        """Fix up the device's non-standard JSON (mirrors the original script)."""
        for zone_num in range(1, 9):
            data = data.replace(
                f'"zone": <!--#zn{zone_num}-->', f'"zone{zone_num}":'
            )
        data = data.replace("<!--#seq-->", "")
        return data

    # ------------------------------------------------------------------
    # Public read methods
    # ------------------------------------------------------------------
    async def async_get_raw_config(self) -> dict[str, Any]:
        """Fetch and parse the device's current status/config JSON.

        The device's embedded web server occasionally returns
        corrupted/truncated JSON (seen as JSONDecodeError at a different
        position each time), most likely from connection-reuse or
        request-overlap issues on its side. A couple of quick retries
        clear this up in practice without surfacing a transient glitch
        as a coordinator update failure.
        """
        import json

        last_err: Exception | None = None
        for attempt in range(3):
            text = await self._get("/rti_status.cgi")
            text = self._remove_html_comments(text)
            try:
                return json.loads(text)
            except ValueError as err:
                last_err = err
                _LOGGER.debug(
                    "Malformed status JSON on attempt %d/3: %s | raw: %r",
                    attempt + 1,
                    err,
                    text,
                )
                if attempt < 2:
                    await asyncio.sleep(0.3)

        raise RtiAudioAmpError(
            f"Could not parse status response from device after retries: {last_err}"
        )

    async def async_get_device_info(self) -> dict[str, Any]:
        """Fetch static device attributes (model, firmware, MAC, etc.)."""
        data = await self._get("/rti.shtml")

        def locate(marker: str) -> int:
            idx = data.find(marker)
            if idx == -1:
                return -1
            return idx + len(marker) + 1

        def slice_after(marker: str, length: int) -> str:
            idx = locate(marker)
            if idx == -1:
                return ""
            return data[idx : idx + length]

        return {
            "model": slice_after("var rtiModel=", 5).strip('";'),
            "zones": slice_after("var rtiMaxPorts", 1),
            "revision": slice_after("var rtiAdRev=", 5).strip('";'),
            "firmware": slice_after("var fwrev=", 6).strip("'\""),
            "mac": slice_after("var macaddr=", 17).strip("'\""),
        }

    async def async_get_zone_status(self, zone: int) -> dict[str, Any]:
        """Return the best-effort parsed status for a single zone (1-based)."""
        raw = await self.async_get_raw_config()
        return self._extract_zone(raw, zone)

    async def async_get_all_zone_status(
        self, num_zones: int
    ) -> dict[int, dict[str, Any]]:
        """Return best-effort parsed status for all zones, keyed by zone number."""
        raw = await self.async_get_raw_config()
        result = {z: self._extract_zone(raw, z) for z in range(1, num_zones + 1)}

        if all(all(v is None for v in zone.values()) for zone in result.values()):
            _LOGGER.warning(
                "Could not find any recognizable fields in the device's "
                "status response for any zone - the JSON shape may not "
                "match what this integration expects. Raw response: %s",
                raw,
            )
        return result

    @staticmethod
    def _extract_zone(raw: dict[str, Any], zone: int) -> dict[str, Any]:
        """Extract one zone's fields (1-based) from the raw config.

        Confirmed real shape: raw["zones"] is a list, in zone order
        (index 0 is zone 1), where each entry is
        {"zoneN": {"pwr": ..., "mut": ..., "src": ..., "vol": ...,
        "grp": ...}} - note the key is "zoneN" (e.g. "zone1"), not a
        generic "zone". A couple of fallback shapes are also tried in
        case a different firmware version differs. Unresolved fields are
        returned as None so entities can mark themselves "unavailable"
        rather than crash.
        """
        result: dict[str, Any] = {
            "power": None,
            "mute": None,
            "source": None,
            "volume": None,
            "group": None,
        }

        zone_block: Any = None

        zones_list = raw.get("zones")
        if isinstance(zones_list, list) and 1 <= zone <= len(zones_list):
            entry = zones_list[zone - 1]
            if isinstance(entry, dict):
                # Confirmed shape: {"zoneN": {...fields...}}
                zone_block = entry.get(f"zone{zone}")
                # Fallback: {"zone": {...fields...}} (generic key)
                if not isinstance(zone_block, dict):
                    zone_block = entry.get("zone")
                # Fallback: the entry itself IS the fields dict
                if not isinstance(zone_block, dict) and any(
                    any(c in entry for c in cands)
                    for cands in _FIELD_CANDIDATES.values()
                ):
                    zone_block = entry

        # Fallback shape: raw["zoneN"] as a nested dict of fields.
        if not isinstance(zone_block, dict):
            zone_block = raw.get(f"zone{zone}")

        if isinstance(zone_block, dict):
            for field, candidates in _FIELD_CANDIDATES.items():
                for candidate in candidates:
                    if candidate in zone_block:
                        result[field] = zone_block[candidate]
                        break
            return result

        # Last-resort fallback: suffixed top-level keys, e.g. "pwr1", "vol1"
        for field, candidates in _FIELD_CANDIDATES.items():
            for candidate in candidates:
                key = f"{candidate}{zone}"
                if key in raw:
                    result[field] = raw[key]
                    break

        return result

    # ------------------------------------------------------------------
    # Public write methods (endpoints confirmed from the original script)
    # ------------------------------------------------------------------
    async def _current_seq(self) -> str:
        """Return the device's current sequence number ("seq" in the
        status JSON), which the write endpoints appear to expect echoed
        back as the "s=" query parameter (see note below).
        """
        try:
            raw = await self.async_get_raw_config()
            return str(raw.get("seq", "0"))
        except RtiAudioAmpError:
            return "0"

    async def async_set_power(self, zone: int, on: bool) -> None:
        suffix = "1" if on else "0"
        seq = await self._current_seq()
        await self._get(f"/rti_zp{suffix}.cgi?z={zone}&s={seq}")

    async def async_set_mute(self, zone: int, on: bool) -> None:
        suffix = "1" if on else "0"
        seq = await self._current_seq()
        await self._get(f"/rti_zm{suffix}.cgi?z={zone}&s={seq}")

    async def async_set_source(self, zone: int, source: int) -> None:
        source = max(1, min(4, source))
        seq = await self._current_seq()
        await self._get(f"/rti_zi.cgi?z={zone}&i={source}&s={seq}")

    async def async_set_group(self, zone: int, group: int) -> None:
        group = max(0, min(4, group))
        seq = await self._current_seq()
        await self._get(f"/rti_zg.cgi?z={zone}&g={group}&s={seq}")

    async def async_set_volume(self, zone: int, percent: int) -> None:
        percent = max(0, min(100, percent))
        db = self._percent_to_decibels(percent)
        seq = await self._current_seq()
        await self._get(f"/rti_zvs.cgi?z={zone}&v={db}&s={seq}")

    # ------------------------------------------------------------------
    # Volume conversion helpers (ported as-is from the original script)
    # ------------------------------------------------------------------
    @staticmethod
    def _percent_to_decibels(percent: int) -> int:
        return round(((percent / 100) - 1) * 75)

    @staticmethod
    def _decibels_to_percent(db: int) -> int:
        value = db
        if value > 0:
            value = value * -1
        return round((1 + (value / 75)) * 100)

    @classmethod
    def decibels_to_percent(cls, db: Any) -> int | None:
        """Public helper so the coordinator can convert a raw dB reading."""
        try:
            return cls._decibels_to_percent(int(db))
        except (TypeError, ValueError):
            return None
