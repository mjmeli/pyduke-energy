"""Client for interacting with the Duke Energy API"""

import asyncio
import logging
from datetime import datetime, timedelta, date, timezone
from os import access
from typing import Optional
from urllib.parse import urljoin
from aiohttp import ClientSession, ClientTimeout, FormData
from aiohttp.client_exceptions import ClientError

from pyduke_energy.const import (
    CUST_API_BASE_URL,
    CUST_PILOT_API_BASE_URL,
    IOT_API_BASE_URL,
    DEFAULT_TIMEOUT
)
from pyduke_energy.types import (
    Account,
    AccountDetails,
    MeterInfo,
    GatewayStatus,
    UsageMeasurement
)
from pyduke_energy.utils import (
    date_to_utc_timestamp
)
from pyduke_energy.errors import (
    RequestError,
    InputError
)

_LOGGER = logging.getLogger(__name__)

class _BaseAuthInfo:
    def __init__(self):
        self.access_token: Optional[str] = None
        self.expires: Optional[datetime] = None

    def needs_new_access_token(self):
        return self.access_token is None or self.expires is None or datetime.now() > self.expires

    def set_new_access_token(self, access_token, expires):
        self.access_token = access_token
        self.expires = datetime.now() + timedelta(seconds=int(expires))

    def clear_access_token(self):
        self.access_token = None
        self.expires = None

class _OAuthAuthInfo(_BaseAuthInfo):
    def __init__(self):
        super().__init__()
        self.internal_user_id: Optional[str] = None

class _GatewayAuthInfo(_BaseAuthInfo):
    def __init__(self):
        super().__init__()
        self.meter_id: Optional[str] = None
        self.activation_date: Optional[datetime] = None
        self.id_token: Optional[str] = None

class DukeEnergyClient:

    def __init__(
        self,
        email: str,
        password: str,
        session: Optional[ClientSession] = None
    ):
        self._email = email
        self._password = password
        self._session = session

        # Authentication
        self._oauth_auth_info = _OAuthAuthInfo()
        self._gateway_auth_info = _GatewayAuthInfo()

    async def get_account_list(self) -> 'list[Account]':
        endpoint = "auth/account-list"
        headers = await self._get_oauth_headers()
        params = {
            "email": self._email,
            "internalUserID": self._oauth_auth_info.internal_user_id
        }
        resp = await self._async_request("GET", CUST_API_BASE_URL, endpoint, headers=headers, params=params)
        account_list = resp.get("accounts")
        return [Account(acc) for acc in account_list]

    async def get_account_details(self, src_acct_id: str, src_sys_cd: str) -> AccountDetails:
        endpoint = "auth/account-details"
        headers = await self._get_oauth_headers()
        params = {
            "email": self._email,
            "srcSysCd": src_sys_cd,
            "srcAcctId": src_acct_id
        }
        resp = await self._async_request("GET", CUST_API_BASE_URL, endpoint, headers=headers, params=params)
        return AccountDetails(resp)

    def select_meter(self, meter_id: str, activation_date: date) -> None:
        """Selects which meter will be used for gateway API calls"""
        self._gateway_auth_info.meter_id = meter_id
        self._gateway_auth_info.activation_date = activation_date
        self._gateway_auth_info.clear_access_token() # resets

    async def get_gateway_status(self) -> GatewayStatus:
        endpoint = "gw/gateways/status"
        headers = await self._get_gateway_auth_headers()
        resp = await self._async_request("GET", IOT_API_BASE_URL, endpoint, headers=headers)
        return GatewayStatus(resp)

    async def get_gateway_usage(self, range_start: datetime, range_end: datetime) -> 'list[UsageMeasurement]':
        """Gets gateway usage for a time window."""
        if range_start > range_end:
            raise InputError("Start date must be before end date")

        endpoint = "smartmeter/usageByHour"
        headers = await self._get_gateway_auth_headers()
        dt_format = "%Y-%m-%dT%H:00" # the API ignores minutes, seconds, timezone
        params = {
            "startHourDt": range_start.astimezone(timezone.utc).strftime(dt_format), # API expects dates to be UTC
            "endHourDt": range_end.astimezone(timezone.utc).strftime(dt_format)
        }
        resp = await self._async_request("GET", IOT_API_BASE_URL, endpoint, headers=headers, params=params)

        # Format is a list of objects containing the measurements, one object per hour. Here we combine all.
        raw_measurements = [mn for d in resp for mn in d.get("mn")]
        measurements = [UsageMeasurement(mn) for mn in raw_measurements]
        measurements.sort(key=lambda x: x.timestamp)
        return measurements

    async def _oauth_login(self) -> None:
        """Hits the OAuth login endpoint to generate a new access token"""
        _LOGGER.debug("Getting new OAuth auth")

        endpoint = "auth/oauth2/token"
        headers = { "Authorization": "Basic UzdmNXFQR2MwcnpVZkJmcVNPak9ycGczZWtSZ3ZHSng6bW1nS2pyY1RQRHptOERtVw==" } # hard-coded from Android app
        request = {
            "grant_type": "password",
            "username": self._email,
            "password": self._password
        }
        resp = await self._async_request("POST", CUST_API_BASE_URL, endpoint, headers=headers, data=FormData(request))
        self._oauth_auth_info.set_new_access_token(resp.get("access_token"), resp.get("expires_in"))
        self._oauth_auth_info.internal_user_id = resp.get("cdp_internal_user_id")

    async def _get_oauth_headers(self) -> dict:
        """Get the auth headers for OAuth scoped actions - logs in if new access token is needed"""
        # Get a new access token if it has expired
        if self._oauth_auth_info.needs_new_access_token():
            await self._oauth_login()
        return { 
            "Authorization": f"Bearer {self._oauth_auth_info.access_token}"
        }

    async def _gateway_login(self) -> None:
        if self._gateway_auth_info.meter_id is None:
            raise InputError("Gateway needs to be selected before calling gateway functions")

        _LOGGER.debug("Getting new gateway auth")

        endpoint = "smartmeter/v1/auth"
        headers = await self._get_oauth_headers()
        request = {
            "meterId": self._gateway_auth_info.meter_id,
            "activationDt": int(date_to_utc_timestamp(self._gateway_auth_info.activation_date)) * 1000 # ms timestamp
        }
        resp = await self._async_request("POST", CUST_PILOT_API_BASE_URL, endpoint, headers=headers, data=FormData(request))
        self._gateway_auth_info.set_new_access_token(resp.get("access_token"), resp.get("expires_in"))
        self._gateway_auth_info.id_token = resp.get("id_token")

    async def _get_gateway_auth_headers(self) -> dict:
        """Get the auth headers for gateway scoped actions - logs in if new access token is needed"""
        # Get a new access token if it has expired
        if self._gateway_auth_info.needs_new_access_token():
            await self._gateway_login()
        return { 
            "Authorization": f"Bearer {self._gateway_auth_info.access_token}",
            "de-iot-id-token": self._gateway_auth_info.id_token
        }

    async def _async_request(self, method: str, base_url: str, endpoint: str, headers: Optional[dict] = None, params: Optional[dict] = None, data: Optional[dict] = None, json: Optional[dict] = None) -> dict:
        """Make a request against the Duke Energy API."""

        use_running_session = self._session and not self._session.closed

        if use_running_session:
            session = self._session
        else:
            session = ClientSession(timeout=ClientTimeout(total=DEFAULT_TIMEOUT))

        full_url = urljoin(base_url, endpoint)

        try:
            async with session.request(method, full_url, headers=headers, params=params, data=data, json=json) as resp:
                resp.raise_for_status()
                data = await resp.json(content_type=None) # not all of their APIs return the correct content_Type
                return data
        except asyncio.TimeoutError as te:
            raise RequestError(f"Timed out making request [{full_url}]") from te
        except ClientError as ce:
            raise RequestError(f"Request failed with unexpected error [{full_url}]: {ce}") from ce
        finally:
            if not use_running_session:
                await session.close()    
        
