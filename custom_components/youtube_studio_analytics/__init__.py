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
    _LOGGER.debug("async_setup: Initializing YouTube Studio Analytics integration")
    hass.data.setdefault(DOMAIN, {})
    _LOGGER.debug("async_setup: Integration initialized")
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up YouTube Studio Analytics from a config entry."""
    _LOGGER.debug("async_setup_entry: Starting setup for entry %s", entry.entry_id)
    # Import API and coordinator inside function to avoid blocking import
    from .api import YouTubeAnalyticsAPI
    from .coordinator import YouTubeAnalyticsDataUpdateCoordinator
    
    hass.data.setdefault(DOMAIN, {})

    _LOGGER.debug("async_setup_entry: Extracting config entry data")
    refresh_token = entry.data["refresh_token"]
    channel_id = entry.data["channel_id"]
    channel_title = entry.data.get("channel_title", "YouTube Channel")
    access_token = entry.data.get("token")
    token_expiry = entry.data.get("token_expiry")
    update_interval = DEFAULT_UPDATE_INTERVAL

    _LOGGER.debug("async_setup_entry: Retrieving application credentials")
    # Retrieve client credentials from application_credentials (not stored in config entry)
    credential = await async_import_client_credential(hass, DOMAIN)
    if not credential:
        _LOGGER.error("async_setup_entry: No application credentials found for %s", DOMAIN)
        return False
    
    client_id = credential.client_id
    client_secret = credential.client_secret

    _LOGGER.debug(
        "async_setup_entry: Setting up YouTube Studio Analytics for channel: %s (%s)",
        channel_title,
        channel_id,
    )

    _LOGGER.debug("async_setup_entry: Creating API client")
    api_client = YouTubeAnalyticsAPI(
        hass=hass,
        refresh_token=refresh_token,
        channel_id=channel_id,
        client_id=client_id,
        client_secret=client_secret,
        access_token=access_token,
        token_expiry=token_expiry,
    )

    _LOGGER.debug("async_setup_entry: Creating coordinator with update interval %d seconds", update_interval)
    coordinator = YouTubeAnalyticsDataUpdateCoordinator(
        hass=hass,
        config_entry=entry,
        api_client=api_client,
        update_interval=update_interval,
    )

    _LOGGER.debug("async_setup_entry: Performing first refresh")
    try:
        await coordinator.async_config_entry_first_refresh()
        _LOGGER.debug("async_setup_entry: First refresh completed successfully")
    except ConfigEntryAuthFailed:
        _LOGGER.error(
            "async_setup_entry: Authentication failed during setup. Refresh token may have expired. "
            "Please reconfigure the integration."
        )
        raise

    _LOGGER.debug("async_setup_entry: Storing coordinator and API client in hass.data")
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "api_client": api_client,
        "channel_id": channel_id,
        "channel_title": channel_title,
    }

    _LOGGER.debug("async_setup_entry: Forwarding entry setups for platforms: %s", PLATFORMS)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _LOGGER.debug("async_setup_entry: Registering device")
    await _register_device(hass, entry, channel_id, channel_title)

    _LOGGER.debug("async_setup_entry: Setup completed successfully")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload YouTube Studio Analytics config entry."""
    _LOGGER.debug("async_unload_entry: Starting unload for entry %s", entry.entry_id)
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        _LOGGER.debug("async_unload_entry: Removing entry data from hass.data")
        hass.data[DOMAIN].pop(entry.entry_id)
    else:
        _LOGGER.warning("async_unload_entry: Failed to unload platforms")

    _LOGGER.debug("async_unload_entry: Unload completed, result: %s", unload_ok)
    return unload_ok


async def _register_device(
    hass: HomeAssistant, entry: ConfigEntry, channel_id: str, channel_title: str
) -> None:
    """Register device in device registry."""
    _LOGGER.debug("_register_device: Registering device for channel %s (%s)", channel_title, channel_id)
    device_registry = dr.async_get(hass)

    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, channel_id)},
        name=channel_title,
        manufacturer="YouTube",
        model="YouTube Channel",
    )
    _LOGGER.debug("_register_device: Device registered successfully")
