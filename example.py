import os
import getpass
import asyncio
import aiohttp
import logging
import jsonpickle
from datetime import datetime, timedelta, timezone
import dateutil

from pyduke_energy import DukeEnergyClient, DukeEnergyError

_LOGGER = logging.getLogger(__name__)

PYDUKEENERGY_TEST_EMAIL = "PYDUKEENERGY_TEST_EMAIL"
PYDUKEENERGY_TEST_PASS = "PYDUKEENERGY_TEST_PASS"

tz_string = datetime.now(timezone.utc).astimezone().tzname()
tz = dateutil.tz.gettz(tz_string)

async def main() -> None:
    logging.basicConfig(level=logging.DEBUG)

    # Pull email/password into environment variables
    email = os.environ.get(PYDUKEENERGY_TEST_EMAIL)
    password = os.environ.get(PYDUKEENERGY_TEST_PASS)
    if (email is None or password is None):
        print(f"Enter your email and password in environment variables. To avoid typing them in, you can put them into environment variables {PYDUKEENERGY_TEST_EMAIL} and {PYDUKEENERGY_TEST_PASS}.")
        email = input("Email: ")
        password = getpass.getpass("Password: ")

    try:
        async with aiohttp.ClientSession() as client:
            duke_energy = DukeEnergyClient(email, password, client)

            _LOGGER.info("Getting account list:")
            account_list = await duke_energy.get_account_list()
            for acc in account_list:
                _LOGGER.info(jsonpickle.encode(acc, indent=2, unpicklable=False))

            account = account_list[0]
            
            _LOGGER.info("Getting account details:")
            account_details = await duke_energy.get_account_details(account)
            _LOGGER.info(jsonpickle.encode(account_details, indent=2, unpicklable=False))

            meter = account_details.meter_infos[0]

            _LOGGER.info(f"Selecting meter (not an API call) {meter.serial_num}")
            duke_energy.select_meter(meter)
            
            _LOGGER.info("Getting gateway status:")
            gw_status = await duke_energy.get_gateway_status()
            _LOGGER.info(jsonpickle.encode(gw_status, indent=2, unpicklable=False))

            _LOGGER.info("Getting gateway usage from top of last hour to now:")
            gw_usage = await duke_energy.get_gateway_usage(datetime.now() + timedelta(hours=-1), datetime.now() + timedelta(hours=1))
            _LOGGER.info(jsonpickle.encode(gw_usage, indent=2, unpicklable=False))

            _LOGGER.info("Getting gateway usage for today:")
            today = datetime.today()
            today_start = datetime(today.year, today.month, today.day)
            today_end = today_start + timedelta(days=1)
            gw_usage = await duke_energy.get_gateway_usage(today_start, today_end)
            today_usage = sum(x.usage for x in gw_usage)
            _LOGGER.info(f"Requesting between {today_start} and {today_end}")
            _LOGGER.info(f"From {gw_usage[0].datetime_utc.astimezone(tz)} to {gw_usage[-1].datetime_utc.astimezone(tz)}: {today_usage} ({len(gw_usage)} measurements)")

    except DukeEnergyError as err:
        _LOGGER.info(err)

asyncio.run(main())