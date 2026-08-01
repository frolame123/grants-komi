"""Ролевая модель и правила изменения ролей (FR-012, п. 4.1.4 ТЗ).

Роль guest в перечень назначаемых не входит: это роль неаутентифицированного
посетителя, она не хранится за учётной записью, а означает её отсутствие.

Ключевое ограничение — администратор не может изменить собственную роль или
заблокировать себя. Иначе единственный администратор системы способен
случайно лишить себя прав, после чего восстановить доступ можно только
правкой базы вручную.
"""

ASSIGNABLE_ROLES = ("applicant", "moderator", "admin")
STATUSES = ("pending", "active", "blocked")

ROLE_NAMES = {
    "guest": "Гость",
    "applicant": "Заявитель",
    "moderator": "Контент-менеджер",
    "admin": "Администратор",
}

STATUS_NAMES = {
    "pending": "Не подтверждён",
    "active": "Активен",
    "blocked": "Заблокирован",
}

# Понижением считается любой переход к роли с меньшими правами: выданные
# токены доступа при этом отзываются, чтобы права не «доживали» до истечения
ROLE_LEVEL = {"applicant": 1, "moderator": 2, "admin": 3}


def check_role_change(actor_id: int, target_id: int, new_role: str) -> None:
    """Проверка назначения роли. Возбуждает ValueError с текстом для ответа."""
    if new_role not in ASSIGNABLE_ROLES:
        allowed = ", ".join(ASSIGNABLE_ROLES)
        raise ValueError(f"Недопустимая роль; разрешены: {allowed}")
    if actor_id == target_id:
        raise ValueError("Администратор не может изменить собственную роль")


def check_status_change(actor_id: int, target_id: int, new_status: str) -> None:
    """Проверка блокировки и разблокировки учётной записи."""
    if new_status not in ("active", "blocked"):
        raise ValueError("Допустимые значения статуса: active, blocked")
    if actor_id == target_id:
        raise ValueError("Администратор не может заблокировать сам себя")


def is_downgrade(old_role: str, new_role: str) -> bool:
    """Понижение прав: требует немедленного отзыва выданных токенов."""
    return ROLE_LEVEL.get(new_role, 0) < ROLE_LEVEL.get(old_role, 0)
