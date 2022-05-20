# -*- coding: utf-8 -*-

import os

raise RuntimeError(f"prefix {os.environ.get('PREFIX')},conda_prefix {os.environ.get('CONDA_PREFIX')} ")

# This should not be there... We should probably
# do this in jupyterlite-xeus-python instead
from subprocess import check_call
check_call(["emsdk", "install", "3.1.2"])
check_call(["emsdk", "activate", "3.1.2"])

extensions = [
    'jupyterlite_sphinx'
]

master_doc = 'index'
source_suffix = '.rst'

project = 'xeus-python-kernel'
copyright = 'JupyterLite Team'
author = 'JupyterLite Team'

exclude_patterns = []

html_theme = "pydata_sphinx_theme"

jupyterlite_config = "jupyterlite_config.json"
