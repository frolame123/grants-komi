"""Журнал аудита критических операций (п. 4.1.4 ТЗ, FR-015)."""

from sqlalchemy.orm import Session

from app.models import AuditLog


def write_audit(
    db: Session,
    *,
    action: str,
    entity: str,
    entity_id: int | None = None,
    user_id: int | None = None,
    ip: str | None = None,
) -> None:
    """Запись в журнал. Коммит остаётся за вызывающим кодом."""
    db.add(
        AuditLog(
            user_id=user_id,
            action=action,
            entity=entity,
            entity_id=entity_id,
            ip_address=ip,
        )
    )
