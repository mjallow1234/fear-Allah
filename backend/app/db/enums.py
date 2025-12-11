import enum


class UserStatus(str, enum.Enum):
    online = "online"
    away = "away"
    dnd = "dnd"
    offline = "offline"


class UserRole(str, enum.Enum):
    system_admin = "system_admin"
    team_admin = "team_admin"
    member = "member"
    guest = "guest"


class ChannelType(str, enum.Enum):
    public = "public"
    private = "private"
    direct = "direct"


class NotificationType(str, enum.Enum):
    mention = "mention"
    reply = "reply"
    dm = "dm"
    reaction = "reaction"
