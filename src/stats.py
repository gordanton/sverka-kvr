"""Сводка отклонений по цехам."""

from __future__ import annotations

import pandas as pd

from .normalize import ALLOWED_LABELS, split_problems


def build_ceh_stats(df: pd.DataFrame, conclusion_col: str = "Итоговый_вывод") -> pd.DataFrame:
    work = df.copy()
    if "Цех" not in work.columns:
        return pd.DataFrame()
    work["Цех"] = work["Цех"].astype(str).str.strip()
    blank = work["Цех"].str.lower().isin(["", "nan", "none", "<na>", "не указан"])
    work = work.loc[~blank].copy()
    if work.empty:
        return pd.DataFrame()
    work["Проблемы"] = work[conclusion_col].apply(split_problems)
    work["Есть_отклонение"] = work["Проблемы"].apply(bool)

    ceh_stats = work.groupby("Цех", dropna=False).agg(
        Всего_КВР=("№_п/п", "count"),
        С_отклонениями=("Есть_отклонение", "sum"),
        Без_отклонений=("Есть_отклонение", lambda series: (~series.astype(bool)).sum()),
    ).reset_index()

    exploded = work.explode("Проблемы")
    exploded = exploded.dropna(subset=["Проблемы"])
    if exploded.empty:
        pivot = pd.DataFrame({"Цех": ceh_stats["Цех"]})
    else:
        counts = exploded.groupby(["Цех", "Проблемы"]).size().reset_index(name="Количество")
        pivot = counts.pivot(index="Цех", columns="Проблемы", values="Количество").reset_index()

    result = ceh_stats.merge(pivot, on="Цех", how="left")
    for label in ALLOWED_LABELS:
        if label not in result.columns:
            result[label] = 0
        result[label] = result[label].fillna(0).astype(int)

    result["%_отклонений"] = (
        result["С_отклонениями"] / result["Всего_КВР"].replace(0, pd.NA) * 100
    ).round(1)

    ordered = (
        ["Цех", "Всего_КВР", "С_отклонениями", "Без_отклонений", "%_отклонений"]
        + list(ALLOWED_LABELS)
    )
    result = result[ordered].sort_values("Цех").reset_index(drop=True)

    total = result.select_dtypes(include="number").sum()
    total_row = {column: total.get(column, 0) for column in result.columns}
    total_row["Цех"] = "ИТОГО"
    if result["Всего_КВР"].sum():
        total_row["%_отклонений"] = round(
            float(result["С_отклонениями"].sum() / result["Всего_КВР"].sum() * 100),
            1,
        )
    result = pd.concat([result, pd.DataFrame([total_row])], ignore_index=True)
    return result