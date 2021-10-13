"""Constant Defintions."""

CUST_API_BASE_URL = "https://cust-api.duke-energy.com/gep/v2/"
CUST_PILOT_API_BASE_URL = "https://cust-pilot-api.duke-energy.com/"
IOT_API_BASE_URL = "https://app-core1.de-iot.io/rest/cloud/"
FASTPOLL_ENDPOINT = "smartmeter/fastpoll/start"
OAUTH_ENDPOINT = "auth/oauth2/token"
BASIC_AUTH = "Basic UzdmNXFQR2MwcnpVZkJmcVNPak9ycGczZWtSZ3ZHSng6bW1nS2pyY1RQRHptOERtVw=="  # hard-coded from Android app
SMARTMETER_AUTH_ENDPOINT = "smartmeter/v1/auth"
ACCT_ENDPOINT = "auth/account-list"
ACCT_DET_ENDPOINT = "auth/account-details"
GW_STATUS_ENDPOINT = "gw/gateways/status"
GW_USAGE_ENDPOINT = "smartmeter/usageByHour"

MQTT_HOST = "app-core1.de-iot.io"
MQTT_PORT = 443
MQTT_ENDPOINT = "/app-mqtt"
MQTT_KEEPALIVE = 50  # Seconds, it appears the server will disconnect after 60s idle
FASTPOLL_TIMEOUT = 900 - 3  # seconds
FASTPOLL_RETRY = 60  # if no messages after this time, retry fastpoll request
FASTPOLL_RETRY_COUNT = 3

DEFAULT_TIMEOUT = 10  # seconds
