import argparse

from labgrid import Target
from labgrid.driver.openocddriver import OpenOCDDriver
from labgrid.remote.client import ClientSession
from labgrid.resource.remote import NetworkAlteraUSBBlaster


def make_session(arguments):
    target = Target("test")
    blaster = NetworkAlteraUSBBlaster(
        target,
        name=None,
        host="host",
        busnum=1,
        devnum=2,
        path="1-2",
        vendor_id=1,
        model_id=2,
    )
    blaster.manager.poll = lambda: None
    blaster.avail = True

    session = object.__new__(ClientSession)
    session.args = argparse.Namespace(wait=12.5, name=None, arguments=arguments)
    session.get_acquired_place = lambda: argparse.Namespace(name="test")
    session._get_target = lambda place: target
    return session, target


def test_bootstrap_openocd_with_multiple_files(monkeypatch):
    session, target = make_session(["first.elf", "second.elf"])
    load_calls = []
    monkeypatch.setattr(OpenOCDDriver, "load", lambda self, filename: load_calls.append(filename))

    session.bootstrap()

    assert target.get_driver(OpenOCDDriver, activate=False).interface.timeout == 12.5
    assert load_calls == ["first.elf", "second.elf"]


def test_bootstrap_openocd_without_file_executes_config(monkeypatch):
    session, _ = make_session(["config=board.cfg"])
    execute_calls = []
    monkeypatch.setattr(OpenOCDDriver, "execute", lambda self, commands: execute_calls.append(commands))

    session.bootstrap()

    assert execute_calls == [[]]
