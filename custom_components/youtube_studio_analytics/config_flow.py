"""Config flow for YouTube Studio Analytics integration."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any

# Log immediately when module is imported
_LOGGER = logging.getLogger(__name__)
_LOGGER.info("config_flow.py: Module is being imported")

try:
    from homeassistant import config_entries
    from homeassistant.core import HomeAssistant
    from homeassistant.data_entry_flow import FlowResult
    from homeassistant.exceptions import HomeAssistantError
    from homeassistant.helpers import config_entry_oauth2_flow
    
    from .const import DEFAULT_UPDATE_INTERVAL, DOMAIN, OAUTH_SCOPES, OAUTH_TOKEN_URL
    
    if TYPE_CHECKING:
        from google.oauth2.credentials import Credentials
    
    _LOGGER.info("config_flow.py: All imports successful")
except Exception as err:
    _LOGGER.error("config_flow.py: Import error: %s", err, exc_info=True)
    raise


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
        _LOGGER.info("YouTubeOAuth2FlowHandler.__init__: Initializing OAuth2 flow handler")
        try:
            super().__init__()
            self._credentials: "Credentials" | None = None
            self._refresh_token: str | None = None
            self._token: str | None = None
            self._token_expiry: str | None = None
            _LOGGER.info("YouTubeOAuth2FlowHandler.__init__: OAuth2 flow handler initialized successfully")
        except Exception as err:
            _LOGGER.error("YouTubeOAuth2FlowHandler.__init__: Error initializing: %s", err, exc_info=True)
            raise

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

            # Store credentials for channel validation
            self._credentials = credentials
            
            _LOGGER.debug("async_oauth2_finish: OAuth completed, proceeding to manual channel ID entry")
            # Skip channel discovery (managedByMe=True has issues with brand channels)
            # User will manually enter channel ID instead
            return await self.async_step_channel_entry()

        except Exception as err:
            _LOGGER.exception("Error finishing OAuth flow: %s", err)
            return self.async_abort(reason="oauth_failed")

    async def async_step_channel_entry(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle manual channel ID entry step."""
        _LOGGER.debug("async_step_channel_entry: Starting manual channel ID entry step")
        errors: dict[str, str] = {}
        channel_title: str | None = None

        if user_input is not None:
            channel_id = user_input.get("channel_id", "").strip()
            _LOGGER.debug("async_step_channel_entry: User entered channel ID: %s", channel_id)

            if not channel_id:
                errors["channel_id"] = "channel_id_required"
            else:
                # Validate channel ID by fetching channel info
                try:
                    from googleapiclient.discovery import build
                    
                    _LOGGER.debug("async_step_channel_entry: Validating channel ID")
                    # Refresh credentials to ensure we have a valid token
                    if self._credentials and hasattr(self._credentials, 'refresh'):
                        from google.auth.transport.requests import Request
                        await self.hass.async_add_executor_job(self._credentials.refresh, Request())
                    
                    service = await self.hass.async_add_executor_job(
                        build, "youtube", "v3", credentials=self._credentials
                    )
                    
                    channel_response = await self.hass.async_add_executor_job(
                        service.channels().list(part="snippet,statistics", id=channel_id).execute
                    )
                    
                    if channel_response.get("items"):
                        channel_info = channel_response["items"][0]
                        channel_title = channel_info["snippet"]["title"]
                        _LOGGER.debug("async_step_channel_entry: Channel validated: %s (%s)", channel_title, channel_id)
                        
                        if not self._refresh_token:
                            _LOGGER.error("async_step_channel_entry: Refresh token not available")
                            return self.async_abort(reason="oauth_failed")
                        
                        _LOGGER.debug("async_step_channel_entry: Creating config entry")
                        return self.async_create_entry(
                            title=f"YouTube: {channel_title}",
                            data={
                                "refresh_token": self._refresh_token,
                                "token": self._token,
                                "token_expiry": self._token_expiry,
                                "channel_id": channel_id,
                                "channel_title": channel_title,
                            },
                        )
                    else:
                        _LOGGER.warning("async_step_channel_entry: Channel not found or not accessible: %s", channel_id)
                        errors["channel_id"] = "channel_not_found"
                except Exception as err:
                    _LOGGER.exception("async_step_channel_entry: Error validating channel: %s", err)
                    errors["channel_id"] = "channel_validation_failed"

        # Import voluptuous inside function to avoid blocking import
        import voluptuous as vol

        data_schema = vol.Schema(
            {
                vol.Required("channel_id", default=user_input.get("channel_id", "") if user_input else ""): str,
            }
        )

        description_placeholders = {}
        if channel_title:
            description_placeholders["channel_title"] = channel_title

        return self.async_show_form(
            step_id="channel_entry",
            data_schema=data_schema,
            errors=errors,
            description_placeholders=description_placeholders,
        )
