from pathlib import Path

from labgrid.driver.openocddriver import OpenOCDDriver
from labgrid.resource.udev import USBDebugger


class DummyConfig:
    def __init__(self, images):
        self.images = images

    def get_tool(self, tool):
        return tool

    def resolve_path_str_or_list(self, path):
        if isinstance(path, str):
            return [path]
        return path

    def get_image_path(self, name):
        return self.images[name]


class DummyEnv:
    def __init__(self, images):
        self.config = DummyConfig(images)


class DummyManagedFile:
    created = []

    def __init__(self, filename, resource):
        self.filename = filename
        self.resource = resource
        self.synced = False
        type(self).created.append(self)

    def sync_to_resource(self):
        self.synced = True

    def get_remote_path(self):
        return f"/remote/{Path(self.filename).name}"


def test_openocd_load_commands_without_file(target, monkeypatch):
    resource = USBDebugger(target, name=None, match={"sys_name": "1-12"})
    resource.avail = True
    driver = OpenOCDDriver(target, name=None, load_commands=["init", "shutdown"])
    target.activate(driver)

    called = {}

    def fake_check_output(cmd, print_on_silent_log=True):
        called["cmd"] = cmd

    def fail_managed_file(*args, **kwargs):
        raise AssertionError("ManagedFile should not be used when no placeholders are present")

    monkeypatch.setattr("labgrid.driver.openocddriver.processwrapper.check_output", fake_check_output)
    monkeypatch.setattr("labgrid.driver.openocddriver.ManagedFile", fail_managed_file)

    driver.load()

    assert "--command" in called["cmd"]
    assert "init" in called["cmd"]
    assert "shutdown" in called["cmd"]


def test_openocd_load_commands_with_multiple_images(target, monkeypatch):
    target.env = DummyEnv(
        {
            "bootstrap": "/tmp/bootstrap.bin",
            "flash_image": "/tmp/flash.bin",
        }
    )
    resource = USBDebugger(target, name=None, match={"sys_name": "1-12"})
    resource.avail = True
    driver = OpenOCDDriver(
        target,
        name=None,
        load_commands=[
            "init",
            "bootstrap {filename}",
            "flash write_image erase {flash_image} 0x0",
            "shutdown",
        ],
    )
    target.activate(driver)

    called = {}
    DummyManagedFile.created = []

    def fake_check_output(cmd, print_on_silent_log=True):
        called["cmd"] = cmd

    monkeypatch.setattr("labgrid.driver.openocddriver.processwrapper.check_output", fake_check_output)
    monkeypatch.setattr("labgrid.driver.openocddriver.ManagedFile", DummyManagedFile)

    driver.load("/tmp/bootstrap.bin")

    assert [mf.filename for mf in DummyManagedFile.created] == ["/tmp/bootstrap.bin", "/tmp/flash.bin"]
    assert all(mf.synced for mf in DummyManagedFile.created)
    assert "bootstrap /remote/bootstrap.bin" in called["cmd"]
    assert "flash write_image erase /remote/flash.bin 0x0" in called["cmd"]


def test_openocd_load_commands_with_multiple_filenames(target, monkeypatch):
    resource = USBDebugger(target, name=None, match={"sys_name": "1-12"})
    resource.avail = True
    driver = OpenOCDDriver(
        target,
        name=None,
        load_commands=[
            'set BOOT_SEQ {{ {{ {filename} board_init_r }} {{ {filename1} "" }} }}',
            "source [find tools/boot.tcl]",
        ],
    )
    target.activate(driver)

    called = {}
    DummyManagedFile.created = []

    def fake_check_output(cmd, print_on_silent_log=True):
        called["cmd"] = cmd

    monkeypatch.setattr("labgrid.driver.openocddriver.processwrapper.check_output", fake_check_output)
    monkeypatch.setattr("labgrid.driver.openocddriver.ManagedFile", DummyManagedFile)

    driver.load(["/tmp/u-boot-spl", "/tmp/u-boot"])

    assert [mf.filename for mf in DummyManagedFile.created] == ["/tmp/u-boot-spl", "/tmp/u-boot"]
    assert 'set BOOT_SEQ { { /remote/u-boot-spl board_init_r } { /remote/u-boot "" } }' in called["cmd"]
