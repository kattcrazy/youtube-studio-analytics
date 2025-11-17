"""Helper functions for YouTube Studio Analytics config flow."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .const import OAUTH_SCOPES, OAUTH_TOKEN_URL

if TYPE_CHECKING:
    from google.oauth2.credentials import Credentials

_LOGGER = logging.getLogger(__name__)


async def create_credentials_from_oauth_result(
    hass: HomeAssistant,
    domain: str,
    token: str | None,
    refresh_token: str,
    token_expiry: str | None,
) -> tuple["Credentials", str | None]:
    """Create Google Credentials object from OAuth result.
    
    Args:
        hass: Home Assistant instance.
        domain: Integration domain.
        token: Access token.
        refresh_token: Refresh token.
        token_expiry: Token expiry timestamp (ISO format string or datetime).
        
    Returns:
        Tuple of (Credentials object, token_expiry as ISO string).
        
    Raises:
        HomeAssistantError: If credentials cannot be retrieved.
    """
    # Import Credentials inside function to avoid blocking import
    from google.oauth2.credentials import Credentials
    # Import async_import_client_credential inside function to avoid blocking import
    from homeassistant.components.application_credentials import async_import_client_credential
    
    credential = await async_import_client_credential(hass, domain)
    if not credential:
        raise HomeAssistantError("OAuth credentials not available from Application Credentials")
    
    expiry = None
    if token_expiry:
        try:
            if isinstance(token_expiry, str):
                expiry = datetime.fromisoformat(token_expiry.replace("Z", "+00:00"))
            else:
                expiry = token_expiry
        except (ValueError, AttributeError):
            _LOGGER.warning("Could not parse token_expiry: %s", token_expiry)
            expiry = None
    
    credentials = Credentials(
        token=token,
        refresh_token=refresh_token,
        token_uri=OAUTH_TOKEN_URL,
        client_id=credential.client_id,
        client_secret=credential.client_secret,
        scopes=OAUTH_SCOPES,
        expiry=expiry,
    )
    
    token_expiry_str = token_expiry or (credentials.expiry.isoformat() if credentials.expiry else None)
    
    return credentials, token_expiry_str


async def fetch_accessible_channels(
    hass: HomeAssistant,
    credentials: "Credentials",
) -> list[dict[str, Any]]:
    """Fetch all accessible YouTube channels (personal and brand).
    
    Args:
        hass: Home Assistant instance.
        credentials: Google OAuth credentials.
        
    Returns:
        List of channel dictionaries with 'id', 'title', and 'type' keys.
        
    Raises:
        Exception: If channel fetching fails.
    """
    channels: list[dict[str, Any]] = []
    _LOGGER.debug("Starting channel discovery (personal and brand)")

    try:
        # Import build inside function to avoid blocking import
        from googleapiclient.discovery import build
        
        service = await hass.async_add_executor_job(
            build, "youtube", "v3", credentials=credentials
        )

        _LOGGER.debug("Fetching personal channels (mine=True)")
        channels_mine = await hass.async_add_executor_job(
            service.channels().list(part="snippet", mine=True).execute
        )
        _LOGGER.debug("Found %d personal channels", len(channels_mine.get("items", [])))

        _LOGGER.debug("Fetching brand channels (managedByMe=True)")
        channels_managed = await hass.async_add_executor_job(
            service.channels().list(part="snippet", managedByMe=True).execute
        )
        _LOGGER.debug("Found %d brand/managed channels", len(channels_managed.get("items", [])))

        channel_ids_seen = set()

        for channel in channels_mine.get("items", []):
            channel_id = channel["id"]
            if channel_id not in channel_ids_seen:
                channels.append(
                    {
                        "id": channel_id,
                        "title": channel["snippet"]["title"],
                        "type": "Personal",
                    }
                )
                channel_ids_seen.add(channel_id)

        for channel in channels_managed.get("items", []):
            channel_id = channel["id"]
            if channel_id not in channel_ids_seen:
                channels.append(
                    {
                        "id": channel_id,
                        "title": channel["snippet"]["title"],
                        "type": "Brand",
                    }
                )
                channel_ids_seen.add(channel_id)

        _LOGGER.debug("Found %d accessible channels", len(channels))
        return channels

    except Exception as err:
        _LOGGER.exception("Error fetching channels: %s", err)
        raise

