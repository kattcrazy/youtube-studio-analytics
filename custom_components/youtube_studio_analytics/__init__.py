"""YouTube Studio Analytics integration for Home Assistant."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.components.application_credentials import async_import_client_credential

from .const import DEFAULT_UPDATE_INTERVAL, DOMAIN

PLATFORMS: list[Platform] = [Platform.SENSOR]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up YouTube Studio Analytics integration."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up YouTube Studio Analytics from a config entry."""
    from .api import YouTubeAnalyticsAPI
    from .coordinator import YouTubeAnalyticsDataUpdateCoordinator

    hass.data.setdefault(DOMAIN, {})
    credential = await async_import_client_credential(hass, DOMAIN)
    if not credential:
        return False

    api_client = YouTubeAnalyticsAPI(
        hass=hass,
        refresh_token=entry.data["refresh_token"],
        channel_id=entry.data["channel_id"],
        client_id=credential.client_id,
        client_secret=credential.client_secret,
        access_token=entry.data.get("token"),
        token_expiry=entry.data.get("token_expiry"),
    )
    coordinator = YouTubeAnalyticsDataUpdateCoordinator(
        hass=hass,
        config_entry=entry,
        api_client=api_client,
        update_interval=DEFAULT_UPDATE_INTERVAL,
    )
    await coordinator.async_config_entry_first_refresh()

    channel_id = entry.data["channel_id"]
    channel_title = entry.data.get("channel_title", "YouTube Channel")
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "api_client": api_client,
        "channel_id": channel_id,
        "channel_title": channel_title,
    }
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await _register_device(hass, entry, channel_id, channel_title)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload YouTube Studio Analytics config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


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
