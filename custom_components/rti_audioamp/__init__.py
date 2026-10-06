"""The RTI Audio Distribution Amp integration."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import RtiAudioAmpApi
from .const import CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL, DOMAIN, MANUFACTURER, build_source_names
from .coordinator import RtiAudioAmpCoordinator

PLATFORMS: list[Platform] = [Platform.SWITCH, Platform.SELECT, Platform.NUMBER]


@dataclass
class RtiAudioAmpData:
    """Runtime data stored on the config entry."""

    api: RtiAudioAmpApi
    coordinator: RtiAudioAmpCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up RTI Audio Distribution Amp from a config entry."""
    session = async_get_clientsession(hass)

    password = entry.options.get(CONF_PASSWORD, entry.data.get(CONF_PASSWORD))
    scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    source_names = build_source_names(entry.data, entry.options)

    api = RtiAudioAmpApi(
        host=entry.data[CONF_HOST],
        password=password,
        session=session,
    )

    coordinator = RtiAudioAmpCoordinator(hass, entry, api, scan_interval, source_names)
    await coordinator.async_config_entry_first_refresh()

    # Register the amp itself as a device, so each zone's device can
    # correctly link to it via via_device_id (not the deprecated
    # via_device-by-identifiers form).
    device_reg = dr.async_get(hass)
    main_device = device_reg.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.data[CONF_HOST])},
        manufacturer=MANUFACTURER,
        model=(coordinator.device_info or {}).get("model") or "Audio Distribution Amp",
        name=entry.title,
    )
    coordinator.main_device_id = main_device.id

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = RtiAudioAmpData(api=api, coordinator=coordinator)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the entry when options change (e.g. poll interval)."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
