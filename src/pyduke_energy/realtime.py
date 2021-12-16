"""Client for connecting to Duke Energy realtime stream."""

import asyncio
import functools
import json
import logging
import socket
import ssl
import time
from typing import Any, Dict, Optional

import paho.mqtt.client as mqtt

from pyduke_energy.client import DukeEnergyClient
from pyduke_energy.const import (
    CONNECT_TIMEOUT_SEC,
    FASTPOLL_TIMEOUT_SEC,
    FOREVER_RETRY_MAX_MINUTES,
    FOREVER_RETRY_MIN_MINUTES,
    MESSAGE_TIMEOUT_RETRY_COUNT,
    MESSAGE_TIMEOUT_SEC,
    MQTT_ENDPOINT,
    MQTT_HOST,
    MQTT_KEEPALIVE,
    MQTT_PORT,
)
from pyduke_energy.errors import MqttCodeError, MqttError, RequestError
from pyduke_energy.types import RealtimeUsageMeasurement

_LOGGER = logging.getLogger(__name__)


class DukeEnergyRealtime:
    """Duke Energy Realtime Client."""

    def __init__(self, duke_energy: DukeEnergyClient):
        self._duke_energy = duke_energy
        self._loop = asyncio.get_event_loop()
        self._disconnected: Optional["asyncio.Future[int]"] = None
        self._disconnecting: bool = False
        self._connected: Optional["asyncio.Future[int]"] = None
        self._rx_msg: Optional["asyncio.Future[int]"] = None
        self._t_start: int = 0
        self._msg_retry_count: int = 0
        self._forever_retry_count: int = 0
        self._mqtt_auth: dict = {}
        self._headers: dict = {}
        self._topic_id: str = None
        self._mqtt_client: Optional[mqtt.Client] = None

    def on_connect(
        self, client: mqtt.Client, _userdata: Any, _flags: Dict[str, int], conn_res: int
    ):
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
        # Return early if already connected. Sometimes this will be called multiple times.
        if not self._connected or self._connected.done():
            return

        if conn_res:
            _LOGGER.error(
                "MQTT connection error with result code: %s",
                mqtt.connack_string(conn_res),
            )
            self._connected.set_exception(MqttCodeError("Connect", conn_res))
        else:
            _LOGGER.debug(
                "MQTT connected with result code: %s", mqtt.connack_string(conn_res)
            )

            # Automatically subscribe to the topic
            sub_res, _ = client.subscribe(self._topic_id, qos=0)
            if sub_res:
                _LOGGER.error("Subscribe error: %s", mqtt.error_string(sub_res))
                self._connected.set_exception(
                    MqttCodeError(
                        "Subscribe",
                        sub_res,
                        "Could not subscribe to topic after connect",
                    )
                )
            else:
                self._connected.set_result(conn_res)

    @staticmethod
    def on_subscribe(_client: mqtt.Client, _userdata: Any, mid: int, granted_qos: int):
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
        _LOGGER.debug("MQTT subscribed msg_id: %s qos: %s", str(mid), str(granted_qos))

    def on_unsubscribe(self, client: mqtt.Client, _userdata: Any, mid: int):
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
        self._disconnecting = True
        client.disconnect()

    def on_disconnect(self, _client: mqtt.Client, _userdata: Any, disconn_res: int):
        """On Disconnect callback.

        Parameters
        ----------
        client : mqtt.Client
            The paho-mqtt client
        userdata
            user data passed by the client
        disconn_res
            Disconnect error code
        """
        # Return early if already connected. Sometimes this will be called multiple times.
        if not self._disconnected or self._disconnected.done():
            return

        if disconn_res:
            _LOGGER.error(
                "MQTT disconnect error, result code: %s (This may not be accurate)",
                mqtt.error_string(disconn_res),
            )
            self._disconnected.set_exception(MqttCodeError("Disconnect", disconn_res))
        else:
            _LOGGER.debug(
                "MQTT disconnected with result code: %s",
                mqtt.error_string(disconn_res),
            )
            self._disconnected.set_result(disconn_res)

        if not self._disconnecting:
            _LOGGER.debug("Unexpected MQTT disconnect. Will attempt reconnect shortly.")

    @staticmethod
    def on_message(msg: mqtt.MQTTMessage):
        """On Message Callback.

        Parameters
        ----------
        msg : MQTTMessage
            This is a class with members topic, payload, qos, retain
        """
        _LOGGER.debug("rx msg on %s\n%s", msg.topic, msg.payload.decode("utf8"))

    def _on_message(self, _client: mqtt.Client, _userdata: Any, msg: mqtt.MQTTMessage):
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
        if not self._rx_msg or self._rx_msg.done():
            msg_if_decoded = None
            try:
                msg_if_decoded = msg.payload.decode("utf8")
            except Exception as ex:
                msg_if_decoded = f"Could not decode message: {ex}"
            _LOGGER.debug(
                "Unexpected message, just skipping for now: %s (decoded = %s)",
                msg,
                msg_if_decoded,
            )
        else:
            self._rx_msg.set_result((msg.payload.decode("utf8")))
            self.on_message(msg)

    @staticmethod
    def msg_to_usage_measurement(
        msg: mqtt.MQTTMessage,
    ) -> Optional[RealtimeUsageMeasurement]:
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
        await self._duke_energy.select_default_meter()

    async def connect_and_subscribe_forever(self):
        """MQTT client connection that runs indefinitely and restarts the connection upon any failure."""
        while True:
            try:
                await self.connect_and_subscribe()
            except (MqttError, RequestError) as retry_err:
                # Exponential backoff of retry interval, maxing out at FOREVER_RETRY_BASE_MAX_MINUTES
                self._forever_retry_count += 1
                reconnect_interval = min(
                    FOREVER_RETRY_MIN_MINUTES * 2 ** (self._forever_retry_count - 1),
                    FOREVER_RETRY_MAX_MINUTES,
                )
                _LOGGER.warning(
                    "Caught retryable error '%s' in forever loop. Will attempt reconnect in %d minute(s). Attempt #%d. Error: %s'",
                    retry_err.__class__.__name__,
                    reconnect_interval,
                    self._forever_retry_count,
                    retry_err,
                )
                await asyncio.sleep(reconnect_interval * 60)  # interval is in minutes
            except Exception as error:
                _LOGGER.error(
                    "Caught non-retryable error '%s' in forever loop. Will not attempt reconnect. Error: %s",
                    error.__class__.__name__,
                    error,
                )
                raise

    async def connect_and_subscribe(self):
        """MQTT client connection."""
        # Reinitialize everything for a new connection
        self._disconnected = self._loop.create_future()
        self._disconnecting = False
        self._connected = self._loop.create_future()
        self._rx_msg = None
        self._t_start = (
            -FASTPOLL_TIMEOUT_SEC
        )  # ensure fastpoll is requested on first run
        self._msg_retry_count = 0

        self._mqtt_auth, self._headers = await self._duke_energy.get_mqtt_auth()
        self._topic_id = f'DESH/{self._mqtt_auth["gateway"]}/out/sm/1/live'

        self._mqtt_client = mqtt.Client(
            self._mqtt_auth["clientid"],
            transport="websockets",
            reconnect_on_failure=False,
        )
        self._mqtt_client.on_connect = self.on_connect
        self._mqtt_client.on_subscribe = self.on_subscribe
        self._mqtt_client.on_unsubscribe = self.on_unsubscribe
        self._mqtt_client.on_disconnect = self.on_disconnect
        self._mqtt_client.on_message = self._on_message
        self._mqtt_client.enable_logger(logger=_LOGGER)
        self._mqtt_client.ws_set_options(path=MQTT_ENDPOINT, headers=self._headers)
        self._mqtt_client.username_pw_set(
            self._mqtt_auth["user"], password=self._mqtt_auth["pass"]
        )
        # create default ssl context to get SSLKEYLOGFILE env variable
        self._mqtt_client.tls_set_context(ssl.create_default_context())

        mqtt_conn = MqttConnHelper(self._loop, self._mqtt_client)
        await self._async_mqtt_client_connect()

        try:
            while not mqtt_conn.misc.cancelled():
                if time.perf_counter() - self._t_start > FASTPOLL_TIMEOUT_SEC:
                    # Request fastpoll
                    await self._fastpoll_req()
                self._rx_msg = self._loop.create_future()
                try:
                    await asyncio.wait_for(self._rx_msg, MESSAGE_TIMEOUT_SEC)
                    self._msg_retry_count = 0
                    self._forever_retry_count = 0
                except asyncio.TimeoutError:
                    self._msg_retry_count += 1
                    if self._disconnected.done():
                        _LOGGER.debug(
                            "Unexpected disconnect detected, attemping reconnect"
                        )
                        await self._reconnect()
                    elif self._msg_retry_count > MESSAGE_TIMEOUT_RETRY_COUNT:
                        _LOGGER.debug("Multiple msg timeout, attempting reconnect")
                        await self._reconnect()
                    else:
                        _LOGGER.debug("Message timeout, requesting fastpoll")
                        await self._fastpoll_req()
                self._rx_msg = None
        finally:
            res = self._mqtt_client.unsubscribe(self._topic_id)
            if not res:
                _LOGGER.warning("Unsubscribe error: %s", mqtt.error_string(res))
            await self._disconnected

    async def _fastpoll_req(self):
        """Request fastpoll, with auth check."""
        try:
            (
                mqtt_auth_new,
                headers_new,
            ) = await self._duke_energy.get_mqtt_auth()
        except RequestError:
            _LOGGER.warning(
                "Error requesting smartmeter auth, will retry after 5 seconds."
            )
            # Attempt clearing auth and try again.
            self._duke_energy._gateway_auth_info.clear_access_token()  # pylint: disable=W0212
            await asyncio.sleep(5)
            (
                mqtt_auth_new,
                headers_new,
            ) = await self._duke_energy.get_mqtt_auth()
        if mqtt_auth_new != self._mqtt_auth or headers_new != self._headers:
            _LOGGER.debug("mqtt auth or headers updated, reconnecting...")
            self._mqtt_auth = mqtt_auth_new
            self._headers = headers_new
            await self._reconnect()
        self._t_start = await self._duke_energy.start_smartmeter_fastpoll()

    async def _reconnect(self):
        """Reconnect in case of updated auth or headers."""
        # Unsub and disconnect first
        res = self._mqtt_client.unsubscribe(self._topic_id)
        if not res:
            _LOGGER.warning("Unsubscribe error: %s", mqtt.error_string(res))
        await self._disconnected

        # Update mqtt_auth and header info
        client_id = self._mqtt_auth["clientid"]
        if isinstance(client_id, str):
            client_id = client_id.encode("utf-8")
        self._mqtt_client._client_id = client_id  # pylint: disable=W0212
        self._mqtt_client.ws_set_options(path=MQTT_ENDPOINT, headers=self._headers)
        self._mqtt_client.username_pw_set(
            self._mqtt_auth["user"], password=self._mqtt_auth["pass"]
        )
        await self._async_mqtt_client_connect()

    async def _async_mqtt_client_connect(self):
        """Run connect() in an async safe manner to avoid blocking."""
        # Re-create the futures
        if self._disconnected.done():
            self._disconnected = self._loop.create_future()
        if self._connected.done():
            self._connected = self._loop.create_future()

        # Run connect() within an executor thread, since it blocks on socket
        # connection for up to `keepalive` seconds: https://git.io/Jt5Yc
        try:
            await self._loop.run_in_executor(
                None,
                functools.partial(
                    self._mqtt_client.connect,
                    MQTT_HOST,
                    port=MQTT_PORT,
                    keepalive=MQTT_KEEPALIVE,
                ),
            )
        except (socket.error, OSError, mqtt.WebsocketConnectionError) as error:
            raise MqttError(f"Failure attempting MQTT connect: {error}") from error

        try:
            await asyncio.wait_for(self._connected, CONNECT_TIMEOUT_SEC)
        except asyncio.TimeoutError as to_err:
            raise MqttError(
                f"Connect operation timed out after {CONNECT_TIMEOUT_SEC} seconds"
            ) from to_err


class MqttConnHelper:
    """Helper for asyncio mqtt."""

    def __init__(self, loop: asyncio.AbstractEventLoop, mqtt_client: mqtt.Client):
        self._loop = loop
        self._mqtt_client = mqtt_client
        self._mqtt_client.on_socket_open = self.on_socket_open
        self._mqtt_client.on_socket_close = self.on_socket_close
        self._mqtt_client.on_socket_register_write = self.on_socket_register_write
        self._mqtt_client.on_socket_unregister_write = self.on_socket_unregister_write
        self.misc = None

    def on_socket_open(
        self, client: mqtt.Client, _userdata: Any, sock: mqtt.WebsocketWrapper
    ):
        """Socket open callback."""
        _LOGGER.debug("Socket opened")

        def call_bk():
            """Socket reader callback."""
            _LOGGER.debug("Socket readable, calling loop_read()")
            client.loop_read()

        self._loop.add_reader(sock, call_bk)

        # paho-mqtt calls this function from the executor thread on which we've called
        # `self._client.connect()`, so we create a callback function to schedule
        # `_misc_loop()` and run it on the loop thread-safely.
        def create_task_cb() -> None:
            self.misc = self._loop.create_task(self.misc_loop())

        self._loop.call_soon_threadsafe(create_task_cb)

    def on_socket_close(
        self, _client: mqtt.Client, _userdata: Any, sock: mqtt.WebsocketWrapper
    ):
        """Socket close callback."""
        _LOGGER.debug("Socket closed")
        self._loop.remove_reader(sock)
        if self.misc is not None:
            self.misc.cancel()

    def on_socket_register_write(
        self, client: mqtt.Client, _userdata: Any, sock: mqtt.WebsocketWrapper
    ):
        """Socket write reg callback."""
        _LOGGER.debug("Watching socket for writability.")

        def call_bk():
            """Socket write callback."""
            _LOGGER.debug("Socket is writable, calling loop_write")
            client.loop_write()

        self._loop.add_writer(sock, call_bk)

    def on_socket_unregister_write(
        self, _client: mqtt.Client, _userdata: Any, sock: mqtt.WebsocketWrapper
    ):
        """Socket unreg write callback."""
        _LOGGER.debug("Stop watching socket for writability.")
        self._loop.remove_writer(sock)

    async def misc_loop(self):
        """Misc loop call."""
        _LOGGER.debug("Misc loop started")

        while self._mqtt_client.loop_misc() == mqtt.MQTT_ERR_SUCCESS:
            try:
                await asyncio.sleep(1)
            except asyncio.CancelledError:
                _LOGGER.debug("Misc loop cancelled")
                break

        _LOGGER.debug("Misc loop finished")
