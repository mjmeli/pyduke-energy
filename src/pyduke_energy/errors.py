"""Error Types."""

from typing import Any, Union

import paho.mqtt.client as mqtt


class DukeEnergyError(Exception):
    """Base error."""


class RequestError(DukeEnergyError):
    """Error for request issues."""


class InputError(DukeEnergyError):
    """Error for input issues."""


class MqttError(DukeEnergyError):
    """Error for issues relating to the MQTT connection."""


class MqttCodeError(MqttError):
    """Error for MQTT issues associated with an error code."""

    def __init__(self, operation: str, code: Union[int, mqtt.ReasonCodes], *args: Any):
        super().__init__(*args)
        self.operation = operation
        self.code = code

    def __str__(self) -> str:
        """Output a formatted string for the error code."""
        if isinstance(self.code, mqtt.ReasonCodes):
            return f"{self.operation}: ({self.code.value}) {str(self.code)}"
        if isinstance(self.code, int):
            return f"{self.operation}: ({self.code}) {mqtt.error_string(self.code)}"
        return f"{self.operation}: ({self.code}) {super().__str__()}"
