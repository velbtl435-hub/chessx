"""TamagóX mode (master list section 23): agents as Tamagotchi pets. Integration point: attach(agent, pet).
Media activities are pluggable via @hook("name"); see docs/AGENT_FACTORY.md."""
from .pet import Pet, PetStore, attach, act, hook, HOOKS, enable, enabled, REACTIONS
__all__ = ["Pet", "PetStore", "attach", "act", "hook", "HOOKS", "enable", "enabled", "REACTIONS"]
