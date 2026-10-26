"""Capability declarations and their data-driven consumers."""
from .registry import load_registry, required_patches, validate_capability

__all__ = ["load_registry", "required_patches", "validate_capability"]
