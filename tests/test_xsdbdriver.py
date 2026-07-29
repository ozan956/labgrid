"""Unit tests for XSDBDriver -- no hardware, no real xsdb.

The driver writes a TCL script to a temp file, stages it via ManagedFile
(a no-op path-passthrough for a local resource), and runs
``xsdb <script>`` through processwrapper.check_output. We monkeypatch
check_output to capture the command and read back the generated TCL, then
assert the expected xsdb verbs (fpga -f / dow / con / rst -system) are
present and reference staged files.
"""

import pytest

from labgrid.driver.xsdbdriver import XSDBDriver
from labgrid.resource.udev import USBDebugger


@pytest.fixture
def xsdb_driver(target):
    r = USBDebugger(target, name=None, match={"sys_name": "1-12"})
    r.avail = True
    d = XSDBDriver(target, name=None, xsdb="xsdb")
    target.activate(d)
    return d


@pytest.fixture
def captured_tcl(monkeypatch):
    """Patch processwrapper.check_output; return a list the driver fills with
    the TCL text of every xsdb invocation."""
    scripts = []

    def fake_check_output(command, *args, **kwargs):
        # command is [xsdb, <script.tcl>] (local resource -> no ssh wrap)
        assert command[0] == "xsdb"
        tcl_path = command[-1]
        assert tcl_path.endswith(".tcl")
        with open(tcl_path) as f:
            scripts.append(f.read())
        return b""

    monkeypatch.setattr(
        "labgrid.driver.xsdbdriver.processwrapper.check_output",
        fake_check_output,
    )
    return scripts


def test_registration():
    from labgrid.driver import XSDBDriver as Exported

    assert Exported is XSDBDriver


def test_tool_resolution_override(target):
    r = USBDebugger(target, name=None, match={"sys_name": "1-12"})
    r.avail = True
    d = XSDBDriver(target, name=None, xsdb="/opt/Xilinx/2025.1/Vitis/bin/xsdb")
    assert d.tool == "/opt/Xilinx/2025.1/Vitis/bin/xsdb"


def test_tool_resolution_default(target):
    r = USBDebugger(target, name=None, match={"sys_name": "1-12"})
    r.avail = True
    d = XSDBDriver(target, name=None)
    # No env config in the bare Target fixture -> PATH fallback.
    assert d.tool == "xsdb"


def test_program_fpga(xsdb_driver, captured_tcl, tmp_path):
    bit = tmp_path / "system_top.bit"
    bit.write_bytes(b"\x00bit")
    xsdb_driver.program_fpga(str(bit), target="1")

    (tcl,) = captured_tcl
    assert "connect" in tcl
    assert "targets 1" in tcl
    assert f"fpga -f {bit}" in tcl


def test_load_uses_bootstrap_surface(xsdb_driver, captured_tcl, tmp_path):
    # load() is the BootstrapProtocol entry point; delegates to program_fpga.
    bit = tmp_path / "top.bit"
    bit.write_bytes(b"\x00bit")
    xsdb_driver.load(str(bit))
    (tcl,) = captured_tcl
    assert f"fpga -f {bit}" in tcl


def test_load_fabric(xsdb_driver, captured_tcl, tmp_path):
    bit = tmp_path / "system_top.bit"
    bit.write_bytes(b"\x00bit")
    kern = tmp_path / "simpleImage.strip"
    kern.write_bytes(b"\x00elf")
    xsdb_driver.load_fabric(str(bit), str(kern), root_target="1", microblaze_target="3")

    (tcl,) = captured_tcl
    assert f"fpga -f {bit}" in tcl
    assert "targets 3" in tcl
    assert f"dow {kern}" in tcl
    assert "con" in tcl


def test_load_elf_minimal(xsdb_driver, captured_tcl, tmp_path):
    elf = tmp_path / "u-boot.elf"
    elf.write_bytes(b"\x00elf")
    xsdb_driver.load_elf(str(elf))

    (tcl,) = captured_tcl
    assert "rst -system" in tcl
    assert 'targets -set -filter {name =~ "*Cortex-A9 MPCore #0"}' in tcl
    assert f"dow {elf}" in tcl
    assert "con" in tcl
    # no bitstream / ps7 -> those verbs absent
    assert "fpga -f" not in tcl
    assert "ps7_init" not in tcl


def test_load_elf_with_bitstream_and_ps7(xsdb_driver, captured_tcl, tmp_path):
    elf = tmp_path / "fw.elf"
    elf.write_bytes(b"\x00elf")
    bit = tmp_path / "top.bit"
    bit.write_bytes(b"\x00bit")
    ps7 = tmp_path / "ps7_init.tcl"
    ps7.write_text("proc ps7_init {} {}\n")
    xsdb_driver.load_elf(str(elf), cpu="*Cortex-A53*#0", bitstream=str(bit), ps7_init_tcl=str(ps7))

    (tcl,) = captured_tcl
    assert f"fpga -f {bit}" in tcl
    assert f"source {ps7}" in tcl
    assert "ps7_init" in tcl
    assert f"dow {elf}" in tcl
    assert 'name =~ "*Cortex-A53*#0"' in tcl


def test_missing_local_file_raises(xsdb_driver, captured_tcl):
    # ManagedFile raises FileNotFoundError before any xsdb call.
    with pytest.raises(FileNotFoundError):
        xsdb_driver.program_fpga("/nonexistent/system_top.bit")
    assert captured_tcl == []
