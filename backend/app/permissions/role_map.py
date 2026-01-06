from .constants import Permission as P
from .roles import SystemRole, ChannelRole

SYSTEM_ROLE_PERMISSIONS: dict[SystemRole, set[P]] = {
    SystemRole.SUPER_ADMIN: {
        P.CREATE_CHANNEL,
        P.ADMIN_PANEL,
        P.MANAGE_USERS,
    },
    SystemRole.ADMIN: {
        P.CREATE_CHANNEL,
        P.ADMIN_PANEL,
    },
    SystemRole.USER: {
        P.CREATE_CHANNEL,
    },
}

CHANNEL_ROLE_PERMISSIONS: dict[ChannelRole, set[P]] = {
    ChannelRole.OWNER: {
        P.SEND_MESSAGE,
        P.READ_MESSAGES,
        P.UPLOAD_FILE,
        P.PIN_MESSAGE,
        P.DELETE_OWN_MESSAGE,
        P.DELETE_ANY_MESSAGE,
        P.MANAGE_CHANNEL,
        P.INVITE_MEMBER,
        P.KICK_MEMBER,
    },
    ChannelRole.MODERATOR: {
        P.SEND_MESSAGE,
        P.READ_MESSAGES,
        P.UPLOAD_FILE,
        P.PIN_MESSAGE,
        P.DELETE_OWN_MESSAGE,
        P.DELETE_ANY_MESSAGE,
        P.INVITE_MEMBER,
        P.KICK_MEMBER,
    },
    ChannelRole.MEMBER: {
        P.SEND_MESSAGE,
        P.READ_MESSAGES,
        P.UPLOAD_FILE,
        P.DELETE_OWN_MESSAGE,
    },
    ChannelRole.GUEST: {
        P.READ_MESSAGES,
    },
}
