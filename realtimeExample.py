"""Example of realtime power measurement."""

# pylint: skip-file

import asyncio
import getpass
import json
import os
import logging

import aiohttp
import sys

from pyduke_energy.client import DukeEnergyClient
from pyduke_energy.errors import DukeEnergyError
from pyduke_energy.realtime import DukeEnergyRealtime

PYDUKEENERGY_TEST_EMAIL = "PYDUKEENERGY_TEST_EMAIL"
PYDUKEENERGY_TEST_PASS = "PYDUKEENERGY_TEST_PASS"

_LOGGER = logging.getLogger(__name__)


class MyDukeRT(DukeEnergyRealtime):
    """My instance of DukeEnergyRealtime."""

    def on_msg(self, msg):
        """On Message callback.

        Parameters
        ----------
        msg : MQTTMessage
            This is a class with members topic, payload, qos, retain
        """
        try:
            tmp = json.loads(msg.payload.decode("utf8"))
            _LOGGER.debug("Recieved: %s", tmp)
        except (ValueError, TypeError):
            _LOGGER.warning("unexpected msg: %s", msg.payload.decode("utf8"))


async def main() -> None:
    """Duke Energy Realtime data demo."""
    logging.basicConfig(
        format="%(asctime)s.%(msecs)03d %(levelname)s {%(module)s} [%(funcName)s] %(message)s",
        datefmt="%Y-%m-%d,%H:%M:%S",
        level=logging.DEBUG,
    )

    # Pull email/password into environment variables
    email = os.environ.get(PYDUKEENERGY_TEST_EMAIL)
    password = os.environ.get(PYDUKEENERGY_TEST_PASS)

    if email is None or password is None:
        print(
            "Enter your email and password in environment variables. To avoid typing them in, you can put them into environment variables {PYDUKEENERGY_TEST_EMAIL} and {PYDUKEENERGY_TEST_PASS}."
        )
        email = input("Email: ")
        password = getpass.getpass("Password: ")
    try:
        async with aiohttp.ClientSession() as client:
            duke_energy = DukeEnergyClient(email, password, client)

            duke_rt = MyDukeRT(duke_energy)
            await duke_rt.select_default_meter()
            await duke_rt.connect_and_subscribe()
    except DukeEnergyError as err:
        print(err)


if __name__ == "__main__":
    # ensure selector event loop is started in windows
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    try:
        asyncio.run(main(), debug=True)
    except KeyboardInterrupt:
        _LOGGER.debug("keyboard interrupt")
