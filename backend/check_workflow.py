"""Самопроверка статусной модели заявки (FR-008).

Проверяется то, ради чего конечный автомат и заводится: что запрещённые
переходы действительно запрещены, а не «просто не встречаются в интерфейсе».

Запуск:  python check_workflow.py
"""

from app.workflow import TRANSITIONS, check_transition


def allowed(current: str, target: str, *, archived: bool = False, result=None) -> bool:
    try:
        check_transition(current, target, program_archived=archived, result=result)
    except ValueError:
        return False
    return True


def check_forward_path() -> None:
    """Разрешённый маршрут проходится целиком."""
    assert allowed("DRAFT", "PREP")
    assert allowed("PREP", "SENT")
    assert allowed("SENT", "RES", result="APPROVED")
    assert allowed("SENT", "RES", result="REJECTED")


def check_backward_and_skips() -> None:
    """Обратные и перепрыгивающие переходы запрещены."""
    for current, target in (
        ("PREP", "DRAFT"),
        ("SENT", "PREP"),
        ("RES", "SENT"),
        ("DRAFT", "SENT"),
        ("DRAFT", "RES"),
        ("PREP", "RES"),
        ("DRAFT", "DRAFT"),
    ):
        assert not allowed(current, target, result="APPROVED"), (
            f"переход {current} → {target} не должен быть разрешён"
        )


def check_result_rules() -> None:
    """Результат заполняется тогда и только тогда, когда статус RES."""
    assert not allowed("SENT", "RES"), "переход в RES без результата"
    assert not allowed("SENT", "RES", result="MAYBE"), "недопустимое значение результата"
    assert not allowed("DRAFT", "PREP", result="APPROVED"), "результат вне статуса RES"


def check_terminal_state() -> None:
    """Завершённая заявка не редактируется."""
    assert TRANSITIONS["RES"] == set()
    for target in ("DRAFT", "PREP", "SENT", "RES"):
        assert not allowed("RES", target, result="APPROVED")


def check_archived_program() -> None:
    """У завершённой программы доступно только внесение результата."""
    assert not allowed("DRAFT", "PREP", archived=True)
    assert not allowed("PREP", "SENT", archived=True)
    assert allowed("PREP", "RES", archived=True, result="REJECTED")
    assert allowed("SENT", "RES", archived=True, result="APPROVED")


def main() -> None:
    for check in (
        check_forward_path,
        check_backward_and_skips,
        check_result_rules,
        check_terminal_state,
        check_archived_program,
    ):
        check()
        print(f"OK: {check.__name__}")


if __name__ == "__main__":
    main()
