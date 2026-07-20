"""
六智Agent模块 - Agent注册中心
"""
from agents.base import BaseAgent
from agents.agent1_parser import Agent1Parser
from agents.agent2_searcher import Agent2Searcher
from agents.agent3_checker import Agent3Checker
from agents.agent4_reader import Agent4Reader
from agents.agent5_suggester import Agent5Suggester
from agents.agent6_integrator import Agent6Integrator


def create_agent(agent_id, config):
    """根据agent_id创建对应的Agent实例"""
    agent_classes = {
        "agent1": Agent1Parser,
        "agent2": Agent2Searcher,
        "agent3": Agent3Checker,
        "agent4": Agent4Reader,
        "agent5": Agent5Suggester,
        "agent6": Agent6Integrator,
    }
    cls = agent_classes.get(agent_id)
    if not cls:
        raise ValueError(f"Unknown agent_id: {agent_id}")
    return cls(config)


__all__ = ["BaseAgent", "create_agent"]
