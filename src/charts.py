"""Данные и графики аудита КВР для Streamlit и Excel."""

from __future__ import annotations

import re
from dataclasses import dataclass

import pandas as pd

from .normalize import split_problems

BLUE = "#5B9BD5"
RED = "#C00000"
GREEN = "#70AD47"
ORANGE = "#ED7D31"
GREY = "#A5A5A5"
YELLOW = "#FFC000"

CEH_SHORT_RULES = (
    ("гидропривод", "УСГП"),
    ("азнакаев", "АзЦ"),
    ("альметьев", "АЦ"),
    ("бавлин", "БЦ"),
    ("джалил", "ДЦ"),
    ("елабуж", "ЕЦ"),
    ("елхов", "ЕЦ"),
    ("лениногор", "ЛЦ"),
    ("нурлат", "НЦ"),
    ("прикам", "ПрЦ"),
    ("ямаш", "ЯЦ"),
)

CEH_SHORT_ORDER = ("АзЦ", "АЦ", "БЦ", "ДЦ", "ЕЦ", "ЛЦ", "НЦ", "ПрЦ", "ЯЦ", "УСГП")

OVERALL_LABELS = (
    "Всего проверено КВР",
    "Выявлены несоответствия по одному или нескольким критериям",
    "Соответствие по всем критериям",
)

FACT_ORDER = (
    "Соответствие",
    "Отсутствует простой",
    "Вид или дата простоя не соответствует",
)
LABOUR_ORDER = (
    "Соответствие",
    "Сверхурочные работы",
    "Приписки",
    "Недосписано",
)
MATERIALS_ORDER = (
    "Соответствие",
    "Некорректное списание ТМЦ",
)
TRANSPORT_ORDER = (
    "Соответствие",
    "Недосписание транспорта",
    "Приписка часов по транспорту",
)


@dataclass
class CriterionChart:
    title: str
    x_title: str
    order: tuple[str, ...]
    colors: tuple[str, ...]
    counts: pd.Series


def extract_audit_date(source_name: str = "") -> str:
    text = str(source_name or "")
    match = re.search(r"(\d{2}\.\d{2}\.\d{4})", text)
    if match:
        return match.group(1)
    match = re.search(r"(\d{2}\.\d{2}\.\d{2,4})", text)
    return match.group(1) if match else ""


def overall_title(source_name: str = "") -> str:
    date = extract_audit_date(source_name)
    if date:
        return f"Аудит КВР цехов УСНПО за {date} года"
    return "Аудит КВР цехов УСНПО"


def short_ceh_name(name: str) -> str:
    lowered = str(name).lower()
    for fragment, short in CEH_SHORT_RULES:
        if fragment in lowered:
            return short
    return str(name)


def _problems(row, conclusion_col: str = "Итоговый_вывод") -> list[str]:
    return split_problems(row.get(conclusion_col, ""))


def _prepared(df: pd.DataFrame, conclusion_col: str) -> pd.DataFrame:
    work = df.copy()
    if "Цех" in work.columns:
        work["Цех"] = work["Цех"].astype(str).str.strip()
        blank = work["Цех"].str.lower().isin(["", "nan", "none", "<na>", "не указан"])
        work = work.loc[~blank].copy()
    work["Проблемы"] = work.apply(lambda row: _problems(row, conclusion_col), axis=1)
    work["Есть_отклонение"] = work["Проблемы"].apply(bool)
    work["Цех_кратко"] = work["Цех"].map(short_ceh_name) if "Цех" in work.columns else ""
    return work


def _ordered_counts(values: pd.Series, order: tuple[str, ...]) -> pd.Series:
    cat = pd.Categorical(values, categories=list(order), ordered=True)
    return pd.Series(cat).value_counts(sort=False).reindex(list(order), fill_value=0).astype(int)


def overall_summary(df: pd.DataFrame, conclusion_col: str = "Итоговый_вывод") -> pd.DataFrame:
    work = _prepared(df, conclusion_col)
    total = int(len(work))
    failed = int(work["Есть_отклонение"].sum()) if total else 0
    passed = total - failed
    values = [total, failed, passed]
    percents = [100.0 if total else 0.0]
    percents.append(round(failed / total * 100, 1) if total else 0.0)
    percents.append(round(passed / total * 100, 1) if total else 0.0)
    return pd.DataFrame(
        {
            "Показатель": list(OVERALL_LABELS),
            "шт": values,
            "%": percents,
        }
    )


def workshop_compliance(df: pd.DataFrame, conclusion_col: str = "Итоговый_вывод") -> pd.DataFrame:
    work = _prepared(df, conclusion_col)
    if work.empty:
        return pd.DataFrame(
            columns=["Цех", "Соответствует всем критериям аудита", "Не соответствует одному или нескольким критериям аудита"]
        )
    grouped = work.groupby("Цех_кратко", dropna=False).agg(
        соответствует=("Есть_отклонение", lambda series: int((~series.astype(bool)).sum())),
        не_соответствует=("Есть_отклонение", "sum"),
    ).reset_index()
    grouped.columns = [
        "Цех",
        "Соответствует всем критериям аудита",
        "Не соответствует одному или нескольким критериям аудита",
    ]
    grouped["порядок"] = grouped["Цех"].apply(
        lambda name: CEH_SHORT_ORDER.index(name) if name in CEH_SHORT_ORDER else 99
    )
    grouped = grouped.sort_values(["порядок", "Цех"]).drop(columns="порядок").reset_index(drop=True)
    return grouped


def _fact_bucket(problems: list[str]) -> str:
    if "простой не соответствует" in problems:
        return FACT_ORDER[2]
    if "отсутствует простой" in problems:
        return FACT_ORDER[1]
    return FACT_ORDER[0]


def _labour_bucket(problems: list[str]) -> str:
    if "трудозатраты приписка" in problems:
        return "Приписки"
    if "трудозатраты недосписание" in problems:
        return "Недосписано"
    if "сверхурочное время работы" in problems:
        return "Сверхурочные работы"
    return "Соответствие"


def _materials_bucket(problems: list[str]) -> str:
    if "ТМЦ не соответствует" in problems:
        return "Некорректное списание ТМЦ"
    return "Соответствие"


def _transport_bucket(problems: list[str]) -> str:
    if "транспорт приписка" in problems:
        return "Приписка часов по транспорту"
    if "транспорт недосписание" in problems:
        return "Недосписание транспорта"
    return "Соответствие"


def criterion_charts(df: pd.DataFrame, conclusion_col: str = "Итоговый_вывод") -> list[CriterionChart]:
    work = _prepared(df, conclusion_col)
    problems = work["Проблемы"]
    return [
        CriterionChart(
            title=(
                "Аудит силами службы управления производством на факт выполнения работ, "
                "корректность указания объекта Заказчика в КВР, шт."
            ),
            x_title="Факт выполнения работы",
            order=FACT_ORDER,
            colors=(BLUE, ORANGE, GREY),
            counts=_ordered_counts(problems.map(_fact_bucket), FACT_ORDER),
        ),
        CriterionChart(
            title=(
                "Аудит силами службы управления персоналом соответствие времени работы "
                "по каждому сотруднику за смену, шт."
            ),
            x_title="Соответствие времени работы",
            order=LABOUR_ORDER,
            colors=(BLUE, ORANGE, GREY, YELLOW),
            counts=_ordered_counts(problems.map(_labour_bucket), LABOUR_ORDER),
        ),
        CriterionChart(
            title=(
                "Аудит силами службы управления производством. Соответствие использованных "
                "материалов, заявленных в КВР, характеру и объему выполненных работ, шт."
            ),
            x_title="Соответствие использованных материалов",
            order=MATERIALS_ORDER,
            colors=(BLUE, ORANGE),
            counts=_ordered_counts(problems.map(_materials_bucket), MATERIALS_ORDER),
        ),
        CriterionChart(
            title=(
                "Аудит силами группы транспортной логистики на корректность информации "
                "по транспорту, заявленному в КВР, шт."
            ),
            x_title="Корректность информации по транспорту",
            order=TRANSPORT_ORDER,
            colors=(BLUE, ORANGE, GREY),
            counts=_ordered_counts(problems.map(_transport_bucket), TRANSPORT_ORDER),
        ),
    ]


def _altair():
    import altair as alt

    return alt


def overall_altair(df: pd.DataFrame, source_name: str = "", conclusion_col: str = "Итоговый_вывод"):
    alt = _altair()
    data = overall_summary(df, conclusion_col)
    data = data.copy()
    data["цвет"] = [BLUE, RED, GREEN]
    bars = (
        alt.Chart(data)
        .mark_bar(size=60)
        .encode(
            x=alt.X("Показатель:N", sort=list(OVERALL_LABELS), title="", axis=alt.Axis(labelLimit=220, labelAngle=0)),
            y=alt.Y("шт:Q", title="шт"),
            color=alt.Color("цвет:N", scale=None, legend=None),
        )
    )
    labels = bars.mark_text(dy=-8, fontWeight="bold").encode(text="шт:Q", color=alt.value("#222"))
    line = (
        alt.Chart(data)
        .mark_line(color=ORANGE, point=True, strokeWidth=3)
        .encode(
            x=alt.X("Показатель:N", sort=list(OVERALL_LABELS)),
            y=alt.Y("%:Q", title="%", axis=alt.Axis(orient="right", format=".0f")),
        )
    )
    return (
        alt.layer(bars, labels, line)
        .resolve_scale(y="independent")
        .properties(title={"text": overall_title(source_name), "subtitle": "Полная сходимость условиям аудита, шт"}, height=360)
    )


def workshop_altair(df: pd.DataFrame, conclusion_col: str = "Итоговый_вывод"):
    alt = _altair()
    data = workshop_compliance(df, conclusion_col)
    if data.empty:
        return None
    long = data.melt(id_vars="Цех", var_name="Критерий", value_name="шт")
    chart = (
        alt.Chart(long)
        .mark_bar()
        .encode(
            x=alt.X("Цех:N", sort=list(CEH_SHORT_ORDER), title=""),
            xOffset="Критерий:N",
            y=alt.Y("шт:Q", title="шт"),
            color=alt.Color(
                "Критерий:N",
                scale=alt.Scale(
                    domain=[
                        "Соответствует всем критериям аудита",
                        "Не соответствует одному или нескольким критериям аудита",
                    ],
                    range=[BLUE, ORANGE],
                ),
                legend=alt.Legend(orient="bottom", title=""),
            ),
        )
        .properties(
            title="Полная сходимость проверенных КВР по условиям аудита в разрезе цехов, шт.",
            height=360,
        )
    )
    text = (
        alt.Chart(long)
        .mark_text(dy=-8)
        .encode(
            x=alt.X("Цех:N", sort=list(CEH_SHORT_ORDER)),
            xOffset="Критерий:N",
            y="шт:Q",
            text="шт:Q",
        )
    )
    return chart + text


def criterion_altair(item: CriterionChart):
    alt = _altair()
    data = item.counts.rename_axis("Категория").reset_index(name="шт")
    data["цвет"] = list(item.colors)[: len(data)]
    bars = (
        alt.Chart(data)
        .mark_bar(size=50)
        .encode(
            x=alt.X("Категория:N", sort=list(item.order), title=item.x_title, axis=alt.Axis(labelAngle=0, labelLimit=180)),
            y=alt.Y("шт:Q", title="шт"),
            color=alt.Color("цвет:N", scale=None, legend=None),
        )
        .properties(title=item.title, height=280)
    )
    labels = bars.mark_text(dy=-8, fontWeight="bold").encode(text="шт:Q", color=alt.value("#222"))
    return bars + labels
