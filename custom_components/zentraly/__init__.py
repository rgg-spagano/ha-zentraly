"""Zentraly integration for Home Assistant."""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.restore_state import RestoreEntity  # noqa: F401 – re-exported for climate.py
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import ZentralyAPI, ZentralyAuthError, ZentralyConnectionError
from .const import CONF_DEVICE_ID, CONF_EMAIL, CONF_PASSWORD, DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.CLIMATE]
_STORAGE_VERSION = 1


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Zentraly from a config entry."""
    api = ZentralyAPI(
        email=entry.data[CONF_EMAIL],
        password=entry.data[CONF_PASSWORD],
    )
    device_id = entry.data[CONF_DEVICE_ID]

    # Persist last known state across restarts
    store = Store(hass, _STORAGE_VERSION, f"{DOMAIN}_{device_id}_state")
    stored = await store.async_load() or {}
    _last_good_state: dict = dict(stored)

    async def async_update_data() -> dict:
        nonlocal _last_good_state
        try:
            state = await hass.async_add_executor_job(api.get_state, device_id)
            _last_good_state = state
            await store.async_save(state)
            return state
        except ZentralyAuthError as exc:
            raise ConfigEntryAuthFailed(str(exc)) from exc
        except ZentralyConnectionError as exc:
            if _last_good_state:
                _LOGGER.warning(
                    "Zentraly: thermostat unreachable (%s), using persisted state",
                    exc,
                )
                return _last_good_state
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
