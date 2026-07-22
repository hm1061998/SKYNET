"""Adapters isolating legacy runtime contracts."""
from .legacy import LegacyInvocationAdapter, LegacyInvocationProjection, LegacyMemoryAdapter
from .migration import LegacyMemoryMigrator, MemoryMigrationReport
from .runtime import RuntimeFeatureFlags

__all__ = ["LegacyInvocationAdapter", "LegacyInvocationProjection", "LegacyMemoryAdapter",
           "LegacyMemoryMigrator", "MemoryMigrationReport", "RuntimeFeatureFlags"]
