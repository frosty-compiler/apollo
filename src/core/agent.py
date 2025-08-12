import logging


class BaseAgent:
    """
    Base class for all Apollo agents with common functionality.

    This provides common agent functionality without requiring separate ABC interfaces.
    Each agent type implements its specific methods (research, generate_outline, etc.)
    directly.
    """

    def __init__(self, name: str, role: str, lm=None):
        """
        Initialize agent with basic properties.

        Args:
            name: Agent's identifier
            role: Agent's role (curator, architect, writer, etc.)
            lm: Language model for this agent
        """
        self.name = name
        self.role = role
        self.lm = lm
        self.logger = logging.getLogger(f"apollo.agent.{role}")

    def log(self, message: str, level: str = "info"):
        """Log a message with agent context."""
        log_method = getattr(self.logger, level.lower())
        log_method(f"[{self.name}] {message}")

    def __str__(self):
        """String representation of the agent."""
        return f"{self.role} agent: {self.name}"
