"""Business logic for each learning feature.

Functions here validate input, build prompts, call the AI service, check the
results, and talk to the repository. They never import Streamlit, so they can be
unit-tested in isolation and reused by a different front end.
"""
