"""Multi-agent role runtime foundation."""
from .capabilities import CapabilityError, CapabilityResolver
from .definitions import AgentDefinitionError, AgentRegistry
from .factory import AgentFactory
from .lifecycle import AgentLifecycleManager, LIFECYCLE_TRANSITIONS
from .prompting import AgentContext, PromptAssembler
from .providers import AgentCompletionProvider, LegacyProviderAdapter
from .routing import LOGICAL_PROFILE_NAMES, ModelRouter, RoutedModelProfile
from .runtime import AgentExecutionResult, AgentRuntime, ResultStatus, RuntimeOutcome

__all__ = [name for name in globals() if not name.startswith("_")]
