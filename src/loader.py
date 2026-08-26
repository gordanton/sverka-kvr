"""Загрузка чек-листа КВР из Excel."""

from __future__ import annotations

import pandas as pd

from .normalize import STANDARD_COLUMNS

_HEADER_MARKERS = ("факт", "трудозатрат", "транспорт")


def _rewind(source):
    if hasattr(source, "seek"):
        source.seek(0)
    return source


def list_sheets(source) -> list[str]:
    source = _rewind(source)
    with pd.ExcelFile(source) as xf:
        return list(xf.sheet_names)


def _detect_header_row(excel_file: pd.ExcelFile, sheet_name: str) -> int:
    preview = pd.read_excel(excel_file, sheet_name=sheet_name, header=None, nrows=12)
    for index, row in preview.iterrows():
        joined = " ".join(str(value).lower() for value in row.tolist() if pd.notna(value))
        if sum(marker in joined for marker in _HEADER_MARKERS) >= 2:
            return int(index)
    return 3


def _is_blank(series: pd.Series) -> pd.Series:
    text = series.astype(str).str.strip().str.lower()
    return series.isna() | text.isin(["", "nan", "none", "<na>", "не указан"])


def _clean_id_column(series: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    if numeric.notna().any() and bool((numeric.dropna() % 1 == 0).all()):
        return numeric.astype("Int64")
    return series


def load_checklist(source, sheet_name: str | None = None) -> pd.DataFrame:
    source = _rewind(source)
    with pd.ExcelFile(source) as xf:
        names = list(xf.sheet_names)
        if sheet_name is None:
            sheet_name = "Лист1" if "Лист1" in names else names[0]
        if sheet_name not in names:
            raise ValueError(f"Лист «{sheet_name}» не найден. Доступны: {', '.join(names)}")

        skiprows = _detect_header_row(xf, sheet_name)
        frame = pd.read_excel(xf, sheet_name=sheet_name, skiprows=skiprows)

    if frame.shape[1] < 7:
        raise ValueError("В файле меньше 7 колонок — это не похоже на чек-лист КВР.")

    width = min(8, frame.shape[1])
    frame = frame.iloc[:, :width].copy()
    frame.columns = STANDARD_COLUMNS[:width]
    for column in STANDARD_COLUMNS[width:]:
        frame[column] = pd.NA

    number = frame["№_п/п"].astype(str).str.strip()
    mask = frame["№_п/п"].notna() & (number != "") & (number.str.lower() != "nan")
    mask &= ~number.str.lower().str.contains("итого|всего", regex=True)
    frame = frame.loc[mask].reset_index(drop=True)

    frame["№_п/п"] = _clean_id_column(frame["№_п/п"])
    frame["Номер_КВР"] = _clean_id_column(frame["Номер_КВР"])
    frame["Цех"] = frame["Цех"].astype(str).str.strip()
    frame = frame.loc[~_is_blank(frame["№_п/п"])].copy()
    frame = frame.loc[~_is_blank(frame["Номер_КВР"])].copy()
    frame = frame.loc[~_is_blank(frame["Цех"])].copy()
    return frame.reset_index(drop=True)