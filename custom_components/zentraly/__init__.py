"""Zentraly integration for Home Assistant."""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import ZentralyAPI, ZentralyAuthError, ZentralyConnectionError
from .const import CONF_DEVICE_ID, CONF_EMAIL, CONF_PASSWORD, DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.CLIMATE]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Zentraly from a config entry."""
    api = ZentralyAPI(
        email=entry.data[CONF_EMAIL],
        password=entry.data[CONF_PASSWORD],
    )
    device_id = entry.data[CONF_DEVICE_ID]

    async def async_update_data() -> dict:
        try:
            return await hass.async_add_executor_job(api.get_state, device_id)
        except ZentralyAuthError as exc:
            raise ConfigEntryAuthFailed(str(exc)) from exc
        except ZentralyConnectionError as exc:
            raise UpdateFailed(str(exc)) from exc

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"zentraly_{device_id}",
        update_method=async_update_data,
        update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
    )

    try:
        await hass.async_add_executor_job(api.login)
    except ZentralyAuthError as exc:
        raise ConfigEntryAuthFailed(str(exc)) from exc
    except ZentralyConnectionError as exc:
        raise ConfigEntryNotReady(str(exc)) from exc

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "api": api,
        "coordinator": coordinator,
        "device_id": device_id,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
