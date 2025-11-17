"""Application credentials support for YouTube Studio Analytics."""

from __future__ import annotations

import logging
from typing import Any

# Log immediately when module is imported
_LOGGER = logging.getLogger(__name__)
_LOGGER.info("application_credentials.py: Module is being imported")

try:
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.components.application_credentials import (
    AuthImplementation,
    AuthorizationServer,
    ClientCredential,
)

from .const import DOMAIN, OAUTH_AUTHORIZE_URL, OAUTH_SCOPES, OAUTH_TOKEN_URL

    _LOGGER.info("application_credentials.py: All imports successful")
except Exception as err:
    _LOGGER.error("application_credentials.py: Import error: %s", err, exc_info=True)
    raise


class YouTubeOAuth2Implementation(AuthImplementation):
    """Custom OAuth2 implementation for YouTube with brand channel support."""

    async def async_generate_authorize_url(self, flow_id: str) -> str:
        """Generate an authorize URL."""
        _LOGGER.info("async_generate_authorize_url: Starting for flow_id: %s", flow_id)
        
        try:
            if not self.client_id:
                _LOGGER.error("async_generate_authorize_url: Missing client_id!")
                raise ValueError("Missing client_id")
            
            if not self.client_secret:
                _LOGGER.error("async_generate_authorize_url: Missing client_secret!")
                raise ValueError("Missing client_secret")
            
            _LOGGER.info("async_generate_authorize_url: Client credentials validated")

        # Use Home Assistant cloud redirect URL - no need to detect instance URL
        # This URL must be registered in Google Cloud Console as an authorized redirect URI
        redirect_uri = "https://my.home-assistant.io/redirect/oauth"
        
            _LOGGER.info("async_generate_authorize_url: Redirect URI: %s", redirect_uri)

        except Exception as err:
            _LOGGER.error("async_generate_authorize_url: Error before creating flow: %s", err, exc_info=True)
            raise

        try:
            # Import Flow inside function to avoid blocking import
            from google_auth_oauthlib.flow import Flow
            
            _LOGGER.debug("async_generate_authorize_url: Creating OAuth flow")
            # Create Flow with client config, but WITHOUT 'redirect_uris' in the config
            # We'll set flow.redirect_uri attribute instead to avoid conflicts
            flow = await self.hass.async_add_executor_job(
                Flow.from_client_config,
                {
                    "web": {
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                        "auth_uri": OAUTH_AUTHORIZE_URL,
                        "token_uri": OAUTH_TOKEN_URL,
                        # Do NOT include "redirect_uris" here - set flow.redirect_uri instead
                    }
                },
                OAUTH_SCOPES,
            )
            
            # Set flow.redirect_uri attribute - this is the definitive way to tell Flow which redirect URI to use
            flow.redirect_uri = redirect_uri
            _LOGGER.debug("async_generate_authorize_url: OAuth flow created successfully")
            _LOGGER.debug("async_generate_authorize_url: Redirect URI set on flow object: %s", redirect_uri)

            # Don't pass redirect_uri - Flow uses it from flow.redirect_uri attribute
            flow_kwargs = {
                "access_type": "offline",
                "prompt": "consent",  # Critical for brand channel support
                "include_granted_scopes": "true",
            }
            _LOGGER.debug(
                "async_generate_authorize_url: OAuth flow kwargs: %s (prompt=consent for brand channel support)",
                flow_kwargs,
            )

            _LOGGER.debug("async_generate_authorize_url: Generating authorization URL")
            auth_url, state = await self.hass.async_add_executor_job(
                lambda: flow.authorization_url(**flow_kwargs)
            )
            _LOGGER.debug("async_generate_authorize_url: Generated auth URL with state: %s", state)

            self.hass.data.setdefault(DOMAIN, {})
            self.hass.data[DOMAIN][f"oauth_flow_{state}"] = flow
            _LOGGER.debug("async_generate_authorize_url: Stored OAuth flow in hass.data")

            return auth_url
        except Exception as err:
            _LOGGER.exception("async_generate_authorize_url: Error generating authorize URL: %s", err)
            raise

    async def async_resolve_external_data(
        self, external_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Resolve external data from OAuth callback."""
        _LOGGER.debug("async_resolve_external_data: Starting resolution of external data")
        code = external_data.get("code")
        state = external_data.get("state")

        if not code or not state:
            _LOGGER.debug(
                "async_resolve_external_data: Missing code or state in OAuth callback: code=%s, state=%s",
                bool(code),
                bool(state),
            )
            raise ValueError("Missing code or state in OAuth callback")

        _LOGGER.debug("async_resolve_external_data: Looking for OAuth flow with state: %s", state)
        flow = self.hass.data.get(DOMAIN, {}).get(f"oauth_flow_{state}")
        if not flow:
            _LOGGER.debug("async_resolve_external_data: OAuth flow not found for state: %s", state)
            raise ValueError("OAuth flow not found")

        authorization_response = external_data.get("url", "")
        if not authorization_response:
            # Use Home Assistant cloud redirect URL - matches what we used in authorize URL
            redirect_uri = "https://my.home-assistant.io/redirect/oauth"
            authorization_response = f"{redirect_uri}?code={code}&state={state}"
            _LOGGER.debug("async_resolve_external_data: Constructed authorization response URL")

        _LOGGER.debug("async_resolve_external_data: Fetching token from authorization response")
        try:
            from datetime import datetime
            from google.oauth2.credentials import Credentials

            token_data = await self.hass.async_add_executor_job(
                flow.fetch_token, authorization_response=authorization_response
            )

            if not token_data or not token_data.get("refresh_token"):
                _LOGGER.debug("async_resolve_external_data: No refresh token received from OAuth flow")
                raise ValueError("No refresh token received")

            refresh_token = token_data.get("refresh_token")
            access_token = token_data.get("access_token") or token_data.get("token")
            
            _LOGGER.debug("async_resolve_external_data: Parsing token expiry")
            token_expiry = None
            if token_data.get("expires_at"):
                token_expiry = datetime.fromtimestamp(token_data["expires_at"]).isoformat()
            elif token_data.get("expires_in"):
                expiry_time = datetime.utcnow().timestamp() + token_data["expires_in"]
                token_expiry = datetime.fromtimestamp(expiry_time).isoformat()

            _LOGGER.debug("async_resolve_external_data: Successfully received refresh token")
            return {
                "refresh_token": refresh_token,
                "token": access_token,
                "token_expiry": token_expiry,
            }
        except Exception as err:
            _LOGGER.exception("async_resolve_external_data: Error resolving external data: %s", err)
            raise


async def async_get_auth_implementation(
    hass: HomeAssistant, auth_domain: str, credential: ClientCredential
) -> config_entry_oauth2_flow.AbstractOAuth2Implementation:
    """Return auth implementation for a custom auth implementation."""
    _LOGGER.info("async_get_auth_implementation: Creating OAuth2 implementation for domain %s", auth_domain)
    try:
        if not credential:
            _LOGGER.error("async_get_auth_implementation: No credential provided!")
            raise ValueError("No credential provided")
        
        if not credential.client_id:
            _LOGGER.error("async_get_auth_implementation: Credential missing client_id!")
            raise ValueError("Credential missing client_id")
        
        if not credential.client_secret:
            _LOGGER.error("async_get_auth_implementation: Credential missing client_secret!")
            raise ValueError("Credential missing client_secret")
        
        _LOGGER.info("async_get_auth_implementation: Credential validation passed, creating implementation")
        implementation = YouTubeOAuth2Implementation(
        hass,
        auth_domain,
        credential,
        AuthorizationServer(
            authorize_url=OAUTH_AUTHORIZE_URL, token_url=OAUTH_TOKEN_URL
        ),
    )
        _LOGGER.info("async_get_auth_implementation: OAuth2 implementation created successfully")
        return implementation
    except Exception as err:
        _LOGGER.error("async_get_auth_implementation: Error creating OAuth2 implementation: %s", err, exc_info=True)
        raise


async def async_get_description_placeholders(hass: HomeAssistant) -> dict[str, str]:
    """Return description placeholders for the credentials dialog."""
    _LOGGER.debug("async_get_description_placeholders: Returning placeholders")
    return {
        "console_url": "https://console.cloud.google.com/apis/credentials",
    }

