# pyDuke-Energy

Python3 wrapper for the unofficial Duke Energy API.

Designed to work with Home Assistant. Unlikely to ever be fully implemented. The primary goal is to expose Duke Energy Gateway usage information.

This repo is a WIP as I'm still in the experimental phase. If all works out all, I will clean this up.

## Before You Begin

### Disclaimer

The API is unofficial, not documented, and probably not supposed to be used by third-parties. It is only accessible as it powers the Duke Energy phone app and we can mimic the app requests.

In addition, the Gateway functionality is part of a pilot program. There is no guarantee on availability going forward.

With that said, please see this disclaimer: **This library could stop working at any time. Some functionality may be removed from the API entirely. Duke Energy may even request we stop hitting this API.**

Along those same lines, **please do not abuse their API**.

### Gateway Requirement

In order to call the gateway related functions, including getting energy usage, you will need to have a Duke Energy Gateway. This is currently available via a pilot program.

It is possible to query *yesterday's* energy usage without a gateway; however, I have not implemented that as I did not find it useful.

### Limitations

Some limitations I've identified:

* Real-time power usage is not easily available. It is retrieved in the app via an MQTT websockets connection. I've been unable to figure out how to connect myself.
* Non-real-time Energy usage data is down to the minute, but doesn't appear to be reported every minute and I see delays up to 15 minutes. My best guess is that they cache the minute-by-minute data for 15 minutes. This is true in the app as well.

## Library

### Example Usage

A detailed example of how to use this library is in [example.py](example.py). The quick example below shows how to retrieve usage info.

```python
# Meter data below can be retrieved via the API - see example.py
meter_num = 123456789
meter_activation_date = datetime.datetime(2021, 1, 1)

async with aiohttp.ClientSession() as client:
    duke_energy = DukeEnergyClient(email, password, client)
    duke_energy.select_meter(meter_num, meter_activation_date)
    usage = duke_energy.get_gateway_usage(datetime.date(2021, 1, 1), datetime.date(2021, 1, 2))
```

To run the example, you might need to install extra dependencies.

```bash
pip install .[example]
```

### Installation

```bash
pip install pyduke-energy
```

### Development

Getting this running is pretty straightforward if you want to contribute.

```bash
virtualenv venv
source venv/bin/activate
pip install --editable .  # --editable is optional
```
