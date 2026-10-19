"""Pydantic models describing every structured response the AI may return.

These models serve two purposes:

* They are sent to the OpenAI API as the structured-output JSON schema.
* They validate the response before anything is displayed or stored.

Validators are written as Pydantic ``AfterValidator`` / ``model_validator``
hooks so they run locally without adding JSON-schema keywords the API might not
support. Passing validation means the response is *well-formed*, not that its
Japanese is guaranteed to be correct.
"""
