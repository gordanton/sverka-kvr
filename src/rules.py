"""Правиловый разбор чек-листа КВР."""

from __future__ import annotations

import re
from dataclasses import dataclass

import pandas as pd

from .normalize import conclusions_match, has_reference_value, normalize_conclusion

LABOUR_KEYS = {
    "табель": ["табель", "табел"],
    "альфа": ["альфа", "альфе", "альфы"],
    "квр": ["квр"],
}

TRANSPORT_KEYS = {
    "tcloud": ["tcloud"],
    "п/л": ["п/л"],
    "пут": ["пут.лист", "путев", "пут"],
    "квр": ["квр"],
}

ISSUE_MARKERS = (
    "квр",
    "табель",
    "табел",
    "альф",
    "п/л",
    "путев",
    "tcloud",
    "приписка",
    "недосписа",
    "простой",
    "простоя",
    "армитс",
)


@dataclass
class RuleResult:
    conclusion: str
    confidence: str
    needs_llm: bool
    details: str = ""


_PLATE_RE = re.compile(r"[а-яa-z]\s*\d{3,4}\s*[а-яa-z]{1,2}", re.IGNORECASE)


def parse_times(text) -> list[float]:
    if not isinstance(text, str):
        return []
    cleaned = _PLATE_RE.sub(" ", text.replace(",", "."))
    numbers = re.findall(r"(\d+[.]?\d*)", cleaned)
    return [float(item) for item in numbers]


def _extract_one(text: str, keyword: str, prefer: str = "after") -> float | None:
    normalized = text.replace(",", ".")
    match = re.search(re.escape(keyword), normalized, flags=re.IGNORECASE)
    if not match:
        return None
    start, end = match.span()
    window_before = normalized[max(0, start - 24):start]
    window_after = normalized[end:end + 24]
    after_num = re.search(r"^[^0-9]{0,12}(\d+[.]?\d*)", window_after)
    before_num = re.search(r"(\d+[.]?\d*)[^0-9]{0,16}$", window_before)
    if prefer == "before":
        chosen = before_num or after_num
    else:
        chosen = after_num or before_num
    return float(chosen.group(1)) if chosen else None


def extract_numbers_by_keywords(text, mapping: dict[str, list[str]]) -> dict[str, float]:
    if not isinstance(text, str):
        return {}
    found: dict[str, float] = {}
    for canonical, variants in mapping.items():
        prefer = "before" if canonical in {"табель", "альфа"} else "after"
        for variant in variants:
            value = _extract_one(text, variant, prefer=prefer)
            if value is not None:
                found[canonical] = value
                break
    return found


def _compare_hours(left: float, right: float, prefix: str) -> str | None:
    if right > left:
        return f"{prefix} приписка"
    if right < left:
        return f"{prefix} недосписание"
    return None


FACT_MISMATCH_MARKERS = (
    "не соответствует",
    "несоответствие",
    "другой простой",
    "другого простоя",
    "иной простой",
    "не тот простой",
    "указан другой",
    "стоит другой",
    "числится другой",
    "другая дата",
)

FACT_ABSENT_MARKERS = (
    "нет простоя",
    "нет простоев",
    "простоя нет",
    "простоев нет",
    "такого простоя нет",
    "отсутствует",
    "не зафиксирован",
    "нет в армитс",
    "нет записи",
    "не найден",
    "не числится",
)

# Только «простоя/простоев … нет», без «НЕТ (простой …)» — это уже другой простой.
_FACT_ABSENT_SPAN = re.compile(
    r"просто(?:я|ев).{0,48}нет",
    re.IGNORECASE,
)


def _compact_text(text: str) -> str:
    return " ".join(str(text).lower().split())


def _looks_like_issue(text) -> bool:
    if not isinstance(text, str):
        return False
    lowered = text.lower().strip()
    if lowered in {"", "nan", "да", "нет"}:
        return False
    return any(marker in lowered for marker in ISSUE_MARKERS)


def _status_is_no(value: str) -> bool:
    compact = _compact_text(value)
    if compact == "нет":
        return True
    return bool(re.match(r"^нет(\s|[\(,;:\-])", compact))


def _fact_is_negative(fact: str) -> bool:
    return _status_is_no(fact)


def _materials_problem(materials: str) -> str | None:
    if _status_is_no(materials):
        return "ТМЦ не соответствует"
    return None


def _fact_problem(fact: str) -> str | None:
    """НЕТ всегда даёт метку. Пустой вывод недопустим.

    Явное отсутствие простоя в системе → «отсутствует простой».
    Любая иная работа/простой в комментарии → «простой не соответствует».
    """
    if not _fact_is_negative(fact):
        return None
    compact = _compact_text(fact)
    comment = re.sub(r"^нет[\s(,;:\-]*", "", compact).strip(" )")
    if not comment:
        return "отсутствует простой"
    if any(marker in compact for marker in FACT_MISMATCH_MARKERS):
        return "простой не соответствует"
    if any(marker in compact for marker in FACT_ABSENT_MARKERS) or _FACT_ABSENT_SPAN.search(compact):
        return "отсутствует простой"
    return "простой не соответствует"


def _labour_problem(labour: str) -> tuple[str | None, str | None]:
    numbers = extract_numbers_by_keywords(labour, LABOUR_KEYS)
    if "квр" in numbers and "табель" in numbers:
        return _compare_hours(numbers["табель"], numbers["квр"], "трудозатраты"), "keywords"
    if "квр" in numbers and "альфа" in numbers:
        return _compare_hours(numbers["альфа"], numbers["квр"], "трудозатраты"), "keywords"

    parsed = parse_times(labour)
    if len(parsed) >= 2:
        return _compare_hours(parsed[0], parsed[1], "трудозатраты"), "fallback"

    if "приписка" in labour:
        return "трудозатраты приписка", "text"
    if "недосписание" in labour:
        return "трудозатраты недосписание", "text"
    if "сверхурочное" in labour:
        return "сверхурочное время работы", "text"
    return None, None


def _transport_problem(transport: str) -> tuple[str | None, str | None]:
    numbers = extract_numbers_by_keywords(transport, TRANSPORT_KEYS)
    if "tcloud" in numbers and "квр" in numbers:
        return _compare_hours(numbers["tcloud"], numbers["квр"], "транспорт"), "keywords"
    if "п/л" in numbers and "квр" in numbers:
        return _compare_hours(numbers["п/л"], numbers["квр"], "транспорт"), "keywords"
    if "пут" in numbers and "квр" in numbers:
        return _compare_hours(numbers["пут"], numbers["квр"], "транспорт"), "keywords"

    parsed = parse_times(transport)
    if len(parsed) >= 2:
        return _compare_hours(parsed[0], parsed[1], "транспорт"), "fallback"

    if "приписка" in transport:
        return "транспорт приписка", "text"
    if "недосписание" in transport:
        return "транспорт недосписание", "text"
    return None, None


def analyze_row(row) -> RuleResult:
    problems: list[str] = []
    methods: list[str] = []
    unparsed: list[str] = []

    fact = str(row.get("Факт", "")).lower()
    labour = str(row.get("Трудозатраты", "")).lower()
    materials = str(row.get("Материалы", "")).lower()
    transport = str(row.get("Транспорт", "")).lower()

    fact_issue = _fact_problem(fact)
    if fact_issue:
        problems.append(fact_issue)
        methods.append("keywords")
    elif _looks_like_issue(fact):
        unparsed.append("факт")

    labour_issue, labour_method = _labour_problem(labour)
    transport_issue, transport_method = _transport_problem(transport)

    if labour_issue == "трудозатраты приписка" and transport_issue is None:
        labour_issue = "сверхурочное время работы"
    if "сверхурочное" in labour and "сверхурочное время работы" not in problems:
        if labour_issue != "сверхурочное время работы":
            problems.append("сверхурочное время работы")
            labour_issue = None
            methods.append(labour_method or "text")

    if labour_issue:
        problems.append(labour_issue)
        if labour_method:
            methods.append(labour_method)
    elif _looks_like_issue(labour):
        unparsed.append("трудозатраты")

    materials_issue = _materials_problem(materials)
    if materials_issue:
        problems.append(materials_issue)
        methods.append("keywords")

    if transport_issue:
        problems.append(transport_issue)
        if transport_method:
            methods.append(transport_method)
    elif _looks_like_issue(transport):
        unparsed.append("транспорт")

    unique = list(dict.fromkeys(problems))
    conclusion = normalize_conclusion(", ".join(unique)) if unique else ""

    if unparsed or "text" in methods:
        confidence = "низкая"
    elif "fallback" in methods:
        confidence = "средняя"
    else:
        confidence = "высокая"

    details = ""
    if unparsed:
        details = "не разобрано: " + ", ".join(unparsed)
    return RuleResult(
        conclusion=conclusion,
        confidence=confidence,
        needs_llm=confidence == "низкая",
        details=details,
    )


def apply_rules(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    parsed = [analyze_row(row) for _, row in out.iterrows()]
    out["Вывод_правила"] = [item.conclusion for item in parsed]
    out["Уверенность"] = [item.confidence for item in parsed]
    out["Спорная"] = [item.needs_llm for item in parsed]
    out["Комментарий_правил"] = [item.details for item in parsed]
    out["Итоговый_вывод"] = out["Вывод_правила"]

    if "Вывод" in out.columns:
        out = out.rename(columns={"Вывод": "Вывод_исходный"})
        has_ref = out["Вывод_исходный"].map(has_reference_value)
        if bool(has_ref.any()):
            out["Совпадение_правила"] = [
                conclusions_match(pred, ref) if flag else pd.NA
                for pred, ref, flag in zip(out["Вывод_правила"], out["Вывод_исходный"], has_ref)
            ]
    return out