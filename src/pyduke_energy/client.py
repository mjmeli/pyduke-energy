"""Client for interacting with the Duke Energy API."""

import asyncio
from datetime import date, datetime, timedelta, timezone
import logging
from typing import List, Optional
from urllib.parse import urljoin

from aiohttp import ClientSession, ClientTimeout, FormData
from aiohttp.client_exceptions import ClientError

from pyduke_energy.const import (
    CUST_API_BASE_URL,
    CUST_PILOT_API_BASE_URL,
    DEFAULT_TIMEOUT,
    IOT_API_BASE_URL,
)
from pyduke_energy.errors import InputError, RequestError
from pyduke_energy.types import (
    Account,
    AccountDetails,
    GatewayStatus,
    MeterInfo,
    UsageMeasurement,
)
from pyduke_energy.utils import date_to_utc_timestamp

_LOGGER = logging.getLogger(__name__)


class _BaseAuthInfo:
    def __init__(self):
        self.access_token: Optional[str] = None
        self.expires: Optional[datetime] = None

    def needs_new_access_token(self):
        """Check if a new access token is needed."""
        return (
            self.access_token is None
            or self.expires is None
            or datetime.now() > self.expires
        )

    def set_new_access_token(self, access_token, expires):
        """Set the new access token and expiration date."""
        self.access_token = access_token
        self.expires = datetime.now() + timedelta(seconds=int(expires))

    def clear_access_token(self):
        """Clear an existing access token."""
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
        self.mqtt_username: Optional[str] = None
        self.mqtt_password: Optional[str] = None
        self.mqtt_clientid: Optional[str] = None
        self.mqtt_clientid_error: Optional[str] = None
        self.gateway: Optional[str] = None


class DukeEnergyClient:
    """The Duke Energy API client."""

    def __init__(
        self, email: str, password: str, session: Optional[ClientSession] = None
    ):
        self._email = email
        self._password = password
        self._session = session

        # Authentication
        self._oauth_auth_info = _OAuthAuthInfo()
        self._gateway_auth_info = _GatewayAuthInfo()

    async def get_account_list(self) -> List[Account]:
        """Get the list of accounts. Data is high-level summary data."""
        endpoint = "auth/account-list"
        headers = await self._get_oauth_headers()
        params = {
            "email": self._email,
            "internalUserID": self._oauth_auth_info.internal_user_id,
        }
        resp = await self._async_request(
            "GET", CUST_API_BASE_URL, endpoint, headers=headers, params=params
        )
        account_list: List[dict] = resp.get("accounts")
        return [Account(acc) for acc in account_list]

    async def get_account_details(self, account: Account) -> AccountDetails:
        """Get detailed account data for a specific account."""
        return await self._get_account_details(
            account.src_sys_cd,
            account.src_acct_id,
            account.src_acct_id_2,
            account.bp_number,
        )

    async def _get_account_details(
        self,
        src_sys_cd: str,
        src_acct_id: str,
        src_acct_id_2: Optional[str],
        bp_number: Optional[str],
    ) -> AccountDetails:
        endpoint = "auth/account-details"
        headers = await self._get_oauth_headers()
        params = {
            "email": self._email,
            "srcSysCd": src_sys_cd,
            "srcAcctId": src_acct_id,
        }
        if src_acct_id_2:
            params["srcAcctId2"] = src_acct_id_2
        if bp_number:
            params["bpNumber"] = bp_number
        resp = await self._async_request(
            "GET", CUST_API_BASE_URL, endpoint, headers=headers, params=params
        )
        return AccountDetails(resp)

    def select_meter(self, meter: MeterInfo) -> None:
        """Select which meter will be used for gateway API calls."""
        self.select_meter_by_id(meter.serial_num, meter.agreement_active_date)

    def select_meter_by_id(self, meter_id: str, activation_date: date) -> None:
        """Select which meter will be used for gateway API calls."""
        self._gateway_auth_info.meter_id = meter_id
        self._gateway_auth_info.activation_date = activation_date
        self._gateway_auth_info.clear_access_token()  # resets

    async def get_gateway_status(self) -> GatewayStatus:
        """Get the status of the selected gateway."""
        endpoint = "gw/gateways/status"
        headers = await self._get_gateway_auth_headers()
        resp = await self._async_request(
            "GET", IOT_API_BASE_URL, endpoint, headers=headers
        )
        return GatewayStatus(resp)

    async def get_gateway_usage(
        self, range_start: datetime, range_end: datetime
    ) -> "list[UsageMeasurement]":
        """Get gateway usage for a time window."""
        if range_start > range_end:
            raise InputError("Start date must be before end date")

        endpoint = "smartmeter/usageByHour"
        headers = await self._get_gateway_auth_headers()

        dt_format = (
            "%Y-%m-%dT%H:%M"  # the API actually ignores minutes, seconds, timezone
        )
        start_hour = range_start.astimezone(timezone.utc).strftime(
            dt_format
        )  # API expects dates to be UTC
        end_hour = range_end.astimezone(timezone.utc).strftime(dt_format)
        params = {"startHourDt": start_hour, "endHourDt": end_hour}
        _LOGGER.debug(
            "Requesting usage between %s UTC and %s UTC", start_hour, end_hour
        )

        resp = await self._async_request(
            "GET", IOT_API_BASE_URL, endpoint, headers=headers, params=params
        )

        # Format is a list of objects containing the measurements, one object per hour. Here we combine all.
        raw_measurements = [mn for d in resp for mn in d.get("mn")]
        measurements = [UsageMeasurement(mn) for mn in raw_measurements]
        measurements.sort(key=lambda x: x.timestamp)
        return measurements

    async def get_mqtt_auth(self):
        """Request mqtt authentication.

        Returns
        -------
        mqtt_auth : dict
            dictionary of mqtt authentication info
        headers : dict
            dictionary of smartmeter authentication info
        """
        try:
            headers = await self._get_gateway_auth_headers()
        except InputError:
            # Assume 1st meter in 1st account # if missing
            _LOGGER.info("No meter specified, assuming fist meter of first accnt")
            accounts = await self.get_account_list()
            meters = await self.get_account_details(accounts[0])
            self.select_meter(meters.meter_infos[0])
            headers = await self._get_gateway_auth_headers()
        mqtt_auth = await self._get_mqtt_auth()
        return mqtt_auth, headers

    async def start_smartmeter_fastpoll(self):
        """Send request to start fastpolling."""
        endpoint = "smartmeter/fastpoll/start"
        headers = await self._get_gateway_auth_headers()
        await self._async_request("GET", IOT_API_BASE_URL, endpoint, headers=headers)
        _LOGGER.debug("Smartmeter fastpoll requested")

    async def _oauth_login(self) -> None:
        """Hit the OAuth login endpoint to generate a new access token."""
        _LOGGER.debug("Getting new OAuth auth")

        endpoint = "auth/oauth2/token"
        headers = {
            "Authorization": "Basic UzdmNXFQR2MwcnpVZkJmcVNPak9ycGczZWtSZ3ZHSng6bW1nS2pyY1RQRHptOERtVw=="
        }  # hard-coded from Android app
        request = {
            "grant_type": "password",
            "username": self._email,
            "password": self._password,
        }
        resp = await self._async_request(
            "POST", CUST_API_BASE_URL, endpoint, headers=headers, data=FormData(request)
        )
        self._oauth_auth_info.set_new_access_token(
            resp.get("access_token"), resp.get("expires_in")
        )
        self._oauth_auth_info.internal_user_id = resp.get("cdp_internal_user_id")

    async def _get_oauth_headers(self) -> dict:
        """Get the auth headers for OAuth scoped actions and logs in if new access token is needed."""
        # Get a new access token if it has expired
        if self._oauth_auth_info.needs_new_access_token():
            await self._oauth_login()
        return {"Authorization": f"Bearer {self._oauth_auth_info.access_token}"}

    async def _gateway_login(self) -> None:
        if self._gateway_auth_info.meter_id is None:
            raise InputError(
                "Gateway needs to be selected before calling gateway functions"
            )

        _LOGGER.debug("Getting new gateway auth")

        endpoint = "smartmeter/v1/auth"
        headers = await self._get_oauth_headers()
        request = {
            "meterId": self._gateway_auth_info.meter_id,
            "activationDt": int(
                date_to_utc_timestamp(self._gateway_auth_info.activation_date)
            )
            * 1000,  # ms timestamp
        }
        resp = await self._async_request(
            "POST",
            CUST_PILOT_API_BASE_URL,
            endpoint,
            headers=headers,
            data=FormData(request),
        )
        self._gateway_auth_info.set_new_access_token(
            resp.get("access_token"), resp.get("expires_in")
        )
        self._gateway_auth_info.id_token = resp.get("id_token")
        self._gateway_auth_info.mqtt_username = resp.get("mqtt_username")
        self._gateway_auth_info.mqtt_password = resp.get("mqtt_password")
        self._gateway_auth_info.mqtt_clientid = resp.get("mqtt_clientId")
        self._gateway_auth_info.mqtt_clientid_error = resp.get("mqtt_clientId_error")
        self._gateway_auth_info.gateway = resp.get("gateway")

    async def _get_gateway_auth_headers(self) -> dict:
        """Get the auth headers for gateway scoped actions and logs in if new access token is needed."""
        # Get a new access token if it has expired
        if self._gateway_auth_info.needs_new_access_token():
            await self._gateway_login()
        return {
            "Authorization": f"Bearer {self._gateway_auth_info.access_token}",
            "de-iot-id-token": self._gateway_auth_info.id_token,
        }

    async def _get_mqtt_auth(self) -> dict:
        """Get the auth headers for mqtt actions and logs in if new access token is needed."""
        # Get a new access token if it has expired
        if self._gateway_auth_info.needs_new_access_token():
            await self._gateway_login()
        return {
            "clientid": self._gateway_auth_info.mqtt_clientid,
            "user": self._gateway_auth_info.mqtt_username,
            "pass": self._gateway_auth_info.mqtt_password,
            "gateway": self._gateway_auth_info.gateway,
        }

    async def _async_request(
        self,
        method: str,
        base_url: str,
        endpoint: str,
        headers: Optional[dict] = None,
        params: Optional[dict] = None,
        data: Optional[dict] = None,
        json: Optional[dict] = None,
    ) -> dict:
        """Make a request against the Duke Energy API."""
        use_running_session = self._session and not self._session.closed

        if use_running_session:
            session = self._session
        else:
            session = ClientSession(timeout=ClientTimeout(total=DEFAULT_TIMEOUT))

        full_url = urljoin(base_url, endpoint)

        try:
            async with session.request(
                method, full_url, headers=headers, params=params, data=data, json=json
            ) as resp:
                resp.raise_for_status()
                data = await resp.json(
                    content_type=None
                )  # not all of their APIs return the correct content_Type
                return data
        except asyncio.TimeoutError as timeout_err:
            raise RequestError(
                f"Timed out making request [{full_url}]"
            ) from timeout_err
        except ClientError as client_err:
            raise RequestError(
                f"Request failed with unexpected error [{full_url}]: {client_err}"
            ) from client_err
        finally:
            if not use_running_session:
                await session.close()
