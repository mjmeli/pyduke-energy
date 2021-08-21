# pyDuke-Energy

Python3 wrapper for the unofficial Duke Energy API.

Designed to work with Home Assistant. Unlikely to ever be fully implemented. The primary goal is to expose Duke Energy Gateway usage information.

**NOTE** This API is not official and so this library could stop working at any time without warning. There are multiple other libraries on GitHub that are dead already due to this.

## Example Usage

A detailed example of how to use this library is in [example.py](example.py). The quick example below shows how to retrieve usage info.

    # Meter data below can be retrieved via the API - see example.py
    meter_num = 123456789
    meter_activation_date = datetime.datetime(2021, 1, 1)

    async with aiohttp.ClientSession() as client:
        duke_energy = DukeEnergyClient(email, password, client)
        duke_energy.select_meter(meter_num, meter_activation_date)
        usage = duke_energy.get_gateway_usage(datetime.date(2021, 1, 1), datetime.date(2021, 1, 2))

To run the example, you might need to install extra dependencies.

    pip install .[example]

## Installation

    pip install pyduke-energy

## Development

Getting this running is pretty straightforward if you want to contribute.

    virtualenv venv
    source venv/bin/activate
    pip install --editable .  # --editable is optional
