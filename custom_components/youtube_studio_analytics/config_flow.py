"""Config flow for YouTube Studio Analytics integration."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any, Mapping

# Log immediately when module is imported
_LOGGER = logging.getLogger(__name__)
_LOGGER.info("config_flow.py: Module is being imported")

try:
from homeassistant import config_entries
    from homeassistant.config_entries import SOURCE_REAUTH
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
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler
):
    """Handle OAuth2 flow for YouTube Studio Analytics."""

    DOMAIN = DOMAIN
    VERSION = 1

    @property
    def oauth2_scopes(self) -> list[str]:
        """Return the OAuth2 scopes required for this integration."""
        return OAUTH_SCOPES

    def __init__(self) -> None:
        """Initialize OAuth2 flow handler."""
        _LOGGER.info("YouTubeOAuth2FlowHandler.__init__: Initializing OAuth2 flow handler")
        try:
        super().__init__()
            self._credentials: "Credentials" | None = None
        self._refresh_token: str | None = None
        self._token: str | None = None
        self._token_expiry: str | None = None
            self._channel_id: str | None = None  # Store channel_id before OAuth
            _LOGGER.info("YouTubeOAuth2FlowHandler.__init__: OAuth2 flow handler initialized successfully")
        except Exception as err:
            _LOGGER.error("YouTubeOAuth2FlowHandler.__init__: Error initializing: %s", err, exc_info=True)
            raise

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle initial step - collect channel ID first."""
        _LOGGER.info("async_step_user: Starting user step - YouTube Studio Analytics config flow")
        try:
        if self._async_current_entries():
                _LOGGER.info("async_step_user: Integration already configured, aborting")
            return self.async_abort(reason="already_configured")

            _LOGGER.info("async_step_user: Checking for application credentials")
            # CRITICAL: Check if credentials are available before proceeding
            # This prevents 500 errors when HA can't find the credentials
            creds = await config_entry_oauth2_flow.async_get_application_credentials(
                self.hass, DOMAIN
            )
            if creds is None:
                _LOGGER.error(
                    "async_step_user: No application credentials found for domain '%s'! "
                    "Please check /config/application_credentials.json file exists and contains "
                    "credentials for 'youtube_studio_analytics'.",
                    DOMAIN
                )
                return self.async_abort(
                    reason="missing_credentials",
                    description_placeholders={
                        "domain": DOMAIN,
                    },
                )
            
            _LOGGER.info("async_step_user: Application credentials found, proceeding to channel entry")
            # Channel ID is entered BEFORE OAuth flow
            return await self.async_step_channel_entry()
        except Exception as err:
            _LOGGER.error("async_step_user: Error in config flow: %s", err, exc_info=True)
            raise

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> FlowResult:
        """Perform reauth upon an API authentication error."""
        _LOGGER.info("async_step_reauth: Starting reauth flow")
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Dialog that informs the user that reauth is required."""
        _LOGGER.info("async_step_reauth_confirm: Showing reauth confirmation")
        if user_input is None:
            import voluptuous as vol
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=vol.Schema({}),
            )
        _LOGGER.info("async_step_reauth_confirm: User confirmed, starting OAuth flow")
        return await self.async_step_user()

    async def async_oauth_create_entry(self, data: dict[str, Any]) -> FlowResult:
        """Create an oauth config entry or update existing entry for reauth."""
        _LOGGER.debug("async_oauth_create_entry: Processing OAuth result")
        try:
            refresh_token = data.get("refresh_token")
            token = data.get("token") or data.get("access_token")
            token_expiry = data.get("token_expiry")
            
            if not refresh_token:
                _LOGGER.error("async_oauth_create_entry: No refresh token received")
                return self.async_abort(reason="oauth_failed")

            try:
                _LOGGER.debug("async_oauth_create_entry: Creating credentials from OAuth result")
                credentials, token_expiry_str = await create_credentials_from_oauth_result(
                    self.hass,
                    DOMAIN,
                    token,
                    refresh_token,
                    token_expiry,
                )
                _LOGGER.debug("async_oauth_create_entry: Credentials created successfully")
            except Exception as err:
                from homeassistant.exceptions import HomeAssistantError
                if isinstance(err, HomeAssistantError):
                    _LOGGER.error(
                        "async_oauth_create_entry: OAuth implementation unavailable: %s", err
                    )
                    return self.async_abort(reason="oauth_implementation_unavailable")
                _LOGGER.exception("async_oauth_create_entry: Unexpected error creating credentials: %s", err)
                raise

            # Store credentials for validation
            self._credentials = credentials

            # Determine channel_id for unique ID (per docs line 307 - set BEFORE checking reauth)
            channel_id: str | None = None
            if self.source == SOURCE_REAUTH:
                reauth_entry = self._get_reauth_entry()
                channel_id = reauth_entry.data.get("channel_id")
                if not channel_id:
                    _LOGGER.error("async_oauth_create_entry: No channel_id in reauth entry")
                    return self.async_abort(reason="oauth_failed")
            else:
                channel_id = self._channel_id
                if not channel_id:
                    _LOGGER.error("async_oauth_create_entry: No channel_id stored before OAuth")
                    return self.async_abort(reason="oauth_failed")
            
            # Set unique ID BEFORE checking reauth (per docs line 307, but with await per line 343)
            await self.async_set_unique_id(channel_id)

            # Handle reauth flow (per docs line 308-313)
            if self.source == SOURCE_REAUTH:
                _LOGGER.info("async_oauth_create_entry: Handling reauth flow")
                # Verify unique ID matches (per docs line 309)
                self._abort_if_unique_id_mismatch()
                
                # Validate the channel ID is still accessible
                try:
                    from googleapiclient.discovery import build
                    from google.auth.transport.requests import Request
                    
                    if self._credentials and hasattr(self._credentials, 'refresh'):
                        await self.hass.async_add_executor_job(self._credentials.refresh, Request())
                    
                    service = await self.hass.async_add_executor_job(
                        build, "youtube", "v3", credentials=self._credentials
                    )
                    channel_response = await self.hass.async_add_executor_job(
                        service.channels().list(part="snippet", id=channel_id).execute
                    )
                    
                    if channel_response.get("items"):
                        channel_title = channel_response["items"][0]["snippet"]["title"]
                        _LOGGER.info("async_oauth_create_entry: Channel validated for reauth: %s", channel_title)
                        
                        # Update the existing entry with new tokens (per docs line 310-313)
                        return self.async_update_reload_and_abort(
                            reauth_entry,
                            data_updates={
                                "refresh_token": refresh_token,
                                "token": token,
                                "token_expiry": token_expiry_str,
                            },
                        )
                    else:
                        _LOGGER.error("async_oauth_create_entry: Channel not accessible during reauth")
                        return self.async_abort(reason="oauth_failed")
                except Exception as err:
                    _LOGGER.exception("async_oauth_create_entry: Error validating channel during reauth: %s", err)
                    return self.async_abort(reason="oauth_failed")

            # Normal flow - check for duplicates (per docs line 314)
            self._abort_if_unique_id_configured()
            
            # Normal flow - validate channel with OAuth credentials and enrich data
            try:
                from googleapiclient.discovery import build
                from google.auth.transport.requests import Request
                
                if self._credentials and hasattr(self._credentials, 'refresh'):
                    await self.hass.async_add_executor_job(self._credentials.refresh, Request())
                
                service = await self.hass.async_add_executor_job(
                    build, "youtube", "v3", credentials=self._credentials
                )
                channel_response = await self.hass.async_add_executor_job(
                    service.channels().list(part="snippet,statistics", id=channel_id).execute
                )

                if not channel_response.get("items"):
                    _LOGGER.error("async_oauth_create_entry: Channel not found or not accessible: %s", channel_id)
                    return self.async_abort(reason="channel_not_found")
                
                channel_info = channel_response["items"][0]
                channel_title = channel_info["snippet"]["title"]
                _LOGGER.info("async_oauth_create_entry: Channel validated: %s (%s)", channel_title, channel_id)
                
                # Enrich data dict with channel information (per docs line 315 - call super with enriched data)
                data["channel_id"] = channel_id
                data["channel_title"] = channel_title
                # Ensure token fields are in data
                data["refresh_token"] = refresh_token
                data["token"] = token
                data["token_expiry"] = token_expiry_str
                
                # Call super() as per docs line 315
                return await super().async_oauth_create_entry(data)
            except Exception as err:
                _LOGGER.exception("async_oauth_create_entry: Error validating channel: %s", err)
                return self.async_abort(reason="channel_validation_failed")

        except Exception as err:
            _LOGGER.exception("async_oauth_create_entry: Error processing OAuth result: %s", err)
            return self.async_abort(reason="oauth_failed")

    async def async_step_channel_entry(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle manual channel ID entry step - BEFORE OAuth."""
        _LOGGER.debug("async_step_channel_entry: Starting manual channel ID entry step")
        errors: dict[str, str] = {}

        if user_input is not None:
            channel_id = user_input.get("channel_id", "").strip()
            _LOGGER.debug("async_step_channel_entry: User entered channel ID: %s", channel_id)

            if not channel_id:
                errors["channel_id"] = "channel_id_required"
            else:
                # Basic validation - just check format (starts with UC and is 24 chars)
                if not (channel_id.startswith("UC") and len(channel_id) == 24):
                    errors["channel_id"] = "channel_id_invalid_format"
                else:
                    # Store channel_id for use after OAuth
                    self._channel_id = channel_id
                    _LOGGER.info("async_step_channel_entry: Channel ID stored, proceeding to OAuth")
                    # Start OAuth flow - channel will be validated after OAuth completes
                    return await self.async_step_pick_implementation()

        # Import voluptuous inside function to avoid blocking import
        import voluptuous as vol

        data_schema = vol.Schema(
            {
                vol.Required("channel_id", default=user_input.get("channel_id", "") if user_input else ""): str,
            }
        )

        return self.async_show_form(
            step_id="channel_entry",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={},
        )
