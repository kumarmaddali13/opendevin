import os
from dataclasses import dataclass
from opendevin.sandbox.plugins.requirement import PluginRequirement


@dataclass
class SSHRequirement(PluginRequirement):
    name: str = 'ssh'
    host_src: str = os.path.dirname(os.path.abspath(__file__))  # The directory of this file (sandbox/plugins/jupyter)
    sandbox_dest: str = '/opendevin/plugins/ssh'
    bash_script_path: str = 'setup.sh'
