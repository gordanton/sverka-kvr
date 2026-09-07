from __future__ import annotations

from datetime import datetime

import pandas as pd
import streamlit as st

from src.config import get_proxy_config, proxy_ready
from src.charts import criterion_altair, criterion_charts, overall_altair, workshop_altair
from src.export import dataframes_to_xlsx
from src.loader import list_sheets, load_checklist
from src.pipeline import run_reconciliation
from src.stats import build_ceh_stats

RESULT_COLUMNS = [
    "№_п/п",
    "Номер_КВР",
    "Цех",
    "Факт",
    "Трудозатраты",
    "Материалы",
    "Транспорт",
    "Вывод_исходный",
    "Вывод_правила",
    "Уверенность",
    "Спорная",
    "Комментарий_правил",
    "Вывод_API",
    "Итоговый_вывод",
    "Совпадение_правила",
    "Совпадение_API",
]


def _init_state() -> None:
    defaults = {
        "result_df": None,
        "source_name": "",
        "sheet_name": "",
        "run_id": 0,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _visible_columns(df: pd.DataFrame) -> list[str]:
    return [column for column in RESULT_COLUMNS if column in df.columns]


def _accuracy(df: pd.DataFrame, column: str) -> str | None:
    if column not in df.columns:
        return None
    series = df[column].dropna()
    if series.empty:
        return None
    return f"{series.mean() * 100:.1f}%"


st.set_page_config(page_title="Сверка КВР", page_icon="📋", layout="wide")
_init_state()

st.title("Сверка данных КВР")
st.caption(
    "Локальное заполнение столбца «Вывод» по чек-листу аудита. "
    "Основной метод — правила сравнения часов, API только для спорных строк."
)

cfg = get_proxy_config()
api_ok = proxy_ready()

with st.sidebar:
    st.header("Настройки")
    if api_ok:
        st.success("Proxy API настроен")
        st.caption(f"Модель: {cfg['model']}")
        st.caption(cfg["base_url"])
    else:
        st.warning("Proxy API не настроен")
        st.caption("Впишите PROXY_API_KEY и PROXY_BASE_URL в файл .env")

    use_llm = st.checkbox(
        "Проверить спорные строки через API",
        value=False,
        disabled=not api_ok,
        help="В API уходят только строки с низкой уверенностью правил.",
    )
    st.divider()
    st.markdown(
        "Запуск:\n\n"
        "`streamlit run app.py`\n\n"
        "или `docker compose up --build`"
    )

uploaded = st.file_uploader("Загрузите чек-лист Excel", type=["xlsx"])
if uploaded is None:
    st.info("Ожидается файл с колонками: № п/п, Номер КВР, Цех, Факт, Трудозатраты, Материалы, Транспорт, Вывод.")
    st.stop()

if uploaded.name != st.session_state.source_name:
    st.session_state.source_name = uploaded.name
    st.session_state.result_df = None
    st.session_state.sheet_name = ""

try:
    sheets = list_sheets(uploaded)
except Exception as exc:
    st.error(f"Не удалось прочитать Excel: {exc}")
    st.stop()

default_sheet = "Лист1" if "Лист1" in sheets else sheets[0]
sheet_name = st.selectbox("Лист", options=sheets, index=sheets.index(default_sheet))
if st.session_state.result_df is not None and st.session_state.sheet_name and sheet_name != st.session_state.sheet_name:
    st.session_state.result_df = None

try:
    raw_df = load_checklist(uploaded, sheet_name=sheet_name)
except Exception as exc:
    st.error(f"Не удалось разобрать чек-лист: {exc}")
    st.stop()

preview_col, metric_col = st.columns([3, 1])
with preview_col:
    st.subheader("Исходные строки")
    st.dataframe(raw_df, use_container_width=True, hide_index=True, height=280)
with metric_col:
    st.metric("Строк КВР", len(raw_df))
    filled = raw_df["Вывод"].map(lambda value: str(value).strip() not in {"", "nan", "None"}).sum()
    st.metric("Эталонных выводов", int(filled))
    st.metric("Цехов", int(raw_df["Цех"].nunique()))

if st.button("Заполнить выводы", type="primary", use_container_width=True):
    progress_bar = st.progress(0, text="Считаем правила...")

    def on_progress(step: int, total: int, message: str) -> None:
        ratio = 1.0 if total == 0 else min(step / total, 1.0)
        progress_bar.progress(ratio, text=message)

    with st.spinner("Идёт сверка..."):
        st.session_state.result_df = run_reconciliation(raw_df, use_llm=use_llm, progress=on_progress)
        st.session_state.sheet_name = sheet_name
        st.session_state.run_id += 1
    progress_bar.empty()

result_df = st.session_state.result_df
if result_df is None:
    st.stop()

st.success(f"Готово: {len(result_df)} строк. Можно поправить итоговый вывод вручную.")

tab_results, tab_charts, tab_stats, tab_compare = st.tabs(
    ["Результаты", "Графики", "Сводка по цехам", "Сравнение"]
)

with tab_results:
    view = result_df[_visible_columns(result_df)].copy()
    disabled = [column for column in view.columns if column != "Итоговый_вывод"]
    edited = st.data_editor(
        view,
        use_container_width=True,
        hide_index=True,
        disabled=disabled,
        height=460,
        key=f"result_editor_{st.session_state.run_id}",
    )
    st.session_state.result_df = result_df.copy()
    st.session_state.result_df["Итоговый_вывод"] = edited["Итоговый_вывод"].values

    current = st.session_state.result_df
    left, mid, right = st.columns(3)
    left.metric("С отклонениями", int(current["Итоговый_вывод"].astype(str).str.strip().ne("").sum()))
    mid.metric("Спорных строк", int(current["Спорная"].sum()) if "Спорная" in current.columns else 0)
    right.metric("Точность правил", _accuracy(current, "Совпадение_правила") or "нет эталона")

with tab_charts:
    current = st.session_state.result_df
    source_name = st.session_state.source_name
    st.altair_chart(overall_altair(current, source_name), width="stretch")
    shop_chart = workshop_altair(current)
    if shop_chart is not None:
        st.altair_chart(shop_chart, width="stretch")
    left_col, right_col = st.columns(2)
    criteria = criterion_charts(current)
    with left_col:
        st.altair_chart(criterion_altair(criteria[0]), width="stretch")
        st.altair_chart(criterion_altair(criteria[2]), width="stretch")
    with right_col:
        st.altair_chart(criterion_altair(criteria[1]), width="stretch")
        st.altair_chart(criterion_altair(criteria[3]), width="stretch")

with tab_stats:
    stats_df = build_ceh_stats(st.session_state.result_df)
    if stats_df.empty:
        st.info("Нет строк с указанным цехом для сводки.")
    else:
        st.dataframe(stats_df, use_container_width=True, hide_index=True)
        chart_df = stats_df[stats_df["Цех"] != "ИТОГО"][["Цех", "%_отклонений"]].set_index("Цех")
        if not chart_df.empty:
            st.bar_chart(chart_df)

with tab_compare:
    compare_cols = [
        column
        for column in (
            "№_п/п",
            "Номер_КВР",
            "Цех",
            "Вывод_исходный",
            "Вывод_правила",
            "Совпадение_правила",
            "Вывод_API",
            "Совпадение_API",
            "Итоговый_вывод",
            "Уверенность",
        )
        if column in st.session_state.result_df.columns
    ]
    st.dataframe(st.session_state.result_df[compare_cols], use_container_width=True, hide_index=True)
    api_acc = _accuracy(st.session_state.result_df, "Совпадение_API")
    if api_acc:
        st.metric("Точность API на эталоне", api_acc)
    else:
        st.caption("Эталонный столбец «Вывод» пуст или API не запускался — сравнивать нечего.")

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
export_df = st.session_state.result_df.copy()
if "Вывод_исходный" in export_df.columns:
    export_df["Вывод"] = export_df["Итоговый_вывод"]
stats_df = build_ceh_stats(export_df)
xlsx_bytes = dataframes_to_xlsx(
    {
        "Результат": export_df,
        "Сводка": stats_df,
    },
    result_df=export_df,
    source_name=st.session_state.source_name,
)
st.download_button(
    "Скачать Excel",
    data=xlsx_bytes,
    file_name=f"Результат_заполнения_{timestamp}.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    type="primary",
)