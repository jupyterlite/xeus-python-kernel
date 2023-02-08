import os
from copy import copy
from pathlib import Path
import requests
import shutil
from subprocess import check_call, run, DEVNULL
from typing import List
from urllib.parse import urlparse

import yaml

from empack.file_packager import split_pack_environment
from empack.file_patterns import PkgFileFilter, pkg_file_filter_from_yaml

import typer

try:
    from mamba.api import create as mamba_create

    MAMBA_PYTHON_AVAILABLE = True
except ImportError as e:
    print(f"cannot import mamba because {e}")
    MAMBA_PYTHON_AVAILABLE = False

MAMBA_COMMAND = shutil.which("mamba")
MICROMAMBA_COMMAND = shutil.which("micromamba")

CONDA_COMMAND = shutil.which("conda")

import sys
print(f"WHICH PY? {shutil.which('python')}  {sys.executable}")

PYTHON_VERSION = "3.10"

CHANNELS = [
    "/Users/thorstenbeier/micromamba/envs/emf/conda-bld",
    "https://repo.mamba.pm/emscripten-forge",
    "https://repo.mamba.pm/conda-forge",
]

PLATFORM = "emscripten-32"


def create_env(
    env_name,
    root_prefix,
    specs,
    channels,
):
    """Create the emscripten environment with the given specs."""
    prefix_path = Path(root_prefix) / "envs" / env_name

    if True and MAMBA_PYTHON_AVAILABLE:
        mamba_create(
            env_name=env_name,
            base_prefix=root_prefix,
            specs=specs,
            channels=channels,
            target_platform=PLATFORM,
        )
        return

    channels_args = []
    for channel in channels:
        channels_args.extend(["-c", channel])

    if True and  MAMBA_COMMAND:
        # Mamba needs the directory to exist already
        prefix_path.mkdir(parents=True, exist_ok=True)
        return _create_env_with_config(MAMBA_COMMAND, prefix_path, specs, channels_args)

    if MICROMAMBA_COMMAND:
        run(
            [
                MICROMAMBA_COMMAND,
                "create",
                "--yes",
                "--root-prefix",
                root_prefix,
                "--name",
                env_name,
                f"--platform={PLATFORM}",
                *channels_args,
                *specs,
            ],
            check=True,
        )
        return

    if CONDA_COMMAND:
        return _create_env_with_config(CONDA_COMMAND, prefix_path, specs, channels_args)

    raise RuntimeError(
        """Failed to create the virtual environment for xeus-python,
        please make sure at least mamba, micromamba or conda is installed.
        """
    )


def _create_env_with_config(conda, prefix_path, specs, channels_args):
    run(
        [conda, "create", "--yes", "--prefix", prefix_path, *channels_args],
        check=True,
    )
    _create_config(prefix_path)
    run(
        [
            conda,
            "install",
            "--yes",
            "--prefix",
            prefix_path,
            *channels_args,
            *specs,
        ],
        check=True,
    )


def _create_config(prefix_path):
    with open(prefix_path / ".condarc", "w") as fobj:
        fobj.write(f"subdir: {PLATFORM}")
    os.environ["CONDARC"] = str(prefix_path / ".condarc")


def build_and_pack_emscripten_env(
    python_version: str = PYTHON_VERSION,
    xeus_python_version: str = "",
    packages: List[str] = [],
    environment_file: str = "",
    root_prefix: str = "/tmp/xeus-python-kernel",
    env_name: str = "xeus-python-kernel",
    empack_config: str = "",
    output_path: str = ".",
    build_worker: bool = False,
    force: bool = False,
):
    """Build a conda environment for the emscripten platform and pack it with empack."""
    channels = copy(CHANNELS)
    specs = [
        f"python={python_version}",
        "xeus-lite",
        "xeus-python"
        if not xeus_python_version
        else f"xeus-python={xeus_python_version}",
        *packages,
    ]
    bail_early = True

    if packages or xeus_python_version or environment_file:
        bail_early = False

    # Process environment.yml file
    if environment_file and Path(environment_file).exists():
        bail_early = False

        with open(Path(environment_file)) as f:
            env_data = yaml.safe_load(f)

        if env_data.get("name") is not None:
            env_name = env_data["name"]

        if env_data.get("channels") is not None:
            channels.extend(
                [channel for channel in env_data["channels"] if channel not in CHANNELS]
            )

        if env_data.get("dependencies") is not None:
            dependencies = env_data["dependencies"]

            for dependency in dependencies:
                if isinstance(dependency, str) and dependency not in specs:
                    specs.append(dependency)
                elif isinstance(dependency, dict) and dependency.get("pip") is not None:
                    raise RuntimeError(
                        """Cannot install pip dependencies in the xeus-python Emscripten environment (yet?).
                        """
                    )

    # Bail early if there is nothing to do
    if bail_early and not force:
        return []

    orig_config = os.environ.get("CONDARC")

    # Cleanup tmp dir in case it's not empty
    shutil.rmtree(Path(root_prefix) / "envs", ignore_errors=True)
    Path(root_prefix).mkdir(parents=True, exist_ok=True)

    output_path = Path(output_path).resolve()
    output_path.mkdir(parents=True, exist_ok=True)

    prefix_path = Path(root_prefix) / "envs" / env_name

    try:
        # Create emscripten env with the given packages
        create_env(env_name, root_prefix, specs, channels)

        pack_kwargs = {}

        # Download env filter config
        if empack_config:
            empack_config_is_url = urlparse(empack_config).scheme in ("http", "https")
            if empack_config_is_url:
                empack_config_content = requests.get(empack_config).content
                pack_kwargs["pkg_file_filter"] = PkgFileFilter.parse_obj(
                    yaml.safe_load(empack_config_content)
                )
            else:
                pack_kwargs["pkg_file_filter"] = pkg_file_filter_from_yaml(
                    empack_config
                )

        # Pack the environment
        split_pack_environment(
            env_prefix=prefix_path,
            outname="python_data",
            pack_outdir=output_path,
            export_name="globalThis.Module",
            with_export_default_statement=False,
            #**pack_kwargs,
        )

        # Copy xeus-python output
        for file in ["xpython_wasm.js", "xpython_wasm.wasm"]:
            shutil.copyfile(prefix_path / "bin" / file, Path(output_path) / file)

        # Copy worker code and process it
        print("build_worker",build_worker)
        if build_worker or True:
            shutil.copytree(
                prefix_path / "share" / "xeus-lite",
                Path(output_path),
                dirs_exist_ok=True,
            )




            worker = """
// Copyright (c) Thorsten Beier
// Copyright (c) JupyterLite Contributors
// Distributed under the terms of the Modified BSD License.

import { expose } from 'comlink';

import {
  DriveFS,
  DriveFSEmscriptenNodeOps,
  IEmscriptenFSNode,
  IStats
} from '@jupyterlite/contents';

declare function createXeusModule(options: any): any;

globalThis.Module = {};

const WASM_KERNEL_FILE = XEUS_KERNEL_FILE;
const DATA_FILE = LANGUAGE_DATA_FILE;

// TODO Remove this. This is to ensure we always perform node ops on Nodes and
// not Streams, but why is it needed??? Why do we get Streams and not Nodes from
// emscripten in the case of xeus-python???
class StreamNodeOps extends DriveFSEmscriptenNodeOps {
  private getNode(nodeOrStream: any) {
    if (nodeOrStream['node']) {
      return nodeOrStream['node'];
    }
    return nodeOrStream;
  }

  lookup(parent: IEmscriptenFSNode, name: string): IEmscriptenFSNode {
    return super.lookup(this.getNode(parent), name);
  }

  getattr(node: IEmscriptenFSNode): IStats {
    return super.getattr(this.getNode(node));
  }

  setattr(node: IEmscriptenFSNode, attr: IStats): void {
    super.setattr(this.getNode(node), attr);
  }

  mknod(
    parent: IEmscriptenFSNode,
    name: string,
    mode: number,
    dev: any
  ): IEmscriptenFSNode {
    return super.mknod(this.getNode(parent), name, mode, dev);
  }

  rename(
    oldNode: IEmscriptenFSNode,
    newDir: IEmscriptenFSNode,
    newName: string
  ): void {
    super.rename(this.getNode(oldNode), this.getNode(newDir), newName);
  }

  rmdir(parent: IEmscriptenFSNode, name: string): void {
    super.rmdir(this.getNode(parent), name);
  }

  readdir(node: IEmscriptenFSNode): string[] {
    return super.readdir(this.getNode(node));
  }
}

// TODO Remove this when we don't need StreamNodeOps anymore
class LoggingDrive extends DriveFS {
  constructor(options: DriveFS.IOptions) {
    super(options);

    this.node_ops = new StreamNodeOps(this);
  }
}

// when a toplevel cell uses an await, the cell is implicitly
// wrapped in a async function. Since the webloop - eventloop
// implementation does not support `eventloop.run_until_complete(f)`
// we need to convert the toplevel future in a javascript Promise
// this `toplevel` promise is then awaited before we
// execute the next cell. After the promise is awaited we need
// to do some cleanup and delete the python proxy
// (ie a js-wrapped python object) to avoid memory leaks
globalThis.toplevel_promise = null;
globalThis.toplevel_promise_py_proxy = null;

let resolveInputReply: any;

async function get_stdin() {
  const replyPromise = new Promise(resolve => {
    resolveInputReply = resolve;
  });
  return replyPromise;
}

(self as any).get_stdin = get_stdin;

class XeusKernel {
  constructor() {
    this._ready = new Promise(resolve => {
      this.initialize(resolve);
    });
  }

  async ready(): Promise<void> {
    return await this._ready;
  }

  mount(driveName: string, mountpoint: string, baseUrl: string): void {
    const { FS, PATH, ERRNO_CODES } = globalThis.Module;

    if (!FS) {
      return;
    }

    this._drive = new LoggingDrive({
      FS,
      PATH,
      ERRNO_CODES,
      baseUrl,
      driveName,
      mountpoint
    });

    FS.mkdir(mountpoint);
    FS.mount(this._drive, {}, mountpoint);
    FS.chdir(mountpoint);
  }

  cd(path: string) {
    if (!path || !globalThis.Module.FS) {
      return;
    }

    globalThis.Module.FS.chdir(path);
  }

  async processMessage(event: any): Promise<void> {
    await this._ready;

    if (
      globalThis.toplevel_promise !== null &&
      globalThis.toplevel_promise_py_proxy !== null
    ) {
      await globalThis.toplevel_promise;
      globalThis.toplevel_promise_py_proxy.delete();
      globalThis.toplevel_promise_py_proxy = null;
      globalThis.toplevel_promise = null;
    }

    const msg_type = event.msg.header.msg_type;

    if (msg_type === 'input_reply') {
      resolveInputReply(event.msg);
    } else {
      this._raw_xserver.notify_listener(event.msg);
    }
  }

  private async initialize(resolve: () => void) {
    importScripts(WASM_KERNEL_FILE);

    globalThis.Module = await createXeusModule({});

    if (DATA_FILE.length !== 0) {
      importScripts(DATA_FILE);
      await this.waitRunDependency();
    }

    try{
        console.log("construct kernel");
        this._raw_xkernel = new globalThis.Module.xkernel();
    }
    catch(error){
        console.error("error while constructing",error);
    }
    try{
        this._raw_xserver = this._raw_xkernel.get_server();
    }
    catch(error){
        console.error("err while get server", error);
    }
    if (!this._raw_xkernel) {
      console.error('Failed to start kernel!');
    }
    try{
        this._raw_xkernel.start();
    }
    catch(error){
        console.error("err while starting", error);
    }
    resolve();
  }

  private async waitRunDependency() {
    const promise = new Promise<void>(resolve => {
      globalThis.Module.monitorRunDependencies = (n: number) => {
        if (n === 0) {
          resolve();
        }
      };
    });
    // If there are no pending dependencies left, monitorRunDependencies will
    // never be called. Since we can't check the number of dependencies,
    // manually trigger a call.
    globalThis.Module.addRunDependency('dummy');
    globalThis.Module.removeRunDependency('dummy');
    return promise;
  }

  private _raw_xkernel: any;
  private _raw_xserver: any;
  private _drive: DriveFS | null = null;
  private _ready: PromiseLike<void>;
}

expose(new XeusKernel());
            """












            if False:
                with open(Path(output_path) / "worker.ts", "r") as fobj:
                    worker = fobj.read()
            worker = worker.replace("declare function createXeusModule(options: any): any;",
"""
globalThis.importPackages = {}
declare function createXeusModule(options: any): any;
declare function loadPackages(): any;
""")
            worker = worker.replace("XEUS_KERNEL_FILE", "'xpython_wasm.js'")
            worker = worker.replace("LANGUAGE_DATA_FILE", "'python_data.js'")

            new_worker_content = """
                importScripts(DATA_FILE);
                try{
                    console.log("import packages")
                    await globalThis.Module.importPackages();
                    console.log("import packages DONE")
                }
                catch(error){
                    console.error("err while importing pkgs", error)
                }
                try{
                    console.log("try init")
                    await globalThis.Module.init();
                    console.log("init done")
                }
                catch(error){
                    console.error("err while init", error)
                }
            """ 


            worker = worker.replace("importScripts(DATA_FILE);", new_worker_content)
            print(worker)
            with open(Path(output_path) / "worker.ts", "w") as fobj:
                fobj.write(worker)
    except Exception as e:
        raise e
    finally:
        if orig_config is not None:
            os.environ["CONDARC"] = orig_config
        elif "CONDARC" in os.environ:
            del os.environ["CONDARC"]

    return prefix_path


def main(
    python_version: str = PYTHON_VERSION,
    xeus_python_version: str = "",
    packages: List[str] = typer.Option(
        [], help="The list of packages you want to install"
    ),
    environment_file: str = typer.Option(
        "", help="The path to the environment.yml file you want to use"
    ),
    root_prefix: str = "/tmp/xeus-python-kernel",
    env_name: str = "xeus-python-kernel",
    empack_config: str = typer.Option(
        "",
        help="The empack config file to use. If not provided, the default empack config will be used",
    ),
    output_path: str = typer.Option(
        ".",
        help="The directory where to output the packed environment",
    ),
    build_worker: bool = typer.Option(
        False,
        help="Whether or not to build the TypeScript worker code for using xeus-python in JupyterLite",
    ),
):
    """Build and pack an emscripten environment."""
    return build_and_pack_emscripten_env(
        python_version,
        xeus_python_version,
        packages,
        environment_file,
        root_prefix,
        env_name,
        empack_config,
        output_path,
        build_worker,
        force=True,
    )


def start():
    typer.run(main)


if __name__ == "__main__":
    start()
