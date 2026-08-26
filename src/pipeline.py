"""Склейка правилового метода и опционального API."""

from __future__ import annotations

from collections.abc import Callable

import pandas as pd

from .llm_client import predict_conclusion
from .normalize import conclusions_match, has_reference_value, normalize_conclusion
from .rules import apply_rules


def run_reconciliation(
    df: pd.DataFrame,
    use_llm: bool = False,
    progress: Callable[[int, int, str], None] | None = None,
) -> pd.DataFrame:
    result = apply_rules(df)
    result["Вывод_API"] = ""

    if not use_llm:
        if progress:
            progress(1, 1, "Готово")
        return result

    targets = [index for index, row in result.iterrows() if bool(row["Спорная"])]
    total = max(len(targets), 1)
    if progress:
        progress(0, total, "Спорных строк нет" if not targets else "Запрос к API...")

    for step, index in enumerate(targets, start=1):
        row = result.loc[index]
        if progress:
            progress(step - 1, total, f"API: строка {row.get('№_п/п', index)}")
        try:
            prediction = predict_conclusion(
                row["Факт"],
                row["Трудозатраты"],
                row["Транспорт"],
                row.get("Материалы", ""),
            )
        except Exception as exc:
            prediction = f"Ошибка API: {exc}"
        result.at[index, "Вывод_API"] = prediction
        if prediction and not str(prediction).startswith("Ошибка"):
            result.at[index, "Итоговый_вывод"] = normalize_conclusion(
                ", ".join(
                    part for part in (str(row["Вывод_правила"] or ""), prediction) if part.strip()
                )
            )

    if "Вывод_исходный" in result.columns:
        has_ref = result["Вывод_исходный"].map(has_reference_value)
        if bool(has_ref.any()):
            result["Совпадение_API"] = [
                conclusions_match(pred, ref) if flag and pred else pd.NA
                for pred, ref, flag in zip(result["Вывод_API"], result["Вывод_исходный"], has_ref)
            ]

    if progress:
        progress(total, total, "Готово")
    return result