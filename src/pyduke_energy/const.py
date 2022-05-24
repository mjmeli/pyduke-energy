"""Constant Defintions."""

CUST_API_BASE_URL = "https://cust-api.duke-energy.com/gep/v2/"
CUST_PILOT_API_BASE_URL = "https://cust-pilot-api.duke-energy.com/"
IOT_API_BASE_URL = "https://app-core1.de-iot.io/rest/cloud/"
FASTPOLL_ENDPOINT = "smartmeter/fastpoll/start"
OAUTH_ENDPOINT = "auth/oauth2/token"
BASIC_AUTH = "Basic NEdtR3J1M085TEFIV3BMNjVjbWpyZDhtQ1VKZU5XTVo6OWFyZVZoZlM3R2N4UmgzWA=="  # hard-coded from Android app
SMARTMETER_AUTH_ENDPOINT = "smartmeter/v1/auth"
ACCT_ENDPOINT = "auth/account-list"
ACCT_DET_ENDPOINT = "auth/account-details"
GW_STATUS_ENDPOINT = "gw/gateways/status"
GW_USAGE_ENDPOINT = "smartmeter/usageByHour"

DEFAULT_TIMEOUT = 10  # seconds

MQTT_HOST = "app-core1.de-iot.io"
MQTT_PORT = 443
MQTT_ENDPOINT = "/app-mqtt"
MQTT_KEEPALIVE = 50  # Seconds, it appears the server will disconnect after 60s idle

# in seconds, how long to until the fastpoll request has timed out and a new one needs to be made
FASTPOLL_TIMEOUT_SEC = 900 - 3  # seconds

# in seconds, how long to wait for a message before retrying fastpoll or reconnecting
MESSAGE_TIMEOUT_SEC = 60

# number of times a message timeout can occur before just reconnecting
MESSAGE_TIMEOUT_RETRY_COUNT = 3

# in minutes, minimum amount of time to wait before retrying connection on forever loop
FOREVER_RETRY_MIN_MINUTES = 1

# in minutes, maximum amount of time to wait before trying connection on forever loop
FOREVER_RETRY_MAX_MINUTES = 60

# in seconds, how long to wait for a connection before timing out
CONNECT_TIMEOUT_SEC = 60
