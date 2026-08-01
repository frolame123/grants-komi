"""Персональный подбор программ под профиль организации (FR-005).

Алгоритм двухступенчатый: жёсткий фильтр отсекает заведомо неподходящие
программы, затем оставшиеся ранжируются по сумме баллов (максимум 100).
Результат нигде не кэшируется — пересчитывается на каждый запрос, поэтому
правка профиля влияет на подбор немедленно.

Функции работают с любыми объектами, у которых есть нужные атрибуты, и не
обращаются к СУБД — это позволяет проверить начисление баллов отдельно.
"""

import re
from datetime import date

SCORE_INDUSTRY = 40
SCORE_REGION = 30
SCORE_GOAL = 20
SCORE_DEADLINE = 10

DEADLINE_COMFORT_DAYS = 14
# Слова короче четырёх букв («для», «на», «под») пересечение не образуют
MIN_WORD_LENGTH = 4


def _words(text: str | None) -> set[str]:
    if not text:
        return set()
    return {w for w in re.findall(r"\w+", text.lower()) if len(w) >= MIN_WORD_LENGTH}


def passes_hard_filter(program, profile, today: date) -> bool:
    """Ступень 1: статус, непросроченный срок и совпадение типа заявителя."""
    if program.status != "PUB":
        return False
    if program.deadline is None or program.deadline < today:
        return False
    types = {t.applicant_type for t in program.applicant_types}
    return profile.org_type in types


def match_score(program, profile, today: date) -> int:
    """Ступень 2: сумма баллов соответствия, она же степень соответствия в процентах."""
    score = 0

    if profile.category_id is not None and program.category_id == profile.category_id:
        score += SCORE_INDUSTRY

    if profile.region in {r.region for r in program.regions}:
        score += SCORE_REGION

    if _words(profile.goal) & _words(program.title):
        score += SCORE_GOAL

    if program.deadline is not None and (program.deadline - today).days > DEADLINE_COMFORT_DAYS:
        score += SCORE_DEADLINE

    return score


def select_programs(programs, profile, today: date) -> list[tuple[object, int]]:
    """Отобранные программы с баллами, по убыванию степени соответствия."""
    matched = [
        (program, match_score(program, profile, today))
        for program in programs
        if passes_hard_filter(program, profile, today)
    ]
    matched.sort(key=lambda pair: (-pair[1], pair[0].deadline))
    return matched
