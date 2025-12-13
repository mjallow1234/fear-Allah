"""Compatibility shim for chat models.

This module re-exports the chat-related ORM models from `app.db.models` so
other packages can import `app.models.chat` as requested by scaffolding.
"""
from app.db.models import Channel, ChannelMember, Message, Notification

__all__ = ["Channel", "ChannelMember", "Message", "Notification"]
