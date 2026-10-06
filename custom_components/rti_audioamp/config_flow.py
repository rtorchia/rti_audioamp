"""Config flow for the RTI Audio Distribution Amp integration."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import RtiAudioAmpApi, RtiAudioAmpError
from .const import (
    CONF_SCAN_INTERVAL,
    DEFAULT_PASSWORD,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    NUM_SOURCES,
    default_source_name,
    source_name_key,
)

_LOGGER = logging.getLogger(__name__)


def _with_source_name_fields(schema_dict: dict, current: dict) -> dict:
    """Add one optional text field per source to a voluptuous schema dict."""
    for n in range(1, NUM_SOURCES + 1):
        key = source_name_key(n)
        schema_dict[
            vol.Optional(key, default=current.get(key, default_source_name(n)))
        ] = str
    return schema_dict


def _build_user_schema(current: dict | None = None) -> vol.Schema:
    current = current or {}
    schema_dict: dict = {
        vol.Required(CONF_HOST, default=current.get(CONF_HOST, "")): str,
        vol.Optional(
            CONF_PASSWORD, default=current.get(CONF_PASSWORD, DEFAULT_PASSWORD)
        ): str,
        vol.Optional(
            CONF_SCAN_INTERVAL,
            default=current.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        ): vol.All(vol.Coerce(int), vol.Range(min=5, max=3600)),
    }
    return vol.Schema(_with_source_name_fields(schema_dict, current))


STEP_USER_SCHEMA = _build_user_schema()


async def _validate_input(hass, data: dict[str, Any]) -> dict[str, Any]:
    """Try to reach the device; raise on failure."""
    session = async_get_clientsession(hass)
    api = RtiAudioAmpApi(
        host=data[CONF_HOST],
        password=data[CONF_PASSWORD],
        session=session,
    )
    try:
        info = await api.async_get_device_info()
    except RtiAudioAmpError as err:
        raise CannotConnect from err

    title = f"RTI {info.get('model') or 'AudioAmp'} ({data[CONF_HOST]})"
    return {"title": title}


class RtiAudioAmpConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for RTI Audio Distribution Amp."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_HOST])
            self._abort_if_unique_id_configured()

            try:
                info = await _validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected exception during setup")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=_build_user_schema(user_input),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> RtiAudioAmpOptionsFlow:
        return RtiAudioAmpOptionsFlow(config_entry)


class RtiAudioAmpOptionsFlow(config_entries.OptionsFlow):
    """Allow changing the poll interval (and password) after setup."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current: dict[str, Any] = {**self._entry.data, **self._entry.options}

        schema_dict: dict = {
            vol.Optional(
                CONF_PASSWORD, default=current.get(CONF_PASSWORD, DEFAULT_PASSWORD)
            ): str,
            vol.Optional(
                CONF_SCAN_INTERVAL,
                default=current.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
            ): vol.All(vol.Coerce(int), vol.Range(min=5, max=3600)),
        }
        schema = vol.Schema(_with_source_name_fields(schema_dict, current))
        return self.async_show_form(step_id="init", data_schema=schema)


class CannotConnect(Exception):
    """Error to indicate we cannot connect to the device."""
