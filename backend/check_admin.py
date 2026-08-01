"""Самопроверка правил администрирования пользователей (FR-012).

Главное, что здесь проверяется, — защита администратора от самого себя и
определение понижения роли, от которого зависит отзыв выданных токенов.

Запуск:  python check_admin.py
"""

from app.rbac import (
    ASSIGNABLE_ROLES,
    ROLE_NAMES,
    check_role_change,
    check_status_change,
    is_downgrade,
)

ADMIN = 1
OTHER = 2


def allowed(func, *args) -> bool:
    try:
        func(*args)
    except ValueError:
        return False
    return True


def check_assignable_roles() -> None:
    """Роль guest не назначается: она означает отсутствие учётной записи."""
    assert "guest" not in ASSIGNABLE_ROLES
    assert set(ASSIGNABLE_ROLES) == {"applicant", "moderator", "admin"}
    assert all(role in ROLE_NAMES for role in ASSIGNABLE_ROLES), "у каждой роли есть название"


def check_role_rules() -> None:
    for role in ASSIGNABLE_ROLES:
        assert allowed(check_role_change, ADMIN, OTHER, role), f"роль {role} должна назначаться"

    assert not allowed(check_role_change, ADMIN, ADMIN, "applicant"), (
        "администратор не может изменить собственную роль"
    )
    assert not allowed(check_role_change, ADMIN, OTHER, "guest"), "guest не назначается"
    assert not allowed(check_role_change, ADMIN, OTHER, "superuser"), "выдуманная роль"


def check_status_rules() -> None:
    assert allowed(check_status_change, ADMIN, OTHER, "blocked")
    assert allowed(check_status_change, ADMIN, OTHER, "active")

    assert not allowed(check_status_change, ADMIN, ADMIN, "blocked"), (
        "администратор не может заблокировать сам себя"
    )
    assert not allowed(check_status_change, ADMIN, OTHER, "pending"), (
        "статус подтверждения ставится системой, а не администратором"
    )


def check_downgrade_detection() -> None:
    """Понижение прав определяется верно — от этого зависит отзыв токенов."""
    assert is_downgrade("admin", "moderator")
    assert is_downgrade("admin", "applicant")
    assert is_downgrade("moderator", "applicant")

    assert not is_downgrade("applicant", "moderator")
    assert not is_downgrade("moderator", "admin")
    assert not is_downgrade("admin", "admin"), "роль не изменилась — не понижение"


def main() -> None:
    for check in (
        check_assignable_roles,
        check_role_rules,
        check_status_rules,
        check_downgrade_detection,
    ):
        check()
        print(f"OK: {check.__name__}")


if __name__ == "__main__":
    main()
