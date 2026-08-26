"""Выгрузка результатов сверки и графиков аудита в Excel."""

from __future__ import annotations

from io import BytesIO

import pandas as pd
from openpyxl.chart import BarChart, LineChart, Reference
from openpyxl.chart.axis import ChartLines
from openpyxl.chart.label import DataLabelList
from openpyxl.chart.series import DataPoint
from openpyxl.chart.shapes import GraphicalProperties
from openpyxl.drawing.line import LineProperties
from openpyxl.styles import Alignment, Font
from openpyxl.utils.dataframe import dataframe_to_rows
from openpyxl.workbook import Workbook

from .charts import (
    BLUE,
    GREEN,
    ORANGE,
    RED,
    criterion_charts,
    overall_summary,
    overall_title,
    workshop_compliance,
)

OVERALL_SHORT = {
    "Выявлены несоответствия по одному или нескольким критериям": "Выявлены несоответствия",
}

WORKSHOP_SHORT = {
    "Соответствует всем критериям аудита": "Соответствует",
    "Не соответствует одному или нескольким критериям аудита": "Не соответствует",
}


def _write_table(ws, frame: pd.DataFrame, start_row: int, start_col: int = 1) -> tuple[int, int]:
    for r_idx, row in enumerate(dataframe_to_rows(frame, index=False, header=True), start=start_row):
        for c_idx, value in enumerate(row, start=start_col):
            cell = ws.cell(row=r_idx, column=c_idx, value=value)
            if r_idx == start_row:
                cell.font = Font(bold=True, color="375623")
            cell.alignment = Alignment(wrap_text=True, vertical="center")
    end_row = start_row + len(frame)
    end_col = start_col + max(frame.shape[1] - 1, 0)
    return end_row, end_col


def _hide_gridlines(axis) -> None:
    axis.majorGridlines = ChartLines()
    axis.majorGridlines.spPr = GraphicalProperties(ln=LineProperties(noFill=True))


def _value_labels() -> DataLabelList:
    labels = DataLabelList()
    labels.showVal = True
    labels.showCatName = False
    labels.showSerName = False
    labels.showPercent = False
    labels.showLegendKey = False
    return labels


def _color_points(series, colors: list[str]) -> None:
    series.dPt = []
    for idx, color in enumerate(colors):
        point = DataPoint(idx=idx)
        point.graphicalProperties.solidFill = color.lstrip("#")
        series.dPt.append(point)


def _style_chart(chart, *, legend: str | None, width: float, height: float) -> None:
    chart.type = "col"
    chart.grouping = "clustered"
    chart.style = 10
    chart.y_axis.title = None
    chart.x_axis.title = None
    chart.y_axis.numFmt = "0"
    chart.gapWidth = 70
    chart.overlap = 0
    chart.width = width
    chart.height = height
    _hide_gridlines(chart.x_axis)
    _hide_gridlines(chart.y_axis)
    if legend is None:
        chart.legend = None
    else:
        chart.legend.position = legend
        chart.legend.overlay = False


def _column_chart(title: str | None = None, *, legend: str | None = None, width: float = 18, height: float = 9) -> BarChart:
    chart = BarChart()
    if title:
        chart.title = title
    _style_chart(chart, legend=legend, width=width, height=height)
    return chart


def _add_overall_chart(ws, frame: pd.DataFrame, source_name: str, chart_row: int, data_row: int, data_col: int = 20) -> int:
    ws.cell(row=chart_row, column=1, value=overall_title(source_name)).font = Font(
        bold=True, size=16, color="548235"
    )
    ws.cell(row=chart_row + 1, column=1, value="Полная сходимость условиям аудита, шт").font = Font(
        color="7F7F7F", size=11
    )

    chart_frame = frame.copy()
    chart_frame["Показатель"] = chart_frame["Показатель"].replace(OVERALL_SHORT)
    end_row, _ = _write_table(ws, chart_frame, data_row, start_col=data_col)

    bars = _column_chart(None, legend=None, width=18, height=9)
    bars.y_axis.axId = 100
    data = Reference(ws, min_col=data_col + 1, min_row=data_row, max_row=end_row)
    cats = Reference(ws, min_col=data_col, min_row=data_row + 1, max_row=end_row)
    bars.add_data(data, titles_from_data=True)
    bars.set_categories(cats)
    if bars.series:
        bars.series[0].dLbls = _value_labels()
        _color_points(bars.series[0], [BLUE, RED, GREEN])

    line = LineChart()
    line.y_axis.axId = 200
    line.y_axis.crosses = "max"
    line.y_axis.title = None
    line.y_axis.scaling.min = 0
    line.y_axis.scaling.max = 100
    _hide_gridlines(line.y_axis)
    line.legend = None
    line_data = Reference(ws, min_col=data_col + 2, min_row=data_row, max_row=end_row)
    line.add_data(line_data, titles_from_data=True)
    line.set_categories(cats)
    if line.series:
        line.series[0].dLbls = DataLabelList()
        line.series[0].dLbls.showVal = False
        line.series[0].graphicalProperties.line.solidFill = ORANGE.lstrip("#")
        line.series[0].graphicalProperties.line.width = 25000

    # Доля уже в процентах 0–100, Excel-ось лучше оставить как числа.
    line.y_axis.numFmt = "0"
    bars.y_axis.crosses = "min"
    bars += line
    bars.legend = None
    ws.add_chart(bars, "A" + str(chart_row + 3))
    return end_row + 2


def _add_workshop_chart(ws, frame: pd.DataFrame, chart_row: int, data_row: int, data_col: int = 20) -> int:
    ws.cell(
        row=chart_row,
        column=1,
        value="Полная сходимость проверенных КВР по условиям аудита в разрезе цехов, шт.",
    ).font = Font(bold=True, size=13, color="375623")

    chart_frame = frame.rename(columns=WORKSHOP_SHORT)
    end_row, _ = _write_table(ws, chart_frame, data_row, start_col=data_col)
    chart = _column_chart(None, legend="b", width=18, height=9)
    data = Reference(ws, min_col=data_col + 1, min_row=data_row, max_col=data_col + 2, max_row=end_row)
    cats = Reference(ws, min_col=data_col, min_row=data_row + 1, max_row=end_row)
    chart.add_data(data, titles_from_data=True)
    chart.set_categories(cats)
    palette = [BLUE, ORANGE]
    for idx, series in enumerate(chart.series):
        series.graphicalProperties.solidFill = palette[idx % 2].lstrip("#")
        series.dLbls = _value_labels()
    ws.add_chart(chart, "A" + str(chart_row + 2))
    return end_row + 2


def _add_criterion_charts(ws, items, chart_row: int, data_row: int, data_col: int = 20) -> None:
    placements = (
        ("A", chart_row),
        ("J", chart_row),
        ("A", chart_row + 20),
        ("J", chart_row + 20),
    )
    table_row = data_row
    for item, (anchor, row) in zip(items, placements):
        frame = item.counts.rename_axis("Категория").reset_index(name="шт")
        end_row, _ = _write_table(ws, frame, table_row, start_col=data_col)
        chart = _column_chart(item.title, legend=None, width=15, height=9)
        data = Reference(ws, min_col=data_col + 1, min_row=table_row, max_row=end_row)
        cats = Reference(ws, min_col=data_col, min_row=table_row + 1, max_row=end_row)
        chart.add_data(data, titles_from_data=True)
        chart.set_categories(cats)
        if chart.series:
            chart.series[0].dLbls = _value_labels()
            _color_points(chart.series[0], [color.lstrip("#") for color in item.colors])
        ws.add_chart(chart, f"{anchor}{row}")
        table_row = end_row + 3


def add_charts_sheet(workbook: Workbook, result_df: pd.DataFrame, source_name: str = "") -> None:
    ws = workbook.create_sheet("Графики")
    ws.sheet_view.showGridLines = False
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToPage = True
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    for col, width in (("A", 28), ("B", 16), ("C", 14), ("J", 36), ("K", 14)):
        ws.column_dimensions[col].width = width

    # Таблицы уводим вправо, чтобы на экране остались только графики.
    overall = overall_summary(result_df)
    after_overall = _add_overall_chart(ws, overall, source_name, chart_row=1, data_row=1)
    workshops = workshop_compliance(result_df)
    after_workshops = _add_workshop_chart(ws, workshops, chart_row=22, data_row=after_overall)
    items = criterion_charts(result_df)
    _add_criterion_charts(ws, items, chart_row=44, data_row=after_workshops)


def dataframes_to_xlsx(
    sheets: dict[str, pd.DataFrame],
    result_df: pd.DataFrame | None = None,
    source_name: str = "",
) -> bytes:
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        for name, frame in sheets.items():
            export_df = frame.copy()
            export_df.to_excel(writer, sheet_name=name[:31], index=False)
        if result_df is not None:
            add_charts_sheet(writer.book, result_df, source_name)
    buffer.seek(0)
    return buffer.getvalue()
