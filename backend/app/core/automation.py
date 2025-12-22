import logging
from functools import wraps
from typing import Callable, Any
from app.core.config import settings, logger

log = logging.getLogger('fear-allah.automation')

def run_if_automations_enabled(fn: Callable) -> Callable:
    """Decorator to skip execution unless automations are enabled.

    Logs and returns None when automations are disabled.
    """
    @wraps(fn)
    async def wrapper(*args, **kwargs) -> Any:
        if not settings.AUTOMATIONS_ENABLED:
            log.info('Automations disabled — skipping %s', fn.__name__)
            return None
        return await fn(*args, **kwargs)
    return wrapper

# Synchronous variant for simple hooks
def run_if_automations_enabled_sync(fn: Callable) -> Callable:
    @wraps(fn)
    def wrapper(*args, **kwargs) -> Any:
        if not settings.AUTOMATIONS_ENABLED:
            log.info('Automations disabled — skipping %s', fn.__name__)
            return None
        return fn(*args, **kwargs)
    return wrapper
