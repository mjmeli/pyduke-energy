"""Example of realtime power measurement."""

# pylint: skip-file

import time
import asyncio
import getpass
import os
import logging

import aiohttp
import sys
from kafka import KafkaProducer
from kafka.errors import KafkaTimeoutError

from pyduke_energy.client import DukeEnergyClient
from pyduke_energy.const import FASTPOLL_TIMEOUT_SEC
from pyduke_energy.errors import DukeEnergyError
from pyduke_energy.realtime import DukeEnergyRealtime

PYDUKEENERGY_TEST_EMAIL = "PYDUKEENERGY_TEST_EMAIL"
PYDUKEENERGY_TEST_PASS = "PYDUKEENERGY_TEST_PASS"

_LOGGER = logging.getLogger(__name__)


class MyDukeRT(DukeEnergyRealtime):
    """My instance of DukeEnergyRealtime."""

    def connect_kafka(self, kfktopic: str, bootstrap_servers: str = "[::1]:9092"):
        """Open connection to Kafka."""
        self.kfk = KafkaProducer(bootstrap_servers=bootstrap_servers)
        self.kfktopic = kfktopic
        _LOGGER.debug("Connected to Kafka")

    def close_kafka(self):
        """Close connection to Kafka."""
        if self.kfk is not None:
            self.kfk.close()
            _LOGGER.debug("Disconnected from Kafka")

    def on_message(self, msg):
        """On Message callback.

        Parameters
        ----------
        msg : MQTTMessage
            This is a class with members topic, payload, qos, retain
        """
        tic = time.perf_counter()
        try:
            self.kfk.send(self.kfktopic, value=msg.payload)
            toc = time.perf_counter() - tic
            _LOGGER.debug("logged msg to kafka in %f seconds", toc)
        except KafkaTimeoutError as e:
            _LOGGER.warning("Kafka Error: %s", e)


async def main() -> None:
    """Duke Energy Realtime data demo."""
    logging.basicConfig(
        format="%(asctime)s.%(msecs)03d %(levelname)s {%(module)s} [%(funcName)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        level=logging.INFO,
    )

    logging.getLogger("kafka").setLevel(logging.WARNING)

    # Pull email/password into environment variables
    email = os.environ.get(PYDUKEENERGY_TEST_EMAIL)
    password = os.environ.get(PYDUKEENERGY_TEST_PASS)

    if email is None or password is None:
        print(
            "Enter your email and password in environment variables. To avoid typing them in, you can put them into environment variables {PYDUKEENERGY_TEST_EMAIL} and {PYDUKEENERGY_TEST_PASS}."
        )
        email = input("Email: ")
        password = getpass.getpass("Password: ")

    while True:
        try:
            async with aiohttp.ClientSession() as client:
                duke_energy = DukeEnergyClient(email, password, client)

                duke_rt = MyDukeRT(duke_energy)
                duke_rt.connect_kafka("smartmeter")
                await duke_rt.select_default_meter()
                await duke_rt.connect_and_subscribe_forever()
        except DukeEnergyError as err:
            # attempt sleep and retry
            _LOGGER.warning("Error: %s\nAttempt sleep and retry.", err)
            await duke_rt.mqtt_client.unsubscribe()
            duke_rt.close_kafka()

            time.sleep(FASTPOLL_TIMEOUT_SEC)
        finally:
            duke_rt.close_kafka()


if __name__ == "__main__":
    # ensure selector event loop is started in windows
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    try:
        asyncio.run(main(), debug=False)
    except KeyboardInterrupt:
        _LOGGER.debug("keyboard interrupt")
