"""
Centralized identity resolution for human-readable display names.

ALL systems that need to show a sender/author name MUST use these helpers.
Never construct inline "user_N" fallback strings for user-visible output.
"""


def resolve_display_name(user) -> str:
    """
    Resolve best human-readable identity for a user ORM object or dict.

    Priority: display_name > username > full_name > "Unknown"

    Never returns "user_N" format for human-visible contexts.
    """
    if user is None:
        return "Unknown"

    return (
        (getattr(user, "display_name", None) or "").strip()
        or (getattr(user, "username", None) or "").strip()
        or (getattr(user, "full_name", None) or "").strip()
        or "Unknown"
    )
