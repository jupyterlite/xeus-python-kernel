"""a JupyterLite addon for creating the env for xeus-python"""
import os
from subprocess import (
    check_call,
    DEVNULL
)
from tempfile import TemporaryDirectory
import shutil
from pathlib import Path

from traitlets import List

from empack.file_packager import pack_python_core

from jupyterlite.constants import SHARE_LABEXTENSIONS
from jupyterlite.addons.federated_extensions import FederatedExtensionAddon

PYTHON_VERSION = "3.10"

SERVICE = "xeus_python_service.js"

CHANNELS = [
    "https://repo.mamba.pm/emscripten-forge",
    "https://repo.mamba.pm/conda-forge"
]
PLATFORM = "emscripten-32"

SILENT = dict(stdout=DEVNULL, stderr=DEVNULL)

try:
    from mamba.api import create as mamba_create
    MAMBA_PYTHON_AVAILABLE = True
except ImportError:
    MAMBA_PYTHON_AVAILABLE = False

try:
    check_call(["mamba", "--version"], **SILENT)
    MAMBA_AVAILABLE = True
except FileNotFoundError:
    MAMBA_AVAILABLE = False

try:
    check_call(["micromamba", "--version"], **SILENT)
    MICROMAMBA_AVAILABLE = True
except FileNotFoundError:
    MICROMAMBA_AVAILABLE = False

try:
    check_call(["conda", "--version"], **SILENT)
    CONDA_AVAILABLE = True
except FileNotFoundError:
    CONDA_AVAILABLE = False


class PackagesList(List):
    def from_string(self, s):
        return s.split(",")


class XeusPythonEnv(FederatedExtensionAddon):

    __all__ = ["pre_build", "post_build"]

    packages = PackagesList([]).tag(
        config=True,
        description="A comma-separated list of packages to install in the xeus-python env"
    )

    @property
    def specs(self):
        """The package specs to install in the environment."""
        return [f"python={PYTHON_VERSION}", "xeus-python", *self.packages]

    @property
    def prefix_path(self):
        """The environment prefix."""
        return Path(self.root_prefix) / "envs" / self.env_name

    def __init__(self, *args, **kwargs):
        super(XeusPythonEnv, self).__init__(*args, **kwargs)

        self.cwd = TemporaryDirectory()
        self.root_prefix = "/tmp/xeus-python-kernel"
        self.env_name = "xeus-python-kernel"

        # Cleanup tmp dir in case it's not empty
        shutil.rmtree(self.root_prefix, ignore_errors=True)
        Path(self.root_prefix).mkdir(parents=True, exist_ok=True)

        self.orig_config = os.environ.get("CONDARC")

    def pre_build(self, manager):
        """yield a doit task to create the emscripten-32 env and grab anything we need from it"""
        yield dict(
            name="setup-service-worker",
            actions=[(self.copy_one, [Path(__file__).parent / SERVICE, Path(self.manager.output_dir) / SERVICE])],
        )

        # Bail early if there is nothing to do
        if not self.packages:
            return

        # Create emscripten env with the given packages
        self.create_env()

        # Pack the environment
        pack_python_core(
            self.prefix_path,
            outname=Path(self.cwd.name) / "python_data",
            version=PYTHON_VERSION,
            export_name="globalThis.Module",
        )

        # Find the federated extensions in the emscripten-env and install them
        root = self.prefix_path / SHARE_LABEXTENSIONS

        if not self.is_sys_prefix_ignored():
            for pkg_json in self.env_extensions(root):
                yield from self.copy_one_extension(pkg_json)

        # TODO Currently we're shamelessly overwriting the
        # python_data.{js,data} into the labextension.
        # We should really find a nicer way.
        # (make jupyterlite-xeus-python extension somewhat configurable?)
        dest = self.output_extensions / "@jupyterlite" / "xeus-python-kernel" / "static"

        task_dep = ["pre_build:federated_extensions:*"]

        for file in ["python_data.js", "python_data.data"]:
            yield dict(
                task_dep=task_dep,
                name=f"copy:{file}",
                actions=[(self.copy_one, [Path(self.cwd.name) / file, dest / file])],
            )

        for file in ["xpython_wasm.js", "xpython_wasm.wasm"]:
            yield dict(
                task_dep=task_dep,
                name=f"copy:{file}",
                actions=[
                    (
                        self.copy_one,
                        [
                            self.prefix_path / "bin" / file,
                            dest / file,
                        ],
                    )
                ],
            )

    def create_env(self):
        """Create the xeus-python emscripten-32 env with either mamba, micromamba or conda."""
        if MAMBA_PYTHON_AVAILABLE:
            mamba_create(
                env_name=self.env_name,
                base_prefix=self.root_prefix,
                specs=self.specs,
                channels=CHANNELS,
                target_platform=PLATFORM
            )
            return

        channels = []
        for channel in CHANNELS:
            channels.extend(["-c", channel])

        if MAMBA_AVAILABLE:
            # Mamba needs the directory to exist already
            self.prefix_path.mkdir(parents=True, exist_ok=True)
            return self._create_env_with_config("mamba", channels)

        if MICROMAMBA_AVAILABLE:
            check_call(
                [
                    "micromamba",
                    "create",
                    "--yes",
                    "--root-prefix",
                    self.root_prefix,
                    "--name",
                    self.env_name,
                    f"--platform={PLATFORM}",
                    *channels,
                    *self.specs,
                ],
                cwd=self.cwd.name,
            )
            return

        if CONDA_AVAILABLE:
            return self._create_env_with_config("conda", channels)

        raise RuntimeError(
            """Failed to create the virtual environment for xeus-python,
            please make sure at least mamba, micromamba or conda is installed.
            """
        )

    def _create_env_with_config(self, conda, channels):
        check_call(
            [
                conda,
                "create",
                "--prefix",
                self.prefix_path,
                *channels
            ],
            cwd=self.cwd.name,
        )
        self._create_config()
        check_call(
            [
                conda,
                "install",
                "--prefix",
                self.prefix_path,
                *channels,
                *self.specs,
            ],
            cwd=self.cwd.name,
        )

    def _create_config(self):
        with open(self.prefix_path / ".condarc", "w") as fobj:
            fobj.write(f"subdir: {PLATFORM}")
        os.environ["CONDARC"] = str(self.prefix_path / ".condarc")

    def post_build(self, manager):
        """Cleanup"""
        # Bail early if there is nothing to do
        if not self.packages:
            return []

        shutil.rmtree(self.cwd.name, ignore_errors=True)
        shutil.rmtree(self.root_prefix, ignore_errors=True)

        if self.orig_config is not None:
            os.environ["CONDARC"] = self.orig_config
        elif "CONDARC" in os.environ:
            del os.environ["CONDARC"]

        return []
