"""Error Types"""

class DukeEnergyError(Exception):
    """Base error."""

class RequestError(DukeEnergyError):
    """Error for request issues"""

class InputError(DukeEnergyError):
    """Error for input issues"""