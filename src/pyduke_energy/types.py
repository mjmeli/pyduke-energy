"""Type Defintions"""

"""An account as provided by account-list endpoint"""
from datetime import datetime, date
from pyduke_energy.utils import (
    str_to_datetime,
    str_to_date,
    utc_timestamp_to_datetime
)

class Account:
    def __init__(self, data: dict):
        self.default_account: bool = data.get("defaultAccount")
        self.nickname: str = data.get("nickname")
        self.account_number: str = data.get("accountNumber")
        self.src_acct_id: str = data.get("srcAcctId")
        self.src_sys_cd: str = data.get("srcSysCd")
        self.status: str = data.get("status")
        self.role: str = data.get("role")
        self.service_address: str = data.get("serviceAddress")
        self.mobile_app_compatible: bool = data.get("mobileAppCompatible")

"""Details account data as provided by account-details endpoint"""
class AccountDetails:
    def __init__(self, data: dict):
        self.customer_name: str = data.get("customerName")
        self.first_name: str = data.get("firstName")
        self.last_name: str = data.get("lastName")
        self.mailing_address: MailingAddress = MailingAddress(data.get("mailingAddress"))
        self.service_address: ServiceAddress = ServiceAddress(data.get("serviceAddress"))
        self.is_electric: bool = data.get("isElectric")
        self.is_gas: bool = data.get("isGas")
        self.meter_infos: list[MeterInfo] = [MeterInfo(mi) for mi in data.get("meterInfo")]

"""Base address data"""
class BaseAddress:
    def __init__(self, data: dict):
        self.address_line_1: str = data.get("addressLine1")
        self.address_line_2: str = data.get("addressLine2")
        self.city: str = data.get("city")
        self.state: str = data.get("stateCode")
        self.zip_code: str = data.get("zipCode")

"""Mailing address data as provided by account-details endpoint"""
class MailingAddress(BaseAddress):
    def __init__(self, data: dict):
        super().__init__(data)
        self.address_number: str = data.get("addressNumber")

"""Service address data as provided by account-details endpoint"""
class ServiceAddress(BaseAddress):
    def __init__(self, data: dict):
        super().__init__(data)
        self.premise_id: str = data.get("premiseID")

"""Meter data as provided by account-details endpoint"""
class MeterInfo:
    def __init__(self, data: dict):
        self.meter_type: str = data.get("meterType")
        self.serial_num: str = data.get("serialNum")
        self.agreement_active_date: date = str_to_date(data.get("agreementActiveDate")) # this is specifically a date with no time component
        self.is_certified_smart_meter: bool = data.get("isCertifiedSmartMeter")
        self.op_center: str = data.get("opCenter")
        self.service_id: str = data.get("serviceId")
        self.transformer_number: str = data.get("transformerNumber")

"""Gateway status data as provided by gateways/status endpoint"""
class GatewayStatus:
    def __init__(self, data: dict):
        self.id: str = data.get("_id")
        self.service_state: str = data.get("serviceState")
        self.service_date: datetime = str_to_datetime(data.get("serviceDt"))
        self.connected: bool = data.get("connected")
        self.connect_date: datetime = str_to_datetime(data.get("connectTm"))
        self.mac_address: str = data.get("gwMAC")
        self.zigbee_mac_address: str = data.get("zgbMAC")

"""Usage reading from the usageByHour endpoint"""
class UsageMeasurement:
    def __init__(self, data: dict):
        self.timestamp: int = int(data.get("t") / 1000) # remove ms
        self.datetime_utc: datetime = utc_timestamp_to_datetime(self.timestamp)
        self.usage: float = data.get("i") # i works for now