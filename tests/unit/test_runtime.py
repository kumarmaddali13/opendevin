"""Test the EventStreamRuntime, which connects to the RuntimeClient running in the sandbox."""

import os
import pathlib
import tempfile
from unittest.mock import patch

import pytest

from opendevin.core.config import AppConfig, SandboxConfig
from opendevin.core.logger import opendevin_logger as logger
from opendevin.events import EventStream
from opendevin.events.action import (
    CmdRunAction,
)
from opendevin.events.observation import (
    CmdOutputObservation,
)
from opendevin.runtime.client.runtime import EventStreamRuntime
from opendevin.runtime.plugins import AgentSkillsRequirement, JupyterRequirement
from opendevin.runtime.server.runtime import ServerRuntime
from opendevin.storage import get_file_store


@pytest.fixture
def temp_dir(monkeypatch):
    # get a temporary directory
    with tempfile.TemporaryDirectory() as temp_dir:
        pathlib.Path().mkdir(parents=True, exist_ok=True)
        yield temp_dir


async def _load_runtime(box_class, event_stream, plugins, sid):
    config = AppConfig(
        sandbox=SandboxConfig(
            use_host_network=False,
        )
    )
    container_image = config.sandbox.container_image
    # NOTE: we will use the default container image specified in the config.sandbox
    # if it is an official od_runtime image.
    if 'od_runtime' not in container_image:
        container_image = 'ubuntu:22.04'
        logger.warning(
            f'`sandbox_config.container_image` is not an od_runtime image. Will use `{container_image}` as the container image for testing.'
        )
    if box_class == EventStreamRuntime:
        runtime = EventStreamRuntime(
            config=config,
            event_stream=event_stream,
            sid=sid,
            # NOTE: we probably don't have a default container image `/sandbox` for the event stream runtime
            # Instead, we will pre-build a suite of container images with OD-runtime-cli installed.
            container_image=container_image,
            plugins=plugins,
        )
        await runtime.ainit()
    elif box_class == ServerRuntime:
        runtime = ServerRuntime(config=config, event_stream=event_stream, sid=sid)
        await runtime.ainit()
        runtime.init_sandbox_plugins(plugins)
        runtime.init_runtime_tools(
            [],
            is_async=False,
            runtime_tools_config={},
        )
    else:
        raise ValueError(f'Invalid box class: {box_class}')
    return runtime


RUNTIME_TO_TEST = [EventStreamRuntime, ServerRuntime]


@pytest.mark.asyncio
async def test_env_vars_os_environ():
    with patch.dict(
        os.environ, {'SANDBOX_ENV_FOOBAR': 'BAZ'}
    ), tempfile.TemporaryDirectory() as temp_dir:
        file_store = get_file_store('local', temp_dir)
        plugins = [JupyterRequirement(), AgentSkillsRequirement()]
        sid = 'test'
        cli_session = 'main_test'

        for box_class in RUNTIME_TO_TEST:
            event_stream = EventStream(cli_session, file_store)
            runtime = await _load_runtime(box_class, event_stream, plugins, sid)

            obs: CmdOutputObservation = await runtime.run_action(
                CmdRunAction(command='env')
            )
            print(obs)

            obs: CmdOutputObservation = await runtime.run_action(
                CmdRunAction(command='echo $FOOBAR')
            )
            print(obs)
            assert obs.exit_code == 0, 'The exit code should be 0.'
            assert (
                obs.content.strip().split('\n\r')[0].strip() == 'BAZ'
            ), f'Output: [{obs.content}] for {box_class}'

            await runtime.close()


@pytest.mark.asyncio
async def test_env_vars_runtime_add_env_vars():
    plugins = [JupyterRequirement(), AgentSkillsRequirement()]
    sid = 'test'
    cli_session = 'main_test'

    with tempfile.TemporaryDirectory() as temp_dir:
        file_store = get_file_store('local', temp_dir)
        for box_class in RUNTIME_TO_TEST:
            event_stream = EventStream(cli_session, file_store)
            runtime = await _load_runtime(box_class, event_stream, plugins, sid)
            await runtime.add_env_vars({'QUUX': 'abc"def'})

            obs: CmdOutputObservation = await runtime.run_action(
                CmdRunAction(command='echo $QUUX')
            )
            print(obs)
            assert obs.exit_code == 0, 'The exit code should be 0.'
            assert (
                obs.content.strip().split('\r\n')[0].strip() == 'abc"def'
            ), f'Output: [{obs.content}] for {box_class}'
            await runtime.close()


@pytest.mark.asyncio
async def test_env_vars_runtime_add_empty_dict():
    plugins = [JupyterRequirement(), AgentSkillsRequirement()]
    sid = 'test'
    cli_session = 'main_test'

    with tempfile.TemporaryDirectory() as temp_dir:
        file_store = get_file_store('local', temp_dir)
        for box_class in RUNTIME_TO_TEST:
            event_stream = EventStream(cli_session, file_store)
            runtime = await _load_runtime(box_class, event_stream, plugins, sid)

            prev_obs = await runtime.run_action(CmdRunAction(command='env'))
            assert prev_obs.exit_code == 0, 'The exit code should be 0.'
            print(prev_obs)

            await runtime.add_env_vars({})

            obs = await runtime.run_action(CmdRunAction(command='env'))
            assert obs.exit_code == 0, 'The exit code should be 0.'
            print(obs)
            assert (
                obs.content == prev_obs.content
            ), 'The env var content should be the same after adding an empty dict.'

            await runtime.close()


@pytest.mark.asyncio
async def test_env_vars_runtime_add_multiple_env_vars():
    plugins = [JupyterRequirement(), AgentSkillsRequirement()]
    sid = 'test'
    cli_session = 'main_test'

    with tempfile.TemporaryDirectory() as temp_dir:
        file_store = get_file_store('local', temp_dir)
        for box_class in RUNTIME_TO_TEST:
            event_stream = EventStream(cli_session, file_store)
            runtime = await _load_runtime(box_class, event_stream, plugins, sid)
            await runtime.add_env_vars({'QUUX': 'abc"def', 'FOOBAR': 'xyz'})

            obs: CmdOutputObservation = await runtime.run_action(
                CmdRunAction(command='echo $QUUX $FOOBAR')
            )
            print(obs)
            assert obs.exit_code == 0, 'The exit code should be 0.'
            assert (
                obs.content.strip().split('\r\n')[0].strip() == 'abc"def xyz'
            ), f'Output: [{obs.content}] for {box_class}'
            await runtime.close()


@pytest.mark.asyncio
async def test_env_vars_runtime_add_env_vars_overwrite():
    plugins = [JupyterRequirement(), AgentSkillsRequirement()]
    sid = 'test'
    cli_session = 'main_test'

    for box_class in RUNTIME_TO_TEST:
        with patch.dict(
            os.environ, {'SANDBOX_ENV_FOOBAR': 'BAZ'}
        ), tempfile.TemporaryDirectory() as temp_dir:
            file_store = get_file_store('local', temp_dir)
            event_stream = EventStream(cli_session, file_store)
            runtime = await _load_runtime(box_class, event_stream, plugins, sid)
            await runtime.add_env_vars({'FOOBAR': 'xyz'})

            obs: CmdOutputObservation = await runtime.run_action(
                CmdRunAction(command='echo $FOOBAR')
            )
            print(obs)
            assert obs.exit_code == 0, 'The exit code should be 0.'
            assert (
                obs.content.strip().split('\r\n')[0].strip() == 'xyz'
            ), f'Output: [{obs.content}] for {box_class}'
            await runtime.close()


@pytest.mark.asyncio
async def test_bash_command_pexcept(temp_dir):
    plugins = [JupyterRequirement(), AgentSkillsRequirement()]
    sid = 'test'
    cli_session = 'main_test'

    with patch.dict(
        os.environ, {'SANDBOX_ENV_FOOBAR': 'BAZ'}
    ), tempfile.TemporaryDirectory() as temp_dir:
        file_store = get_file_store('local', temp_dir)
        box_class = EventStreamRuntime
        event_stream = EventStream(cli_session, file_store)
        runtime = await _load_runtime(box_class, event_stream, plugins, sid)

        # We set env var PS1="\u@\h:\w $"
        # and construct the PEXCEPT prompt base on it.
        # When run `env`, bad implementation of CmdRunAction will be pexcepted by this
        # and failed to pexcept the right content, causing it fail to get error code.
        obs = await runtime.run_action(CmdRunAction(command='env'))

        # For example:
        # 02:16:13 - opendevin:DEBUG: client.py:78 - Executing command: env
        # 02:16:13 - opendevin:DEBUG: client.py:82 - Command output: PYTHONUNBUFFERED=1
        # CONDA_EXE=/opendevin/miniforge3/bin/conda
        # [...]
        # LC_CTYPE=C.UTF-8
        # PS1=\u@\h:\w $
        # 02:16:13 - opendevin:DEBUG: client.py:89 - Executing command for exit code: env
        # 02:16:13 - opendevin:DEBUG: client.py:92 - Exit code Output:
        # CONDA_DEFAULT_ENV=base

        # As long as the exit code is 0, the test will pass.
        assert isinstance(
            obs, CmdOutputObservation
        ), 'The observation should be a CmdOutputObservation.'
        assert obs.exit_code == 0, 'The exit code should be 0.'
