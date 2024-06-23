from opendevin.controller.agent import Agent

from .codeact_planning_agent import CodeActPlanningAgent

Agent.register('CodeActPlanningAgent', CodeActPlanningAgent)
