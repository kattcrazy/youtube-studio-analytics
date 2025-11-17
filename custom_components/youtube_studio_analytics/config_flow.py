"""Config flow for YouTube Studio Analytics integration."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any, Mapping

from homeassistant import config_entries
from homeassistant.config_entries import SOURCE_REAUTH
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_entry_oauth2_flow

from .const import DEFAULT_UPDATE_INTERVAL, DOMAIN, OAUTH_SCOPES, OAUTH_TOKEN_URL

_LOGGER = logging.getLogger(__name__)

if TYPE_CHECKING:
    from google.oauth2.credentials import Credentials


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
    from google.oauth2.credentials import Credentials
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
            expiry = None
    
    credentials = Credentials(
        token=None,  # Always None - we'll refresh to get a valid token
        refresh_token=refresh_token,
        token_uri=OAUTH_TOKEN_URL,
        client_id=credential.client_id,
        client_secret=credential.client_secret,
        scopes=OAUTH_SCOPES,
        expiry=expiry,
    )
    
    # Always refresh credentials to get a valid access token (matches test_oauth_flow.py pattern)
    from google.auth.transport.requests import Request
    await hass.async_add_executor_job(credentials.refresh, Request())
    
    token_expiry_str = credentials.expiry.isoformat() if credentials.expiry else None
    
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
    from googleapiclient.discovery import build
    
    channels: list[dict[str, Any]] = []
    service = await hass.async_add_executor_job(
        build, "youtube", "v3", credentials=credentials
    )

    channels_mine = await hass.async_add_executor_job(
        service.channels().list(part="snippet", mine=True).execute
    )

    channels_managed = await hass.async_add_executor_job(
        service.channels().list(part="snippet", managedByMe=True).execute
    )

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

    return channels


class ConfigFlow(
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler, domain=DOMAIN
):
    """Handle OAuth2 flow for YouTube Studio Analytics."""

    VERSION = 1

    @property
    def oauth2_scopes(self) -> list[str]:
        """Return the OAuth2 scopes required for this integration."""
        return OAUTH_SCOPES

    def __init__(self) -> None:
        """Initialize OAuth2 flow handler."""
        super().__init__()
        self._credentials: "Credentials" | None = None
        self._refresh_token: str | None = None
        self._token: str | None = None
        self._token_expiry: str | None = None
        self._channel_id: str | None = None  # Store channel_id before OAuth

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle initial step - collect channel ID first."""
        if self._async_current_entries():
            return self.async_abort(reason="already_configured")

        creds = await config_entry_oauth2_flow.async_get_application_credentials(
            self.hass, DOMAIN
        )
        if creds is None:
            return self.async_abort(
                reason="missing_credentials",
                description_placeholders={
                    "domain": DOMAIN,
                },
            )
        
        return await self.async_step_channel_entry()

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> FlowResult:
        """Perform reauth upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Dialog that informs the user that reauth is required."""
        if user_input is None:
            import voluptuous as vol
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=vol.Schema({}),
            )
        return await self.async_step_user()

    async def async_oauth_create_entry(self, data: dict[str, Any]) -> FlowResult:
        """Create an oauth config entry or update existing entry for reauth."""
        refresh_token = data.get("refresh_token")
        token = data.get("token") or data.get("access_token")
        token_expiry = data.get("token_expiry")
        
        if not refresh_token:
            return self.async_abort(reason="oauth_failed")

        try:
            credentials, token_expiry_str = await create_credentials_from_oauth_result(
                self.hass,
                DOMAIN,
                token,
                refresh_token,
                token_expiry,
            )
        except HomeAssistantError as err:
            _LOGGER.error("OAuth credentials not available: %s", err)
            return self.async_abort(reason="oauth_implementation_unavailable")
        except Exception as err:
            _LOGGER.error("OAuth failed: %s", err)
            return self.async_abort(reason="oauth_failed")

        self._credentials = credentials

        channel_id: str | None = None
        if self.source == SOURCE_REAUTH:
            reauth_entry = self._get_reauth_entry()
            channel_id = reauth_entry.data.get("channel_id")
            if not channel_id:
                return self.async_abort(reason="oauth_failed")
        else:
            channel_id = self._channel_id
            if not channel_id:
                return self.async_abort(reason="oauth_failed")
        
        await self.async_set_unique_id(channel_id)

        if self.source == SOURCE_REAUTH:
            self._abort_if_unique_id_mismatch()
            
            try:
                from googleapiclient.discovery import build
                from google.auth.transport.requests import Request
                from googleapiclient.errors import HttpError
                
                if self._credentials and hasattr(self._credentials, 'refresh'):
                    await self.hass.async_add_executor_job(self._credentials.refresh, Request())
                
                service = await self.hass.async_add_executor_job(
                    build, "youtube", "v3", credentials=self._credentials
                )
                channel_response = await self.hass.async_add_executor_job(
                    service.channels().list(part="snippet", id=channel_id).execute
                )
                
                if channel_response.get("items"):
                    return self.async_update_reload_and_abort(
                        reauth_entry,
                        data_updates={
                            "refresh_token": refresh_token,
                            "token": token,
                            "token_expiry": token_expiry_str,
                        },
                    )
                _LOGGER.error("Channel not found during reauth for channel_id: %s", channel_id)
                return self.async_abort(reason="oauth_failed")
            except HttpError as err:
                status_code = getattr(err.resp, "status", "unknown") if hasattr(err, "resp") else "unknown"
                _LOGGER.error("HTTP error %s during reauth: %s", status_code, err)
                if status_code == 500:
                    _LOGGER.error("YouTube API returned 500 error - this is a server-side issue with YouTube's API")
                return self.async_abort(reason="oauth_failed")
            except Exception as err:
                _LOGGER.error("Reauth failed: %s", err)
                return self.async_abort(reason="oauth_failed")

        self._abort_if_unique_id_configured()
        
        try:
            from googleapiclient.discovery import build
            from google.auth.transport.requests import Request
            from googleapiclient.errors import HttpError
            
            if self._credentials and hasattr(self._credentials, 'refresh'):
                await self.hass.async_add_executor_job(self._credentials.refresh, Request())
            
            service = await self.hass.async_add_executor_job(
                build, "youtube", "v3", credentials=self._credentials
            )
            channel_response = await self.hass.async_add_executor_job(
                service.channels().list(part="snippet,statistics", id=channel_id).execute
            )

            if not channel_response.get("items"):
                _LOGGER.error("Channel not found: %s", channel_id)
                return self.async_abort(reason="channel_not_found")
            
            channel_info = channel_response["items"][0]
            channel_title = channel_info["snippet"]["title"]
            
            data["channel_id"] = channel_id
            data["channel_title"] = channel_title
            data["refresh_token"] = refresh_token
            data["token"] = token
            data["token_expiry"] = token_expiry_str
            
            return await super().async_oauth_create_entry(data)
        except HttpError as err:
            status_code = getattr(err.resp, "status", "unknown") if hasattr(err, "resp") else "unknown"
            _LOGGER.error("HTTP error %s during channel validation: %s", status_code, err)
            if status_code == 500:
                _LOGGER.error("YouTube API returned 500 error - this is a server-side issue with YouTube's API")
            return self.async_abort(reason="channel_validation_failed")
        except Exception as err:
            _LOGGER.error("Channel validation failed: %s", err)
            return self.async_abort(reason="channel_validation_failed")

    async def async_step_channel_entry(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle manual channel ID entry step - BEFORE OAuth."""
        errors: dict[str, str] = {}

        if user_input is not None:
            channel_id = user_input.get("channel_id", "").strip()

            if not channel_id:
                errors["channel_id"] = "channel_id_required"
            else:
                if not (channel_id.startswith("UC") and len(channel_id) == 24):
                    errors["channel_id"] = "channel_id_invalid_format"
                else:
                    self._channel_id = channel_id
                    return await self.async_step_pick_implementation()

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
