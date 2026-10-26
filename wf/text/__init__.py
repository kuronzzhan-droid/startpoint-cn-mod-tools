"""Unified character text reads, assertions, local staging and warning audit."""
from .model import TextWorkspace
from .rules import check_character

__all__ = ["TextWorkspace", "check_character"]
