"""Tests for pyduke-energy."""

import aiohttp
import pytest

from pyduke_energy.client import DukeEnergyClient


@pytest.mark.asyncio
async def test_duke_energy_client_creation():
    """Test we can create the object."""
    dec = DukeEnergyClient(
        "me@gmail.com",
        "mypassword",
        aiohttp.ClientSession(),
    )
    assert dec
