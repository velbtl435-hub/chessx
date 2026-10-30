"""ChessX agents: recursive sub-agents, type registry/generator, factory, workspaces, calendar scheduling, TamagóX.
See docs/AGENT_FACTORY.md."""
from .core import Agent, Tree, Limits, AgentLimitError
from .types import AgentType, Registry, Generator
from .factory import Factory, AgentDefinition
__all__ = ["Factory", "AgentDefinition", "Agent", "Tree", "Limits", "AgentLimitError", "AgentType", "Registry", "Generator"]
