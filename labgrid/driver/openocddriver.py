from itertools import chain
from string import Formatter
import attr

from ..factory import target_factory
from ..protocol import BootstrapProtocol
from ..step import step
from ..util.managedfile import ManagedFile
from ..util.helper import processwrapper
from .common import Driver


@target_factory.reg_driver
@attr.s(eq=False)
class OpenOCDDriver(Driver, BootstrapProtocol):
    bindings = {
        "interface": {
            "AlteraUSBBlaster",
            "NetworkAlteraUSBBlaster",
            "USBDebugger",
            "NetworkUSBDebugger",
        },
    }

    config = attr.ib(
        default=attr.Factory(list), validator=attr.validators.optional(attr.validators.instance_of((str, list)))
    )
    search = attr.ib(
        default=attr.Factory(list), validator=attr.validators.optional(attr.validators.instance_of((str, list)))
    )
    image = attr.ib(default=None, validator=attr.validators.optional(attr.validators.instance_of(str)))
    interface_config = attr.ib(default=None, validator=attr.validators.optional(attr.validators.instance_of(str)))
    board_config = attr.ib(default=None, validator=attr.validators.optional(attr.validators.instance_of(str)))
    load_commands = attr.ib(default=None, validator=attr.validators.optional(attr.validators.instance_of(list)))

    def __attrs_post_init__(self):
        super().__attrs_post_init__()

        # FIXME make sure we always have an environment or config
        if self.target.env:
            self.tool = self.target.env.config.get_tool("openocd")
            self.config = self.target.env.config.resolve_path_str_or_list(self.config)
            self.search = self.target.env.config.resolve_path_str_or_list(self.search)
        else:
            self.tool = "openocd"
            if isinstance(self.config, str):
                self.config = [self.config]
            if isinstance(self.search, str):
                self.search = [self.search]

    def _get_usb_path_cmd(self):
        # OpenOCD supports "adapter usb location" since a1b308ab, released with 0.11.0-rc1
        return ["--command", f'adapter usb location "{self.interface.path}"']

    def _run_commands(self, commands: list):
        cmd = [self.tool]
        cmd += chain.from_iterable(("--search", path) for path in self.search)
        cmd += self._get_usb_path_cmd()

        managed_configs = []
        for config in self.config:
            mconfig = ManagedFile(config, self.interface)
            mconfig.sync_to_resource()
            managed_configs.append(mconfig)

        if self.interface_config:
            cmd.append("--file")
            cmd.append(f"interface/{self.interface_config}")

        if self.board_config:
            cmd.append("--file")
            cmd.append(f"board/{self.board_config}")

        for mconfig in managed_configs:
            cmd.append("--file")
            cmd.append(mconfig.get_remote_path())

        cmd += chain.from_iterable(("--command", f"{command}") for command in commands)
        processwrapper.check_output(self.interface.wrap_command(cmd), print_on_silent_log=True)

    def _resolve_load_commands(self, filename):
        formatter = Formatter()
        placeholders = []
        for command in self.load_commands:
            for _, field_name, _, _ in formatter.parse(command):
                if field_name and field_name not in placeholders:
                    placeholders.append(field_name)

        if not placeholders:
            return self.load_commands

        if not self.target.env:
            raise ValueError("OpenOCDDriver load command placeholders require an environment configuration")

        filenames = []
        if isinstance(filename, list):
            filenames = filename
            filename = filename[0] if filename else None

        paths = {}
        if "filename" in placeholders:
            if filename is None:
                if self.image is None:
                    raise ValueError("no bootstrap filename provided and no default image configured")
                filename = self.target.env.config.get_image_path(self.image)
            paths["filename"] = filename

        for placeholder in placeholders:
            if placeholder == "filename":
                continue
            if placeholder.startswith("filename") and placeholder[8:].isdigit():
                index = int(placeholder[8:])
                try:
                    paths[placeholder] = filenames[index]
                except IndexError as exc:
                    raise ValueError(f"missing bootstrap filename for placeholder '{placeholder}'") from exc
                continue
            paths[placeholder] = self.target.env.config.get_image_path(placeholder)

        remote_paths = {}
        for placeholder, path in paths.items():
            mf = ManagedFile(path, self.interface)
            mf.sync_to_resource()
            remote_paths[placeholder] = mf.get_remote_path()

        return [command.format(**remote_paths) for command in self.load_commands]

    @Driver.check_active
    @step(args=["filename"])
    def load(self, filename=None):
        if self.load_commands is None:
            if isinstance(filename, list):
                if len(filename) > 1:
                    raise ValueError("OpenOCDDriver default bootstrap sequence supports only a single filename")
                filename = filename[0] if filename else None
            if filename is None and self.image is not None:
                filename = self.target.env.config.get_image_path(self.image)
            mf = ManagedFile(filename, self.interface)
            mf.sync_to_resource()
            commands = [
                "init",
                f"bootstrap {mf.get_remote_path()}",
                "shutdown",
            ]
        else:
            commands = self._resolve_load_commands(filename)

        self._run_commands(commands)

    @Driver.check_active
    @step(args=["commands"])
    def execute(self, commands: list):
        self._run_commands(commands)
