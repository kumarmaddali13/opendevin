import re

from opendevin.controller.action_parser import ActionParser, ResponseParser
from opendevin.events.action import (
    Action,
    AgentDelegateAction,
    AgentFinishAction,
    CmdRunAction,
    IPythonRunCellAction,
    MessageAction,
)
from opendevin.events.action.tasks import PlanStepAction, SavePlanAction


class CodeActPlanningResponseParser(ResponseParser):
    """
    Parser action:
        - CmdRunAction(command) - bash command to run
        - IPythonRunCellAction(code) - IPython code to run
        - AgentDelegateAction(agent, inputs) - delegate action for (sub)task
        - MessageAction(content) - Message action to run (e.g. ask for clarification)
        - AgentFinishAction() - end the interaction
    """

    def __init__(
        self,
    ):
        # Need pay attention to the item order in self.action_parsers
        self.action_parsers = [
            CodeActPlanningActionParserFinish(),
            CodeActPlanningActionParserCmdRun(),
            CodeActPlanningActionParserIPythonRunCell(),
            CodeActPlanningActionParserAgentDelegate(),
            CodeActPlanningActionParserSavePlan(),
            CodeActPlanningActionParserPlanStep(),
        ]
        self.default_parser = CodeActPlanningActionParserMessage()

    def parse(self, response: str) -> Action:
        action_str = self.parse_response(response)
        return self.parse_action(action_str)

    def parse_response(self, response) -> str:
        action = response.choices[0].message.content
        for tag in [
            'execute_bash',
            'execute_ipython',
            'execute_browse',
            'save_plan',
            'plan_step',
        ]:
            if f'<{tag}>' in action and f'</{tag}>' not in action:
                action += f'</{tag}>'
        return action

    def parse_action(self, action_str: str) -> Action:
        for action_parser in self.action_parsers:
            if action_parser.check_condition(action_str):
                return action_parser.parse(action_str)
        return self.default_parser.parse(action_str)


class CodeActPlanningActionParserFinish(ActionParser):
    """
    Parser action:
        - AgentFinishAction() - end the interaction
    """

    def __init__(
        self,
    ):
        self.finish_command = None

    def check_condition(self, action_str: str) -> bool:
        self.finish_command = re.search(r'<finish>.*</finish>', action_str, re.DOTALL)
        return self.finish_command is not None

    def parse(self, action_str: str) -> Action:
        assert (
            self.finish_command is not None
        ), 'self.finish_command should not be None when parse is called'
        thought = action_str.replace(self.finish_command.group(0), '').strip()
        return AgentFinishAction(thought=thought)


class CodeActPlanningActionParserCmdRun(ActionParser):
    """
    Parser action:
        - CmdRunAction(command) - bash command to run
        - AgentFinishAction() - end the interaction
    """

    def __init__(
        self,
    ):
        self.bash_command = None
        self.plan_step = None

    def check_condition(self, action_str: str) -> bool:
        self.bash_command = re.search(
            r'<execute_bash>(.*?)</execute_bash>', action_str, re.DOTALL
        )
        self.plan_step = re.search(
            r'<plan_step>(.*?)</plan_step>', action_str, re.DOTALL
        )
        return self.bash_command is not None

    def parse(self, action_str: str) -> Action:
        assert (
            self.bash_command is not None
        ), 'self.bash_command should not be None when parse is called'
        thought = action_str.replace(self.bash_command.group(0), '').strip()
        # a command was found
        command_group = self.bash_command.group(1).strip()
        if command_group.strip() == 'exit':
            return AgentFinishAction()
        step = None
        if self.plan_step is not None:
            step_group = self.plan_step.group(1).strip()
            thought = thought.replace(self.plan_step.group(0), '').strip()
            step = int(step_group)
        return CmdRunAction(command=command_group, thought=thought, step=step)


class CodeActPlanningActionParserIPythonRunCell(ActionParser):
    """
    Parser action:
        - IPythonRunCellAction(code) - IPython code to run
    """

    def __init__(
        self,
    ):
        self.python_code = None
        self.jupyter_kernel_init_code: str = 'from agentskills import *'
        self.plan_step = None

    def check_condition(self, action_str: str) -> bool:
        self.python_code = re.search(
            r'<execute_ipython>(.*?)</execute_ipython>', action_str, re.DOTALL
        )
        self.plan_step = re.search(
            r'<plan_step>(.*?)</plan_step>', action_str, re.DOTALL
        )
        return self.python_code is not None

    def parse(self, action_str: str) -> Action:
        assert (
            self.python_code is not None
        ), 'self.python_code should not be None when parse is called'
        code_group = self.python_code.group(1).strip()
        thought = action_str.replace(self.python_code.group(0), '').strip()
        step = None
        if self.plan_step is not None:
            step_group = self.plan_step.group(1).strip()
            thought = thought.replace(self.plan_step.group(0), '').strip()
            step = int(step_group)
        return IPythonRunCellAction(
            code=code_group,
            thought=thought,
            kernel_init_code=self.jupyter_kernel_init_code,
            step=step,
        )


class CodeActPlanningActionParserAgentDelegate(ActionParser):
    """
    Parser action:
        - AgentDelegateAction(agent, inputs) - delegate action for (sub)task
    """

    def __init__(
        self,
    ):
        self.agent_delegate = None
        self.plan_step = None

    def check_condition(self, action_str: str) -> bool:
        self.agent_delegate = re.search(
            r'<execute_browse>(.*)</execute_browse>', action_str, re.DOTALL
        )
        self.plan_step = re.search(
            r'<plan_step>(.*?)</plan_step>', action_str, re.DOTALL
        )
        return self.agent_delegate is not None

    def parse(self, action_str: str) -> Action:
        assert (
            self.agent_delegate is not None
        ), 'self.agent_delegate should not be None when parse is called'
        thought = action_str.replace(self.agent_delegate.group(0), '').strip()
        browse_actions = self.agent_delegate.group(1).strip()
        task = f'{thought}. I should start with: {browse_actions}'
        step = None
        if self.plan_step is not None:
            step_group = self.plan_step.group(1).strip()
            thought = thought.replace(self.plan_step.group(0), '').strip()
            step = int(step_group)
        return AgentDelegateAction(
            agent='BrowsingAgent', inputs={'task': task}, step=step
        )


class CodeActPlanningActionParserSavePlan(ActionParser):
    """
    Parser action:
        - SavePlanAction(content) - Plan to save
    """

    def __init__(
        self,
    ):
        self.plan = None

    def check_condition(self, action_str: str) -> bool:
        self.plan = re.search(r'<save_plan>(.*?)</save_plan>', action_str, re.DOTALL)
        return self.plan is not None

    def parse(self, action_str: str) -> Action:
        assert (
            self.plan is not None
        ), 'self.plan should not be None when parse is called'
        plan_group = self.plan.group(1).strip()
        thought = action_str.replace(self.plan.group(0), '').strip()
        steps = plan_group.split('\n')
        return SavePlanAction(
            plan=steps,
            thought=thought,
        )


class CodeActPlanningActionParserPlanStep(ActionParser):
    """
    Parser action:
        - PlanStepAction(content) - How to take a step in a plan
    """

    def __init__(
        self,
    ):
        self.step = None

    def check_condition(self, action_str: str) -> bool:
        self.step = re.search(r'<plan_step>(.*?)</plan_step>', action_str, re.DOTALL)
        return self.step is not None

    def parse(self, action_str: str) -> Action:
        assert (
            self.step is not None
        ), 'self.step should not be None when parse is called'
        step_group = self.step.group(1).strip()
        thought = action_str.replace(self.step.group(0), '').strip()
        step = int(step_group)
        return PlanStepAction(
            step=step,
            thought=thought,
        )


class CodeActPlanningActionParserMessage(ActionParser):
    """
    Parser action:
        - MessageAction(content) - Message action to run (e.g. ask for clarification)
    """

    def __init__(
        self,
    ):
        pass

    def check_condition(self, action_str: str) -> bool:
        # We assume the LLM is GOOD enough that when it returns pure natural language
        # it wants to talk to the user
        return True

    def parse(self, action_str: str) -> Action:
        return MessageAction(content=action_str, wait_for_response=True)
