"""Application credentials support for YouTube Studio Analytics."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.components.application_credentials import (
    AuthImplementation,
    AuthorizationServer,
    ClientCredential,
)

from .const import DOMAIN, OAUTH_AUTHORIZE_URL, OAUTH_SCOPES, OAUTH_TOKEN_URL


class YouTubeOAuth2Implementation(AuthImplementation):
    """Custom OAuth2 implementation for YouTube with brand channel support."""

    async def async_generate_authorize_url(self, flow_id: str) -> str:
        """Generate an authorize URL."""
        if not self.client_id or not self.client_secret:
            raise ValueError("Missing client credentials")
            from google_auth_oauthlib.flow import Flow
            flow = await self.hass.async_add_executor_job(
                Flow.from_client_config,
                {
                    "web": {
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                        "auth_uri": OAUTH_AUTHORIZE_URL,
                        "token_uri": OAUTH_TOKEN_URL,
                    }
                },
                OAUTH_SCOPES,
            )
        flow.redirect_uri = "https://my.home-assistant.io/redirect/oauth"
            auth_url, state = await self.hass.async_add_executor_job(
            lambda: flow.authorization_url(
                access_type="offline", prompt="consent", include_granted_scopes="true"
            )
        )
            self.hass.data.setdefault(DOMAIN, {})
            self.hass.data[DOMAIN][f"oauth_flow_{state}"] = flow
            return auth_url

    async def async_resolve_external_data(
        self, external_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Resolve external data from OAuth callback."""
        code = external_data.get("code")
        state = external_data.get("state")
        if not code or not state:
            raise ValueError("Missing code or state in OAuth callback")
        flow = self.hass.data.get(DOMAIN, {}).get(f"oauth_flow_{state}")
        if not flow:
            raise ValueError("OAuth flow not found")
        authorization_response = external_data.get("url") or f"https://my.home-assistant.io/redirect/oauth?code={code}&state={state}"
            from datetime import datetime
            token_data = await self.hass.async_add_executor_job(
                flow.fetch_token, authorization_response=authorization_response
            )
            if not token_data or not token_data.get("refresh_token"):
                raise ValueError("No refresh token received")
            token_expiry = None
            if token_data.get("expires_at"):
                token_expiry = datetime.fromtimestamp(token_data["expires_at"]).isoformat()
            elif token_data.get("expires_in"):
            token_expiry = datetime.fromtimestamp(
                datetime.utcnow().timestamp() + token_data["expires_in"]
            ).isoformat()
            return {
            "refresh_token": token_data.get("refresh_token"),
            "token": token_data.get("access_token") or token_data.get("token"),
                "token_expiry": token_expiry,
            }


async def async_get_auth_implementation(
    hass: HomeAssistant, auth_domain: str, credential: ClientCredential
) -> config_entry_oauth2_flow.AbstractOAuth2Implementation:
    """Return auth implementation for a custom auth implementation."""
    if not credential or not credential.client_id or not credential.client_secret:
        raise ValueError("Invalid credential provided")
    return YouTubeOAuth2Implementation(
        hass,
        auth_domain,
        credential,
        AuthorizationServer(authorize_url=OAUTH_AUTHORIZE_URL, token_url=OAUTH_TOKEN_URL),
    )


async def async_get_description_placeholders(hass: HomeAssistant) -> dict[str, str]:
    """Return description placeholders for the credentials dialog."""
    return {
        "console_url": "https://console.cloud.google.com/apis/credentials",
    }

