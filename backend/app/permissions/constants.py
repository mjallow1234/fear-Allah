from enum import Enum


class Permission(str, Enum):
    # Channel-scoped
    SEND_MESSAGE = "send_message"
    READ_MESSAGES = "read_messages"
    UPLOAD_FILE = "upload_file"
    PIN_MESSAGE = "pin_message"
    DELETE_OWN_MESSAGE = "delete_own_message"
    DELETE_ANY_MESSAGE = "delete_any_message"
    MANAGE_CHANNEL = "manage_channel"
    INVITE_MEMBER = "invite_member"
    KICK_MEMBER = "kick_member"

    # System-scoped
    CREATE_CHANNEL = "create_channel"
    ADMIN_PANEL = "admin_panel"
    MANAGE_USERS = "manage_users"
