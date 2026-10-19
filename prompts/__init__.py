"""Prompt templates, one module per feature.

Each module exposes a ``build_*`` function returning a :class:`prompts.base.PromptSpec`.
Templates contain no API logic; the AI service sends whatever spec it is given.
"""
