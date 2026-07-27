"""Статусная модель заявки — конечный автомат (FR-008).

Разрешены только переходы вперёд и по одному шагу:

    DRAFT ──▶ PREP ──▶ SENT ──▶ RES
   черновик  готовлю   подана  результат

Обратные и «перепрыгивающие» переходы запрещены: заявка не может из
черновика сразу стать поданной, а поданная — вернуться в черновик.
Статус RES конечный: заявка с внесённым результатом не редактируется,
при повторном участии заявитель создаёт новую заявку.

Результат (одобрено / отклонено) вносится заявителем вручную: система не
получает его от организатора (границы автоматизации, п. 3.3 ТЗ).
"""

TRANSITIONS: dict[str, set[str]] = {
    "DRAFT": {"PREP"},
    "PREP": {"SENT"},
    "SENT": {"RES"},
    "RES": set(),
}

RESULTS = {"APPROVED", "REJECTED"}

STATUS_NAMES = {
    "DRAFT": "Черновик",
    "PREP": "Готовлю",
    "SENT": "Подана",
    "RES": "Результат",
}


def check_transition(
    current: str, target: str, *, program_archived: bool, result: str | None
) -> None:
    """Проверка перехода. Возбуждает ValueError с текстом для пользователя.

    Программа в архиве: заявка сохраняется, но продвигать её по статусам
    больше нельзя — разрешено только внести итоговый результат (п. 4.2.8 ТЗ).
    """
    if current == "RES":
        raise ValueError("Завершённая заявка не редактируется")

    if program_archived:
        if target != "RES":
            raise ValueError(
                "Приём по программе завершён: доступно только внесение результата"
            )
    elif target not in TRANSITIONS[current]:
        allowed = ", ".join(sorted(TRANSITIONS[current])) or "нет доступных переходов"
        raise ValueError(
            f"Недопустимый переход из статуса «{STATUS_NAMES[current]}»; "
            f"разрешено: {allowed}"
        )

    if target == "RES":
        if result not in RESULTS:
            raise ValueError("Для статуса «Результат» укажите одобрено или отклонено")
    elif result is not None:
        raise ValueError("Результат заполняется только при переходе в статус «Результат»")
