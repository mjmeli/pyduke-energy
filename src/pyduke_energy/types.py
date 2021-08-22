"""Type Defintions"""

"""An account as provided by account-list endpoint"""
from pyduke_energy.utils import (
    str_to_datetime,
    str_to_date,
    utc_timestamp_to_datetime
)

class Account:
    def __init__(self, data: dict):
        self.default_account = data.get("defaultAccount")
        self.nickname = data.get("nickname")
        self.account_number = data.get("accountNumber")
        self.src_acct_id = data.get("srcAcctId")
        self.src_sys_cd = data.get("srcSysCd")
        self.status = data.get("status")
        self.role = data.get("role")
        self.service_address = data.get("serviceAddress")
        self.mobile_app_compatible = data.get("mobileAppCompatible")

"""Details account data as provided by account-details endpoint"""
class AccountDetails:
    def __init__(self, data: dict):
        self.customer_name = data.get("customerName")
        self.first_name = data.get("firstName")
        self.last_name = data.get("lastName")
        self.mailing_address = MailingAddress(data.get("mailingAddress"))
        self.service_address = ServiceAddress(data.get("serviceAddress"))
        self.is_electric = data.get("isElectric")
        self.is_gas = data.get("isGas")
        self.meter_infos = [MeterInfo(mi) for mi in data.get("meterInfo")]

"""Base address data"""
class BaseAddress:
    def __init__(self, data: dict):
        self.address_line_1 = data.get("addressLine1")
        self.address_line_2 = data.get("addressLine2")
        self.city = data.get("city")
        self.state = data.get("stateCode")
        self.zip_code = data.get("zipCode")

"""Mailing address data as provided by account-details endpoint"""
class MailingAddress(BaseAddress):
    def __init__(self, data: dict):
        self.address_number = data.get("addressNumber")
        super().__init__(data)

"""Service address data as provided by account-details endpoint"""
class ServiceAddress(BaseAddress):
    def __init__(self, data: dict):
        self.premise_id = data.get("premiseID")
        super().__init__(data)

"""Meter data as provided by account-details endpoint"""
class MeterInfo:
    def __init__(self, data: dict):
        self.meter_type = data.get("meterType")
        self.serial_num = data.get("serialNum")
        self.agreement_active_date = str_to_date(data.get("agreementActiveDate")) # this is specifically a date with no time component
        self.is_certified_smart_meter = data.get("isCertifiedSmartMeter")
        self.op_center = data.get("opCenter")
        self.service_id = data.get("serviceId")
        self.transformer_number = data.get("transformerNumber")

"""Gateway status data as provided by gateways/status endpoint"""
class GatewayStatus:
    def __init__(self, data: dict):
        self.id = data.get("_id")
        self.service_state = data.get("serviceState")
        self.service_date = str_to_datetime(data.get("serviceDt"))
        self.connected = data.get("connected")
        self.connect_date = str_to_datetime(data.get("connectTm"))
        self.mac_address = data.get("gwMAC")
        self.zigbee_mac_address = data.get("zgbMAC")

"""Usage reading from the usageByHour endpoint"""
class UsageMeasurement:
    def __init__(self, data: dict):
        self.timestamp = data.get("t")
        self.datetime_utc = utc_timestamp_to_datetime(data.get("t") / 1000)
        self.usage = data.get("i") # i works for now