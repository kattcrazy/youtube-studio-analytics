"""YouTube Studio Analytics integration for Home Assistant."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry, ConfigEntryAuthFailed
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.components.application_credentials import async_import_client_credential

from .const import DEFAULT_UPDATE_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up YouTube Studio Analytics integration."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up YouTube Studio Analytics from a config entry."""
    # Import API and coordinator inside function to avoid blocking import
    from .api import YouTubeAnalyticsAPI
    from .coordinator import YouTubeAnalyticsDataUpdateCoordinator
    
    hass.data.setdefault(DOMAIN, {})

    refresh_token = entry.data["refresh_token"]
    channel_id = entry.data["channel_id"]
    channel_title = entry.data.get("channel_title", "YouTube Channel")
    access_token = entry.data.get("token")
    token_expiry = entry.data.get("token_expiry")
    update_interval = entry.options.get("update_interval", DEFAULT_UPDATE_INTERVAL)

    # Retrieve client credentials from application_credentials (not stored in config entry)
    credential = await async_import_client_credential(hass, DOMAIN)
    if not credential:
        _LOGGER.error("No application credentials found for %s", DOMAIN)
        return False
    
    client_id = credential.client_id
    client_secret = credential.client_secret

    _LOGGER.debug(
        "Setting up YouTube Studio Analytics for channel: %s (%s)",
        channel_title,
        channel_id,
    )

    api_client = YouTubeAnalyticsAPI(
        hass=hass,
        refresh_token=refresh_token,
        channel_id=channel_id,
        client_id=client_id,
        client_secret=client_secret,
        access_token=access_token,
        token_expiry=token_expiry,
    )

    coordinator = YouTubeAnalyticsDataUpdateCoordinator(
        hass=hass,
        config_entry=entry,
        api_client=api_client,
        update_interval=update_interval,
    )

    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryAuthFailed:
        _LOGGER.error(
            "Authentication failed during setup. Refresh token may have expired. "
            "Please reconfigure the integration."
        )
        raise

    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "api_client": api_client,
        "channel_id": channel_id,
        "channel_title": channel_title,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    await _register_device(hass, entry, channel_id, channel_title)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload YouTube Studio Analytics config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def _register_device(
    hass: HomeAssistant, entry: ConfigEntry, channel_id: str, channel_title: str
) -> None:
    """Register device in device registry."""
    device_registry = dr.async_get(hass)

    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, channel_id)},
        name=channel_title,
        manufacturer="YouTube",
        model="YouTube Channel",
    )
