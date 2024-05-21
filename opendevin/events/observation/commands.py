from dataclasses import dataclass, fields

from opendevin.core.schema import ObservationType

from .observation import Observation


@dataclass
class CmdOutputObservation(Observation):
    """
    This data class represents the output of a command.
    """

    command_id: int
    command: str
    exit_code: int = 0
    observation: str = ObservationType.RUN

    @property
    def error(self) -> bool:
        return self.exit_code != 0

    @property
    def message(self) -> str:
        return f'Command `{self.command}` executed with exit code {self.exit_code}.'

    def __str__(self) -> str:
        return f'**CmdOutputObservation (exit code={self.exit_code})**\n{self.content}'

    def __eq__(self, other: object) -> bool:
        print('CmdOutputObservation.__eq__')
        if Observation.is_ignoring_command_id():
            return all(
                getattr(self, f.name) == getattr(other, f.name)
                for f in fields(self)
                if f.name != 'command_id'
            )
        print(super().__eq__(other))
        return super().__eq__(other)


@dataclass
class IPythonRunCellObservation(Observation):
    """
    This data class represents the output of a IPythonRunCellAction.
    """

    code: str
    observation: str = ObservationType.RUN_IPYTHON

    @property
    def error(self) -> bool:
        return False  # IPython cells do not return exit codes

    @property
    def message(self) -> str:
        return 'Code executed in IPython cell.'

    def __str__(self) -> str:
        return f'**IPythonRunCellObservation**\n{self.content}'
