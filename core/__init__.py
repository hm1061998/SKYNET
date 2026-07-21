"""Skill Agent — core package."""
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = PROJECT_ROOT / "skills"
PLANS_DIR = PROJECT_ROOT / "plans"
MEMORY_DIR = PROJECT_ROOT / "memory"
CONFIG_PATH = PROJECT_ROOT / "config.json"

__all__ = ["PROJECT_ROOT", "SKILLS_DIR", "PLANS_DIR", "MEMORY_DIR", "CONFIG_PATH"]
