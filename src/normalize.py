"""Канонические формулировки вывода аудита КВР."""

from __future__ import annotations

ALLOWED_LABELS = (
    "транспорт приписка",
    "транспорт недосписание",
    "трудозатраты приписка",
    "трудозатраты недосписание",
    "ТМЦ не соответствует",
    "отсутствует простой",
    "простой не соответствует",
    "сверхурочное время работы",
)

LABEL_ALIASES = {
    "приписка транспорта": "транспорт приписка",
    "недосписание транспорта": "транспорт недосписание",
    "приписка трудозатрат": "трудозатраты приписка",
    "недосписание трудозатрат": "трудозатраты недосписание",
    "нет простоя": "отсутствует простой",
    "простоев нет": "отсутствует простой",
    "простоя нет": "отсутствует простой",
    "простой отсутствует": "отсутствует простой",
    "несоответствие простоя": "простой не соответствует",
    "сверхурочные": "сверхурочное время работы",
    "сверхурочное время": "сверхурочное время работы",
    "тмц не соответствует": "ТМЦ не соответствует",
    "материалы не соответствует": "ТМЦ не соответствует",
    "несоответствие тмц": "ТМЦ не соответствует",
    "несоответствие материалов": "ТМЦ не соответствует",
}

STANDARD_COLUMNS = [
    "№_п/п",
    "Номер_КВР",
    "Цех",
    "Факт",
    "Трудозатраты",
    "Материалы",
    "Транспорт",
    "Вывод",
]


def split_problems(text) -> list[str]:
    if not isinstance(text, str) or not text.strip():
        return []
    cleaned = text.replace(";", ",").strip()
    return [part.strip() for part in cleaned.split(",") if part.strip()]


def normalize_conclusion(text) -> str:
    """Оставляет только разрешённые фразы в фиксированном порядке."""
    if text is None:
        return ""
    raw = str(text).strip()
    if not raw or raw.lower() in {"nan", "none", "null"}:
        return ""

    lowered = raw.lower()
    found: list[str] = []

    for alias, label in LABEL_ALIASES.items():
        if alias in lowered and label not in found:
            found.append(label)

    for label in ALLOWED_LABELS:
        if label.lower() in lowered and label not in found:
            found.append(label)

    return ", ".join(label for label in ALLOWED_LABELS if label in found)


def conclusions_match(left, right) -> bool:
    return normalize_conclusion(left) == normalize_conclusion(right)


def has_reference_value(value) -> bool:
    if value is None or (isinstance(value, float) and value != value):
        return False
    text = str(value).strip()
    return bool(text) and text.lower() not in {"nan", "none", "null"}