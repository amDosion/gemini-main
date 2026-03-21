"""
Starter templates package.

- templates/: one JSON file per starter template
- loader.py: load & validate template definitions
"""

from .loader import load_starter_template_definitions

__all__ = ["load_starter_template_definitions"]

