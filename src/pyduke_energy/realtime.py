"""Client for connecting to Duke Energy realtime stream."""

import asyncio
import json
import logging
import ssl
import time
from typing import Optional

import paho.mqtt.client as mqtt

from pyduke_energy.client import DukeEnergyClient
from pyduke_energy.const import (
    FASTPOLL_RETRY,
    FASTPOLL_RETRY_COUNT,
    FASTPOLL_TIMEOUT,
    MQTT_ENDPOINT,
    MQTT_HOST,
    MQTT_KEEPALIVE,
    MQTT_PORT,
)
from pyduke_energy.errors import RequestError
from pyduke_energy.types import RealtimeUsageMeasurement

_LOGGER = logging.getLogger(__name__)


class DukeEnergyRealtime:
    """Duke Energy Realtime Client."""

    def __init__(self, duke_energy: DukeEnergyClient):
        self.duke_energy = duke_energy
        self.loop = asyncio.get_event_loop()
        self.disconnected = None
        self.disconnecting = False
        self.rx_msg = None
        self.mqtt_client = None
        self.topicid = None
        self.tstart = -FASTPOLL_TIMEOUT  # ensure fastpoll is requested on first run
        self.retrycount = 0
        self.mqtt_auth = None
        self.headers = None

    def on_conn(self, client: mqtt.Client, _userdata, _flags, conn_res):
        """On Connect callback.

        Parameters
        ----------
        client : mqtt.Client
            The paho-mqtt client
        userdata
            user data passed by the client
        flags
            Response flags sent by server
        conn_res : connack_code
            connection result code

        This will call the client.subscribe() method if the connection was successful.
        """
        if conn_res:
            _LOGGER.error(
                "MQTT connection error with result code: %s",
                mqtt.connack_string(conn_res),
            )
        else:
            _LOGGER.debug(
                "MQTT connected with result code: %s", mqtt.connack_string(conn_res)
            )
            res = client.subscribe(self.topicid, qos=0)
            if not res:
                _LOGGER.warning("Subscribe error: %s", mqtt.error_string(res))

    @staticmethod
    def on_sub(_client: mqtt.Client, _userdata, mid, granted_qos):
        """On Subscribe callback.

        Parameters
        ----------
        client : mqtt.Client
            The paho-mqtt client
        userdata
            user data passed by the client
        mid : int
            message id#
        granted_qos : literal[0, 1, 2]
            qos level granted by the server
        """
        _LOGGER.info("MQTT subscribed msg_id: %s qos: %s", str(mid), str(granted_qos))

    def on_unsub(self, client: mqtt.Client, _userdata, mid):
        """On Unubscribe callback.

        Parameters
        ----------
        client : mqtt.Client
            The paho-mqtt client
        userdata
            user data passed by the client
        mid : int
            message id#

        This will call the client.disconnect() method
        """
        _LOGGER.debug("MQTT unsubscribed msg_id: %s", str(mid))
        self.disconnecting = True
        client.disconnect()

    def on_discon(self, _client: mqtt.Client, _userdata, conn_res):
        """On Disconnect callback.

        Parameters
        ----------
        client : mqtt.Client
            The paho-mqtt client
        userdata
            user data passed by the client
        conn_res
            Disconnect error code
        """
        if conn_res:
            _LOGGER.error(
                "MQTT disconnect error, result code: %s (This may not be accurate)",
                mqtt.error_string(conn_res),
            )
        else:
            _LOGGER.info(
                "MQTT disconnected with result code: %s",
                mqtt.error_string(conn_res),
            )
        if self.disconnecting:
            self.disconnected.set_result(conn_res)
        else:
            self.mqtt_client.reconnect()

    @staticmethod
    def on_msg(msg):
        """On Message Callback.

        Parameters
        ----------
        msg : MQTTMessage
            This is a class with members topic, payload, qos, retain
        """
        _LOGGER.debug("rx msg on %s\n%s", msg.topic, msg.payload.decode("utf8"))

    def _on_msg(self, _client: mqtt.Client, _userdata, msg):
        """Private On Message callback.

        Parameters
        ----------
        client : mqtt.Client
            The paho-mqtt client
        userdata
            user data passed by the client
        msg : MQTTMessage
            This is a class with members topic, payload, qos, retain
        """
        if not self.rx_msg:
            _LOGGER.warning("Unexpected message: %s", msg)
        else:
            self.rx_msg.set_result((msg.payload.decode("utf8")))
            self.on_msg(msg)

    @staticmethod
    def msg_to_usage_measurement(msg) -> Optional[RealtimeUsageMeasurement]:
        """Parse a raw message to the realtime usage measurement type."""
        raw_json = msg.payload.decode("utf8")
        try:
            data = json.loads(raw_json)
            measurement = RealtimeUsageMeasurement(data)
            return measurement
        except (ValueError, TypeError):
            return None

    async def select_default_meter(self):
        """Call select_default_meter method of duke_energy client."""
        await self.duke_energy.select_default_meter()

    async def connect_and_subscribe(self):
        """Mqtt client connection."""
        self.disconnected = self.loop.create_future()
        self.rx_msg = None

        self.mqtt_auth, self.headers = await self.duke_energy.get_mqtt_auth()
        self.topicid = f'DESH/{self.mqtt_auth["gateway"]}/out/sm/1/live'

        self.mqtt_client = mqtt.Client(
            self.mqtt_auth["clientid"], transport="websockets"
        )
        self.mqtt_client.on_connect = self.on_conn
        self.mqtt_client.on_subscribe = self.on_sub
        self.mqtt_client.on_unsubscribe = self.on_unsub
        self.mqtt_client.on_disconnect = self.on_discon
        self.mqtt_client.on_message = self._on_msg
        self.mqtt_client.enable_logger(logger=_LOGGER)
        self.mqtt_client.ws_set_options(path=MQTT_ENDPOINT, headers=self.headers)
        self.mqtt_client.username_pw_set(
            self.mqtt_auth["user"], password=self.mqtt_auth["pass"]
        )
        self.mqtt_client.reconnect_delay_set(3, 60)
        # create default ssl context to get SSLKEYLOGFILE env variable
        self.mqtt_client.tls_set_context(ssl.create_default_context())

        mqtt_conn = MqttConnHelper(self.loop, self.mqtt_client)
        self.mqtt_client.connect(MQTT_HOST, port=MQTT_PORT, keepalive=MQTT_KEEPALIVE)
        try:
            while not mqtt_conn.misc.cancelled():
                if time.perf_counter() - self.tstart > FASTPOLL_TIMEOUT:
                    # Request fastpoll
                    await self._fastpoll_req()
                self.rx_msg = self.loop.create_future()
                try:
                    await asyncio.wait_for(self.rx_msg, FASTPOLL_RETRY)
                    self.retrycount = 0
                except asyncio.TimeoutError:
                    self.retrycount += 1
                    if self.retrycount <= FASTPOLL_RETRY_COUNT:
                        _LOGGER.info("Message timeout, requesting fastpoll")
                        await self._fastpoll_req()
                    else:
                        _LOGGER.info("Multiple msg timeout, attempting reconnect")
                        await self._reconnect()
                self.rx_msg = None
        finally:
            res = self.mqtt_client.unsubscribe(self.topicid)
            if not res:
                _LOGGER.warning("Unsubscribe error: %s", mqtt.error_string(res))
            await self.disconnected

    async def _fastpoll_req(self):
        """Request fastpoll, with auth check."""
        try:
            (
                mqtt_auth_new,
                headers_new,
            ) = await self.duke_energy.get_mqtt_auth()
        except RequestError:
            _LOGGER.warning(
                "Error requesting smartmeter auth, will retry after 5 seconds."
            )
            # Attempt clearing auth and try again.
            self.duke_energy._gateway_auth_info.clear_access_token()  # pylint: disable=W0212
            time.sleep(5)
            (
                mqtt_auth_new,
                headers_new,
            ) = await self.duke_energy.get_mqtt_auth()
        if mqtt_auth_new != self.mqtt_auth or headers_new != self.headers:
            _LOGGER.info("mqtt auth or headers updated, reconnecting...")
            self.mqtt_auth = mqtt_auth_new
            self.headers = headers_new
            await self._reconnect()
        self.tstart = await self.duke_energy.start_smartmeter_fastpoll()

    async def _reconnect(self):
        """Reconnect in case of updated auth or headers."""
        # Unsub and disconnect first
        res = self.mqtt_client.unsubscribe(self.topicid)
        if not res:
            _LOGGER.warning("Unsubscribe error: %s", mqtt.error_string(res))
        await self.disconnected
        self.disconnected = self.loop.create_future()  # re-create the future

        # Update mqtt_auth and header info
        clientid = self.mqtt_auth["clientid"]
        if isinstance(clientid, str):
            clientid = clientid.encode("utf-8")
        self.mqtt_client._client_id = clientid  # pylint: disable=W0212
        self.mqtt_client.ws_set_options(path=MQTT_ENDPOINT, headers=self.headers)
        self.mqtt_client.username_pw_set(
            self.mqtt_auth["user"], password=self.mqtt_auth["pass"]
        )
        self.mqtt_client.connect(MQTT_HOST, port=MQTT_PORT, keepalive=MQTT_KEEPALIVE)


class MqttConnHelper:
    """Helper for asyncio mqtt."""

    def __init__(self, loop: asyncio.AbstractEventLoop, mqtt_client: mqtt.Client):
        self.loop = loop
        self.mqtt_client = mqtt_client
        self.mqtt_client.on_socket_open = self.on_socket_open
        self.mqtt_client.on_socket_close = self.on_socket_close
        self.mqtt_client.on_socket_register_write = self.on_socket_register_write
        self.mqtt_client.on_socket_unregister_write = self.on_socket_unregister_write
        self.misc = None

    def on_socket_open(self, client: mqtt.Client, _userdata, sock):
        """Socket open callback."""
        _LOGGER.debug("Socket opened")

        def call_bk():
            """Socket reader callback."""
            _LOGGER.debug("Socket readable, calling loop_read()")
            client.loop_read()

        self.loop.add_reader(sock, call_bk)
        self.misc = self.loop.create_task(self.misc_loop())

    def on_socket_close(self, _client: mqtt.Client, _userdata, sock):
        """Socket close callback."""
        _LOGGER.debug("Socket closed")
        self.loop.remove_reader(sock)
        self.misc.cancel()

    def on_socket_register_write(self, client: mqtt.Client, _userdata, sock):
        """Socket write reg callback."""
        _LOGGER.debug("Watching socket for writability.")

        def call_bk():
            """Socket write callback."""
            _LOGGER.debug("Socket is writable, calling loop_write")
            client.loop_write()

        self.loop.add_writer(sock, call_bk)

    def on_socket_unregister_write(self, _client: mqtt.Client, _userdata, sock):
        """Socket unreg write callback."""
        _LOGGER.debug("Stop watching socket for writability.")
        self.loop.remove_writer(sock)

    async def misc_loop(self):
        """Misc loop call."""
        _LOGGER.debug("Misc loop started")

        while self.mqtt_client.loop_misc() == mqtt.MQTT_ERR_SUCCESS:
            try:
                await asyncio.sleep(1)
            except asyncio.CancelledError:
                _LOGGER.debug("Misc loop cancelled")
                break

        _LOGGER.debug("Misc loop finished")
