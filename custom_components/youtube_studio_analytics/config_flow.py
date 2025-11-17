"""Config flow for YouTube Studio Analytics integration."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_entry_oauth2_flow

from .const import DEFAULT_UPDATE_INTERVAL, DOMAIN, OAUTH_SCOPES, OAUTH_TOKEN_URL

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
    _LOGGER.debug("create_credentials_from_oauth_result: Starting")
    # Import Credentials inside function to avoid blocking import
    from google.oauth2.credentials import Credentials
    # Import async_import_client_credential inside function to avoid blocking import
    from homeassistant.components.application_credentials import async_import_client_credential
    
    _LOGGER.debug("create_credentials_from_oauth_result: Importing client credential for domain %s", domain)
    credential = await async_import_client_credential(hass, domain)
    if not credential:
        _LOGGER.error("create_credentials_from_oauth_result: No credential found")
        raise HomeAssistantError("OAuth credentials not available from Application Credentials")
    
    _LOGGER.debug("create_credentials_from_oauth_result: Parsing token expiry")
    expiry = None
    if token_expiry:
        try:
            if isinstance(token_expiry, str):
                expiry = datetime.fromisoformat(token_expiry.replace("Z", "+00:00"))
            else:
                expiry = token_expiry
        except (ValueError, AttributeError) as err:
            _LOGGER.warning("create_credentials_from_oauth_result: Could not parse token_expiry: %s", token_expiry)
            expiry = None
    
    _LOGGER.debug("create_credentials_from_oauth_result: Creating Credentials object")
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
    _LOGGER.debug("create_credentials_from_oauth_result: Completed successfully")
    
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
    _LOGGER.debug("fetch_accessible_channels: Starting channel discovery (personal and brand)")
    channels: list[dict[str, Any]] = []

    try:
        # Import build inside function to avoid blocking import
        from googleapiclient.discovery import build
        
        _LOGGER.debug("fetch_accessible_channels: Building YouTube service")
        service = await hass.async_add_executor_job(
            build, "youtube", "v3", credentials=credentials
        )

        _LOGGER.debug("fetch_accessible_channels: Fetching personal channels (mine=True)")
        channels_mine = await hass.async_add_executor_job(
            service.channels().list(part="snippet", mine=True).execute
        )
        _LOGGER.debug("fetch_accessible_channels: Found %d personal channels", len(channels_mine.get("items", [])))

        _LOGGER.debug("fetch_accessible_channels: Fetching brand channels (managedByMe=True)")
        channels_managed = await hass.async_add_executor_job(
            service.channels().list(part="snippet", managedByMe=True).execute
        )
        _LOGGER.debug("fetch_accessible_channels: Found %d brand/managed channels", len(channels_managed.get("items", [])))

        channel_ids_seen = set()

        _LOGGER.debug("fetch_accessible_channels: Processing personal channels")
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

        _LOGGER.debug("fetch_accessible_channels: Processing brand channels")
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

        _LOGGER.debug("fetch_accessible_channels: Found %d total accessible channels", len(channels))
        return channels

    except Exception as err:
        _LOGGER.exception("fetch_accessible_channels: Error fetching channels: %s", err)
        raise


class YouTubeOAuth2FlowHandler(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Handle OAuth2 flow for YouTube Studio Analytics."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize OAuth2 flow handler."""
        super().__init__()
        self._channels: list[dict[str, Any]] = []
        self._refresh_token: str | None = None
        self._token: str | None = None
        self._token_expiry: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle initial step - start OAuth flow."""
        _LOGGER.info("async_step_user: Starting user step - YouTube Studio Analytics config flow")
        try:
            if self._async_current_entries():
                _LOGGER.info("async_step_user: Integration already configured, aborting")
                return self.async_abort(reason="already_configured")

            _LOGGER.info("async_step_user: Starting OAuth2 flow - checking for application credentials")
            # Start OAuth2 flow - credentials are managed by application_credentials component
            # The parent class will handle checking for credentials availability
            result = await self.async_step_pick_implementation()
            _LOGGER.info("async_step_user: OAuth2 flow step completed")
            return result
        except Exception as err:
            _LOGGER.error("async_step_user: Error in config flow: %s", err, exc_info=True)
            raise

    async def async_oauth2_finish(self, result: dict[str, Any]) -> FlowResult:
        """Handle OAuth callback."""
        _LOGGER.debug("OAuth flow finished, processing result")
        try:
            refresh_token = result.get("refresh_token")
            token = result.get("token") or result.get("access_token")
            token_expiry = result.get("token_expiry")
            
            if not refresh_token:
                _LOGGER.debug("No refresh token received from OAuth flow")
                return self.async_abort(reason="oauth_failed")

            try:
                _LOGGER.debug("async_oauth2_finish: Creating credentials from OAuth result")
                credentials, token_expiry_str = await create_credentials_from_oauth_result(
                    self.hass,
                    DOMAIN,
                    token,
                    refresh_token,
                    token_expiry,
                )
                _LOGGER.debug("async_oauth2_finish: Credentials created successfully")
            except Exception as err:
                # Import HomeAssistantError inside except block to avoid blocking import
                from homeassistant.exceptions import HomeAssistantError
                if isinstance(err, HomeAssistantError):
                    _LOGGER.error(
                        "async_oauth2_finish: OAuth implementation unavailable: %s", err
                    )
                    return self.async_abort(reason="oauth_implementation_unavailable")
                _LOGGER.exception("async_oauth2_finish: Unexpected error creating credentials: %s", err)
                raise

            # Store tokens temporarily for use in channel selection step
            self._refresh_token = refresh_token
            self._token = token
            self._token_expiry = token_expiry_str

            _LOGGER.debug("async_oauth2_finish: Fetching channels (personal and brand)")
            self._channels = await fetch_accessible_channels(self.hass, credentials)

            _LOGGER.debug("async_oauth2_finish: Found %d accessible channels", len(self._channels))
            if not self._channels:
                _LOGGER.warning("async_oauth2_finish: No accessible channels found")
                return self.async_abort(reason="no_channels")

            if len(self._channels) == 1:
                _LOGGER.debug("async_oauth2_finish: Only one channel found, auto-selecting: %s", self._channels[0]["title"])
                return await self.async_step_channel_selection(
                    {"channel_id": self._channels[0]["id"]}
                )

            _LOGGER.debug("async_oauth2_finish: Multiple channels found, showing selection")
            return await self.async_step_channel_selection()

        except Exception as err:
            _LOGGER.exception("Error finishing OAuth flow: %s", err)
            return self.async_abort(reason="oauth_failed")

    async def async_step_channel_selection(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle channel selection step."""
        _LOGGER.debug("async_step_channel_selection: Starting channel selection step")
        errors: dict[str, str] = {}

        if user_input is not None:
            _LOGGER.debug("async_step_channel_selection: User input received: %s", user_input.get("channel_id"))
            channel_id = user_input.get("channel_id")
            selected_channel = next(
                (ch for ch in self._channels if ch["id"] == channel_id), None
            )

            if selected_channel:
                _LOGGER.debug("async_step_channel_selection: Channel selected: %s (%s)", selected_channel["title"], channel_id)
                if not self._refresh_token:
                    _LOGGER.error("async_step_channel_selection: Refresh token not available")
                    return self.async_abort(reason="oauth_failed")
                
                _LOGGER.debug("async_step_channel_selection: Creating config entry")
                # Note: client_id and client_secret are NOT stored in config entry
                # They are retrieved from application_credentials when needed
                return self.async_create_entry(
                    title=f"YouTube: {selected_channel['title']}",
                    data={
                        "refresh_token": self._refresh_token,
                        "token": self._token,
                        "token_expiry": self._token_expiry,
                        "channel_id": channel_id,
                        "channel_title": selected_channel["title"],
                    },
                )

            _LOGGER.warning("async_step_channel_selection: Channel not found: %s", channel_id)
            errors["base"] = "channel_not_found"

        if not self._channels:
            _LOGGER.error("async_step_channel_selection: No channels available")
            return self.async_abort(reason="no_channels")

        # Import voluptuous inside function to avoid blocking import
        import voluptuous as vol

        _LOGGER.debug("async_step_channel_selection: Building channel selection form with %d channels", len(self._channels))
        channel_options = {
            channel["id"]: f"{channel['title']} ({channel['type']})"
            for channel in self._channels
        }

        data_schema = vol.Schema(
            {
                vol.Required("channel_id"): vol.In(channel_options),
            }
        )

        return self.async_show_form(
            step_id="channel_selection",
            data_schema=data_schema,
            errors=errors,
        )
