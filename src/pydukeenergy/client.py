"""Client for interacting with the Duke Energy API"""

import asyncio
import logging
from datetime import datetime, timedelta, date, timezone
from typing import Optional
from urllib.parse import urljoin
from aiohttp import ClientSession, ClientTimeout, FormData
from aiohttp.client_exceptions import ClientError

from pydukeenergy.const import (
    CUST_API_BASE_URL,
    CUST_PILOT_API_BASE_URL,
    IOT_API_BASE_URL,
    DEFAULT_TIMEOUT
)
from pydukeenergy.types import (
    Account,
    AccountDetails,
    MeterInfo,
    GatewayStatus,
    UsageMeasurement
)
from pydukeenergy.utils import (
    date_to_utc_timestamp
)
from pydukeenergy.errors import (
    DukeEnergyError,
    RequestError,
    InputError
)

_LOGGER = logging.getLogger(__name__)

class _GatewayInfo:
    def __init__(self, meter_id: str, activation_date: date, access_token: str, id_token: str, expires: datetime):
        self.meter_id = meter_id
        self.activation_date = activation_date
        self.access_token = access_token
        self.id_token = id_token
        self.expires = expires

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
        self._oauth_access_token: Optional[str] = None
        self._oauth_expires = datetime.min
        self._internal_user_id: Optional[str] = None
        self._gateway_info: Optional[_GatewayInfo] = None

    async def get_account_list(self) -> 'list[Account]':
        endpoint = "auth/account-list"
        headers = await self._get_oauth_headers()
        params = {
            "email": self._email,
            "internalUserID": self._internal_user_id
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

    def select_meter(self, meter: MeterInfo) -> None:
        """Selects which meter wil be used for gateway API calls"""
        self.select_meter(meter.serial_num, meter.agreement_active_date)

    def select_meter(self, meter_id: str, activation_date: date) -> None:
        """Selects which meter wil be used for gateway API calls"""
        if (self._gateway_info is not None and self._gateway_info.meter_id == meter_id):
            # Don't update so we keep the same auth credentails
            return

        # Initialize with no credentials
        self._gateway_info = _GatewayInfo(meter_id, activation_date, None, None, datetime.min)

    async def get_gateway_status(self) -> GatewayStatus:
        endpoint = "gw/gateways/status"
        headers = await self._get_gateway_auth_headers()
        resp = await self._async_request("GET", IOT_API_BASE_URL, endpoint, headers=headers)
        return GatewayStatus(resp)

    async def get_gateway_usage(self, range_start: datetime, range_end: datetime) -> None:
        """Gets gateway usage for a time window."""

        if range_start > range_end:
            raise InputError("Start date must be before end date")

        endpoint = "smartmeter/usageByHour"
        headers = await self._get_gateway_auth_headers()
        dt_format = "%Y-%m-%dT%H:00" # the API ignores minutes, seconds, timezone
        params = {
            "startHourDt": range_start.astimezone(timezone.utc).strftime(dt_format),
            "endHourDt": range_end.astimezone(timezone.utc).strftime(dt_format)
        }
        resp = await self._async_request("GET", IOT_API_BASE_URL, endpoint, headers=headers, params=params)

        # Format is a list of objects containing the measurements, one object per hour. Here we combine all.
        raw_measurements = [mn for d in resp for mn in d.get("mn")]
        measurements = [UsageMeasurement(mn) for mn in raw_measurements]
        measurements.sort(key=lambda x: x.time)
        return measurements

    async def _oauth_login(self) -> None:
        endpoint = "auth/oauth2/token"
        headers = { "Authorization": "Basic UzdmNXFQR2MwcnpVZkJmcVNPak9ycGczZWtSZ3ZHSng6bW1nS2pyY1RQRHptOERtVw==" } # hard-coded from Android app
        request = {
            "grant_type": "password",
            "username": self._email,
            "password": self._password
        }
        resp = await self._async_request("POST", CUST_API_BASE_URL, endpoint, headers=headers, data=FormData(request))
        self._oauth_access_token = resp.get("access_token")
        self._oauth_expires = datetime.now() + timedelta(seconds=int(resp.get("expires_in")))
        self._internal_user_id = resp.get("cdp_internal_user_id")

    async def _get_oauth_headers(self) -> dict:
        """Need a new access token?"""
        if (not self._oauth_access_token or datetime.now() > self._oauth_expires):
            await self._oauth_login()
        return { 
            "Authorization": f"Bearer {self._oauth_access_token}"
        }

    async def _gateway_login(self) -> None:
        if self._gateway_info is None:
            raise InputError("Gateway needs to be selected before calling gateway functions")

        endpoint = "smartmeter/v1/auth"
        headers = await self._get_oauth_headers()
        request = {
            "meterId": self._gateway_info.meter_id,
            "activationDt": int(date_to_utc_timestamp(self._gateway_info.activation_date)) * 1000 # ms timestamp
        }
        print(request)
        resp = await self._async_request("POST", CUST_PILOT_API_BASE_URL, endpoint, headers=headers, data=FormData(request))
        self._gateway_info.access_token = resp.get("access_token")
        self._gateway_info.expires = datetime.now() + timedelta(seconds=int(resp.get("expires_in")))
        self._gateway_info.id_token = resp.get("id_token")

    async def _get_gateway_auth_headers(self) -> dict:
        """Need a new access token?"""
        if (not self._gateway_info.access_token or datetime.now() > self._gateway_info.expires):
            await self._gateway_login()
        return { 
            "Authorization": f"Bearer {self._gateway_info.access_token}",
            "de-iot-id-token": self._gateway_info.id_token
        }

    async def _async_request(self, method: str, base_url: str, endpoint: str,headers: Optional[dict] = None, params: Optional[dict] = None, data: Optional[dict] = None, json: Optional[dict] = None) -> dict:
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
        
