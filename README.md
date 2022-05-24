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

The library supports access to the real-time power usage implemented via an MQTT over websockets connection, or a more traditional REST API to poll near-real-time data.

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

- Non-real-time Energy usage data is down to the minute, but is only updated once every 15 minutes. Meaning, the last 15 minutes of minute-by-minute data will all arrive at once after 15 minutes. My best guess is that the gateway only sends data to Duke Energy every 15 minutes. This is a limitation in the app as well.

## Usage

### Installation

The latest version is available on PyPi.

```bash
pip install pyduke-energy
```

### Examples

Various usage examples can be found in the `examples/` folder of this repo.

#### Example REST API Usage

The quick example below shows how to retrieve non-real-time usage info using the traditional REST API.

```python
async with aiohttp.ClientSession() as client:
    duke_energy = DukeEnergyClient(email, password, client)
    await duke_energy.select_default_meter() # NB: can also use MeterInfo from API with select_meter()
    usage = await duke_energy.get_gateway_usage(datetime.date(2021, 1, 1), datetime.date(2021, 1, 2))
```

A more detailed example is in [examples/example_rest.py](examples/example_rest.py).

#### Example Real-time Usage

Real-time usage can be retrieved using an MQTT connection. The quick example below shows how to do this using the default real-time client.

```python
async with aiohttp.ClientSession() as client:
    duke_energy = DukeEnergyClient(email, password, client)
    duke_rt = DukeEnergyRealtime(duke_energy)
    await duke_rt.select_default_meter()
    await duke_rt.connect_and_subscribe_forever()
```

More detailed examples can be found in [examples/example_realtime.py](examples/example_realtime.py) and [examples/example_realtime_kafka.py](examples/example_realtime_kafka.py).

#### Running Examples

If you want to run the examples, you will need to install extra dependencies.

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
tox -e py310
```

To run just the linting:

```bash
tox -e lint
```

### Android App Debugging

If you want to debug requests via the Android app, the following general approach works well for me.

1. Install [HTTP Toolkit](https://httptoolkit.tech/) on your computer.
2. Set up Android Studio so that you can use an emulator through it.
3. Start Android Studio emulator and use HTTP Toolkit to connect to it via ADB. Make sure to set up the HTTPS request intercepting.
4. Install Duke Energy APK on the emulator. You can download an `xapk` file from a site like APKPure. To install an `xapk` file on an emulator, extract the `xapk` file using something like WinRAR and drag the inside `apk` file to the emulator.
5. Start Duke Energy app on the emulator and logs should now be requested in your HTTP Toolkit app.

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
