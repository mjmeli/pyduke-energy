"""Type Defintions."""

from dataclasses import dataclass
from datetime import date, datetime

from pyduke_energy.utils import str_to_date, str_to_datetime, utc_timestamp_to_datetime


@dataclass
class Account:
    """An account as provided by account-list endpoint."""

    def __init__(self, data: dict):
        self.default_account: bool = data.get("defaultAccount")
        self.nickname: str = data.get("nickname")
        self.account_number: str = data.get("accountNumber")
        self.src_acct_id: str = data.get("srcAcctId")
        self.src_acct_id_2: str = data.get("srcAcctId2")
        self.src_sys_cd: str = data.get("srcSysCd")
        self.bp_number: str = data.get("primaryBpNumber")
        self.status: str = data.get("status")
        self.role: str = data.get("role")
        self.service_address: str = data.get("serviceAddress")
        self.mobile_app_compatible: bool = data.get("mobileAppCompatible")


@dataclass
class AccountDetails:
    """Details account data as provided by account-details endpoint."""

    def __init__(self, data: dict):
        self.customer_name: str = data.get("customerName")
        self.first_name: str = data.get("firstName")
        self.last_name: str = data.get("lastName")
        self.mailing_address: MailingAddress = MailingAddress(
            data.get("mailingAddress")
        )
        self.service_address: ServiceAddress = ServiceAddress(
            data.get("serviceAddress")
        )
        self.is_electric: bool = data.get("isElectric")
        self.is_gas: bool = data.get("isGas")
        self.meter_infos: "list[MeterInfo]" = [
            MeterInfo(mi) for mi in data.get("meterInfo")
        ]


@dataclass
class BaseAddress:
    """Base address data."""

    def __init__(self, data: dict):
        self.address_line_1: str = data.get("addressLine1")
        self.address_line_2: str = data.get("addressLine2")
        self.city: str = data.get("city")
        self.state: str = data.get("stateCode")
        self.zip_code: str = data.get("zipCode")


@dataclass
class MailingAddress(BaseAddress):
    """Mailing address data as provided by account-details endpoint."""

    def __init__(self, data: dict):
        super().__init__(data)
        self.address_number: str = data.get("addressNumber")


@dataclass
class ServiceAddress(BaseAddress):
    """Service address data as provided by account-details endpoint."""

    def __init__(self, data: dict):
        super().__init__(data)
        self.premise_id: str = data.get("premiseID")


@dataclass
class MeterInfo:
    """Meter data as provided by account-details endpoint."""

    def __init__(self, data: dict):
        self.meter_type: str = data.get("meterType")
        self.serial_num: str = data.get("serialNum")
        self.agreement_active_date: date = str_to_date(
            data.get("agreementActiveDate")
        )  # this is specifically a date with no time component
        self.is_certified_smart_meter: bool = data.get("isCertifiedSmartMeter")
        self.op_center: str = data.get("opCenter")
        self.service_id: str = data.get("serviceId")
        self.transformer_number: str = data.get("transformerNumber")


@dataclass
class GatewayStatus:
    """Gateway status data as provided by gateways/status endpoint."""

    def __init__(self, data: dict):
        self.id: str = data.get("_id")
        self.service_state: str = data.get("serviceState")
        self.service_date: datetime = str_to_datetime(data.get("serviceDt"))
        self.connected: bool = data.get("connected")
        self.connect_date: datetime = str_to_datetime(data.get("connectTm"))
        self.mac_address: str = data.get("gwMAC")
        self.zigbee_mac_address: str = data.get("zgbMAC")


@dataclass
class UsageMeasurement:
    """Usage reading from the usageByHour endpoint."""

    def __init__(self, data: dict):
        self.timestamp: int = int(data.get("t") / 1000)  # remove ms
        self.datetime_utc: datetime = utc_timestamp_to_datetime(self.timestamp)
        self.usage: float = data.get("dr")  # dr is energy in Wh
        self.power: float = data.get("i")  # i is average power over the interval in W


@dataclass
class RealtimeUsageMeasurement:
    """Usage reading from the real-time data stream."""

    def __init__(self, data: dict):
        self.gateway_id: str = data.get("gw")
        self.timestamp: int = int(data.get("t") / 1000)  # remove ms
        self.datetime_utc: datetime = utc_timestamp_to_datetime(self.timestamp)
        self.usage: float = data.get("da").get("i")  # in watts
