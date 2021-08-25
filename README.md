# pyDuke-Energy

[![PyPi Project][pypi-shield]][pypi]
[![GitHub Build][build-shield]][build]
[![GitHub Activity][commits-shield]][commits]
[![License][license-shield]](LICENSE)

[![Project Maintenance][maintenance-shield]][user_profile]
[![GitHub Top Language][language-shield]][language]
[![Black][black-shield]][black]

Python3 wrapper for the unofficial Duke Energy API.

Designed to work with Home Assistant. Unlikely to ever be fully implemented. The primary goal is to expose Duke Energy Gateway usage information.

## Before You Begin

### Disclaimer

The API is unofficial, not documented, and probably not supposed to be used by third-parties. It is only accessible as it powers the Duke Energy phone app and we can mimic the app requests.

In addition, the Gateway functionality is part of a pilot program. There is no guarantee on availability going forward.

With that said, please see this disclaimer: **This library could stop working at any time. Some functionality may be removed from the API entirely. Duke Energy may even request we stop hitting this API.**

Along those same lines, **please do not abuse their API**.

### Gateway Requirement

In order to call the gateway related functions, including getting energy usage, you will need to have a Duke Energy Gateway. This is currently available via a pilot program.

It is possible to query _yesterday's_ energy usage without a gateway; however, I have not implemented that as I did not find it useful.

### Limitations

Some limitations I've identified:

- Real-time power usage is not easily available. It is retrieved in the app via an MQTT websockets connection. I've been unable to figure out how to connect myself.
- Non-real-time Energy usage data is down to the minute, but doesn't appear to be reported every minute and I see delays up to 15 minutes. My best guess is that the gateway only sends data to Duke Energy every 15 minutes. This is a limitation in the app as well.

## Usage

### Installation

The latest version is available on PyPi.

```bash
pip install pyduke-energy
```

### Example Usage

A detailed example of how to use this library is in [example.py](example.py). The quick example below shows how to retrieve usage info.

```python
# Meter data below can be retrieved via the API - see example.py
meter_num = 123456789
meter_activation_date = datetime.datetime(2021, 1, 1)

async with aiohttp.ClientSession() as client:
    duke_energy = DukeEnergyClient(email, password, client)
    duke_energy.select_meter_by_id(meter_num, meter_activation_date) # NB: can also use MeterInfo from API with select_meter()
    usage = duke_energy.get_gateway_usage(datetime.date(2021, 1, 1), datetime.date(2021, 1, 2))
```

#### Running Example

If you want to run the example, you might need to install extra dependencies.

```bash
pip install .[example]
python example.py
```

## Development

### Environment Setup

#### Dev Container

The preferred method of development is using the Visual Studio Code devcontainer, which will handle setting up your environment including all dependencies.

1. Open repo in VS Code (e.g. `code .` from repo root)
2. Re-open in container when the pop-up appears in VS Code
3. Wait for the container to build
4. Done!

#### Manual Installation

You can also develop outside of a dev container if desired. The example below uses a `virtualenv` which is optional but recommended.

```bash
virtualenv venv
source venv/bin/activate
pip install -e .[example,tests]
```

### Testing

The test command will run the test suite and also run linting against all source files.

```bash
tox
```

To run just the tests:

```bash
tox -e py39
```

To run just the linting:

```bash
tox -e lint
```

[black]: https://github.com/psf/black
[black-shield]: https://img.shields.io/badge/code%20style-black-000000.svg?style=for-the-badge
[commits-shield]: https://img.shields.io/github/commit-activity/y/mjmeli/pyduke-energy.svg?style=for-the-badge
[commits]: https://github.com/mjmeli/pyduke-energy/commits/main
[license-shield]: https://img.shields.io/github/license/mjmeli/pyduke-energy.svg?style=for-the-badge
[maintenance-shield]: https://img.shields.io/badge/maintainer-%40mjmeli-blue.svg?style=for-the-badge
[pypi-shield]: https://img.shields.io/pypi/v/pyduke-energy?style=for-the-badge
[pypi]: https://pypi.org/project/pyduke-energy/
[build-shield]: https://img.shields.io/github/workflow/status/mjmeli/pyduke-energy/Tests?style=for-the-badge
[build]: https://github.com/mjmeli/pyduke-energy/actions/workflows/tests.yaml
[language-shield]: https://img.shields.io/github/languages/top/mjmeli/pyduke-energy?style=for-the-badge
[language]: https://github.com/mjmeli/ha-duke-energy-gateway/search?l=python
[user_profile]: https://github.com/mjmeli
