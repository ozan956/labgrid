"""Driver to program Xilinx FPGAs and boot Zynq/ZynqMP/Microblaze via xsdb.

xsdb (the Xilinx System Debugger) ships with Vivado/Vitis and drives the JTAG
chain through a TCL command interface. This driver generates a small TCL
script per operation and runs it through ``xsdb``, either locally (when the
test runner is the exporter) or on the exporter host (when the JTAG debugger
is a ``NetworkUSBDebugger`` reached through a coordinator). The local/remote
decision and the ssh transport are handled entirely by the bound resource's
``wrap_command`` -- the same mechanism :class:`OpenOCDDriver` uses -- so no
driver-side ssh handling is needed.

All file arguments (bitstream, kernel/ELF image, ps7_init.tcl) are staged to
the host that runs xsdb via :class:`~labgrid.util.managedfile.ManagedFile`
before the script references them, so the caller only needs the files locally.
"""

import os
import tempfile

import attr

from ..factory import target_factory
from ..protocol import BootstrapProtocol
from ..step import step
from ..util.helper import processwrapper
from ..util.managedfile import ManagedFile
from .common import Driver


@target_factory.reg_driver
@attr.s(eq=False)
class XSDBDriver(Driver, BootstrapProtocol):
    """Program Xilinx FPGAs / boot Zynq(-MP)/Microblaze via xsdb.

    Binds to a USB (or network) JTAG debugger resource, exactly like
    :class:`OpenOCDDriver`. ``xsdb`` is resolved from the environment tool
    config (``tools: {xsdb: ...}``) with a ``"xsdb"`` PATH fallback, or
    overridden with the ``xsdb`` attribute.

    Bindings:
        interface: a ``USBDebugger``/``NetworkUSBDebugger`` (the JTAG adapter).
    """

    bindings = {
        "interface": {
            "USBDebugger",
            "NetworkUSBDebugger",
        },
    }

    #: Optional explicit path to the xsdb executable; overrides tool config.
    xsdb = attr.ib(
        default=None,
        validator=attr.validators.optional(attr.validators.instance_of(str)),
    )
    #: Default bitstream image name (resolved via the env image config) used by
    #: :meth:`load` when no filename is passed -- mirrors OpenOCDDriver.image.
    image = attr.ib(
        default=None,
        validator=attr.validators.optional(attr.validators.instance_of(str)),
    )

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        if self.xsdb is not None:
            self.tool = self.xsdb
        elif self.target.env:
            self.tool = self.target.env.config.get_tool("xsdb")
        else:
            self.tool = "xsdb"

    def _stage(self, local_path):
        """Copy a local file to the host that runs xsdb; return its path there.

        For a local resource this is the (absolute) local path; for a
        ``NetworkUSBDebugger`` the file is synced to the exporter and the
        remote path is returned.
        """
        mf = ManagedFile(local_path, self.interface)
        mf.sync_to_resource()
        return mf.get_remote_path()

    def _run_tcl(self, tcl):
        """Run a TCL script through xsdb, locally or on the exporter host."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".tcl", delete=False
        ) as f:
            f.write(tcl)
            local_tcl = f.name
        try:
            remote_tcl = self._stage(local_tcl)
            cmd = self.interface.wrap_command([self.tool, remote_tcl])
            processwrapper.check_output(cmd, print_on_silent_log=True)
        finally:
            os.unlink(local_tcl)

    @Driver.check_active
    @step(args=["filename"])
    def load(self, filename=None):
        """Program a bitstream onto the FPGA (BootstrapProtocol).

        With no ``filename``, uses the configured ``image``. Shares the
        BootstrapProtocol surface with :class:`OpenOCDDriver` so callers can
        treat either JTAG driver uniformly.
        """
        if filename is None and self.image is not None:
            filename = self.target.env.config.get_image_path(self.image)
        self.program_fpga(filename)

    @Driver.check_active
    @step(args=["bitstream", "target"])
    def program_fpga(self, bitstream, target="1"):
        """Program ``bitstream`` onto the FPGA at JTAG ``target``."""
        remote_bit = self._stage(bitstream)
        tcl = (
            "connect\n"
            "after 1000\n"
            f"targets {target}\n"
            "after 1000\n"
            f"fpga -f {remote_bit}\n"
            "after 2000\n"
            'puts "bitstream programmed"\n'
        )
        self._run_tcl(tcl)

    @Driver.check_active
    @step(args=["image", "target"])
    def download(self, image, target):
        """Download an ELF/image to a JTAG ``target`` (xsdb ``dow``)."""
        remote_img = self._stage(image)
        tcl = (
            "connect\n"
            "after 1000\n"
            f"targets {target}\n"
            "after 1000\n"
            f"dow {remote_img}\n"
            "after 1000\n"
            'puts "image downloaded"\n'
        )
        self._run_tcl(tcl)

    @Driver.check_active
    @step(args=["bitstream", "kernel", "root_target", "microblaze_target"])
    def load_fabric(self, bitstream, kernel, root_target="1", microblaze_target="3"):
        """Program fabric + download a kernel to the Microblaze and run it.

        The logic-only FPGA path (Virtex/Artix/Kintex + Microblaze): program
        the PL, ``dow`` the kernel onto the Microblaze target, then ``con``.
        """
        remote_bit = self._stage(bitstream)
        remote_kernel = self._stage(kernel)
        tcl = (
            "connect\n"
            "after 1000\n"
            f"targets {root_target}\n"
            "after 1000\n"
            f"fpga -f {remote_bit}\n"
            "after 2000\n"
            f"targets {microblaze_target}\n"
            "after 1000\n"
            f"dow {remote_kernel}\n"
            "after 1000\n"
            "con\n"
            "after 500\n"
            'puts "fabric loaded and running"\n'
        )
        self._run_tcl(tcl)

    @Driver.check_active
    @step(args=["elf", "cpu", "bitstream", "ps7_init_tcl"])
    def load_elf(self, elf, cpu="*Cortex-A9 MPCore #0", bitstream=None, ps7_init_tcl=None):
        """JTAG-load and run a bare-metal ELF (e.g. U-Boot or no-os firmware).

        Runs the standard xsdb sequence on a Zynq(-MP) core:
        ``connect -> targets <cpu> -> rst -system -> [fpga] -> [ps7_init] ->
        dow elf -> con``. ``bitstream`` programs the PL first (needed when the
        firmware touches fabric peripherals); ``ps7_init_tcl`` runs the board
        PS init. The ``cpu`` name-filter is used instead of an integer index
        because Zynq target ordering shifts once the PL is loaded.
        """
        lines = [
            "connect",
            "after 1000",
            f'targets -set -filter {{name =~ "{cpu}"}}',
            "after 500",
            "rst -system",
            "after 2000",
        ]
        if bitstream:
            lines.append(f"fpga -f {self._stage(bitstream)}")
            lines.append("after 2000")
        if ps7_init_tcl:
            lines.append(f"source {self._stage(ps7_init_tcl)}")
            lines.append("ps7_init")
            lines.append("ps7_post_config")
        lines.append(f"dow {self._stage(elf)}")
        lines.append("con")
        lines.append('puts "ELF started via JTAG"')
        self._run_tcl("\n".join(lines) + "\n")

    @Driver.check_active
    @step(args=["cpu"])
    def stop(self, cpu="*Cortex-A9 MPCore #0"):
        """Halt a CPU core (used between failed bootstrap attempts)."""
        tcl = (
            "connect\n"
            "after 500\n"
            f'targets -set -filter {{name =~ "{cpu}"}}\n'
            "stop\n"
            'puts "cpu stopped"\n'
        )
        self._run_tcl(tcl)

    @Driver.check_active
    @step()
    def disconnect(self):
        """Disconnect from the JTAG session."""
        self._run_tcl('disconnect\nputs "disconnected"\n')
