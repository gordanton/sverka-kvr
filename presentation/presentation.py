"""Генерация презентации проекта сверки КВР."""

from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt

GREEN = RGBColor(0x37, 0x56, 0x23)
DARK = RGBColor(0x1F, 0x1F, 0x1F)
GRAY = RGBColor(0x59, 0x59, 0x59)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
ACCENT = RGBColor(0x54, 0x82, 0x35)
LIGHT = RGBColor(0xE2, 0xEF, 0xDA)

OUTPUT = Path(__file__).resolve().parent / "Презентация_сверка_КВР_август2026.pptx"


def _set_run(paragraph, text, *, size=18, bold=False, color=DARK, align=None):
    if align is not None:
        paragraph.alignment = align
    run = paragraph.add_run()
    run.text = text
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color
    run.font.name = "Calibri"
    return run


def _add_notes(slide, text):
    notes = slide.notes_slide.notes_text_frame
    notes.text = text


def _blank(prs):
    return prs.slides.add_slide(prs.slide_layouts[6])


def _band(slide, prs, color=GREEN):
    shape = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE, Inches(0), Inches(0), prs.slide_width, Inches(0.18)
    )
    shape.fill.solid()
    shape.fill.fore_color.rgb = color
    shape.line.fill.background()


def _footer(slide, prs, page, total=12):
    box = slide.shapes.add_textbox(Inches(0.5), Inches(7.05), Inches(8.5), Inches(0.3))
    p = box.text_frame.paragraphs[0]
    _set_run(p, f"Сверка КВР  ·  Иннополис  ·  {page}/{total}", size=11, color=GRAY)


def _title_box(slide, text, top=0.35):
    box = slide.shapes.add_textbox(Inches(0.5), Inches(top), Inches(9.0), Inches(0.7))
    _set_run(box.text_frame.paragraphs[0], text, size=28, bold=True, color=GREEN)
    return box


def _bullets(slide, lines, top=1.15, height=5.6, size=18):
    box = slide.shapes.add_textbox(Inches(0.55), Inches(top), Inches(8.9), Inches(height))
    tf = box.text_frame
    tf.word_wrap = True
    first = True
    for item in lines:
        if isinstance(item, tuple):
            text, opts = item
        else:
            text, opts = item, {}
        p = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        p.level = opts.get("level", 0)
        p.space_after = Pt(opts.get("space", 8))
        _set_run(
            p,
            text,
            size=opts.get("size", size),
            bold=opts.get("bold", False),
            color=opts.get("color", DARK),
        )
    return box


def create_presentation():
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)

    # --- 1. Титульный ---
    slide = _blank(prs)
    bg = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), Inches(0), prs.slide_width, prs.slide_height)
    bg.fill.solid()
    bg.fill.fore_color.rgb = GREEN
    bg.line.fill.background()
    accent = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), Inches(0), Inches(0.25), prs.slide_height)
    accent.fill.solid()
    accent.fill.fore_color.rgb = ACCENT
    accent.line.fill.background()

    box = slide.shapes.add_textbox(Inches(0.9), Inches(2.0), Inches(11.5), Inches(1.8))
    tf = box.text_frame
    tf.word_wrap = True
    _set_run(tf.paragraphs[0], "Автоматизированная система сверки КВР", size=36, bold=True, color=WHITE, align=PP_ALIGN.LEFT)
    p = tf.add_paragraph()
    _set_run(p, "с элементами ИИ", size=28, color=LIGHT, align=PP_ALIGN.LEFT)

    info = slide.shapes.add_textbox(Inches(0.9), Inches(4.3), Inches(10), Inches(2))
    tf = info.text_frame
    _set_run(tf.paragraphs[0], "Гордионов Антон", size=22, color=WHITE)
    for line in (
        "Курс: Специалист по ИИ-системам, Университет Иннополис",
        "Итоговый проект  ·  август 2026",
    ):
        p = tf.add_paragraph()
        _set_run(p, line, size=18, color=LIGHT)
    _add_notes(slide, "Представиться. Название: локальная сверка чек-листов КВР, ИИ — опциональный API и неудачный эксперимент с Qwen.")

    # --- 2 ---
    slide = _blank(prs)
    _band(slide, prs)
    _title_box(slide, "Актуальность и цель")
    _bullets(
        slide,
        [
            ("Проблема", {"bold": True, "size": 22, "color": GREEN}),
            ("Ручная сверка КВР — факт/простой, трудозатраты, транспорт, материалы — до 4 часов в месяц", {"level": 0}),
            ("Высокий риск ошибок при сравнении часов и свободного текста", {"level": 0}),
            ("Цель", {"bold": True, "size": 22, "color": GREEN, "space": 10}),
            ("Локальное веб-приложение: автоматическое заполнение столбца «Вывод» за несколько минут", {"level": 0}),
            ("Понятная сводка по цехам, графики и выгрузка в Excel", {"level": 0}),
        ],
    )
    _footer(slide, prs, 2)
    _add_notes(slide, "Акцент: не «заменить аудитора», а снять рутину сравнения часов и шаблонных формулировок.")

    # --- 3 ---
    slide = _blank(prs)
    _band(slide, prs)
    _title_box(slide, "Этап 1. Эксперимент с дообучением Qwen (Colab)")
    _bullets(
        slide,
        [
            ("Первая попытка: LoRA-дообучение Qwen2-1.5B-Instruct на 200+ размеченных строках чек-листов", {"size": 18}),
            ("Проблемы", {"bold": True, "size": 22, "color": GREEN}),
            ("Точность около 30%: модель путала «приписку» и «недосписание»", {"level": 0}),
            ("Нужен GPU, долгая загрузка, непригодно для обычного рабочего ПК", {"level": 0}),
            ("Плохо сравнивает числа в свободном тексте, ответы нестабильны", {"level": 0}),
            ("Вывод: сверка КВР — не генерация текста, а детерминированное сравнение чисел и шаблонов. Дальше — правиловый парсер.", {"bold": True, "size": 17}),
        ],
    )
    _footer(slide, prs, 3)
    _add_notes(slide, "Честно сказать: fine-tuning не оправдался. «Элементы ИИ» в продукте — опциональный Proxy API, не эта модель.")

    # --- 4 ---
    slide = _blank(prs)
    _band(slide, prs)
    _title_box(slide, "Правиловый парсер в Colab")
    _bullets(
        slide,
        [
            ("Вместо дообучения — парсер по ключевым словам и числам", {"size": 18}),
            ("Факт / простой: «НЕТ», «простоя нет», «нет в АРМИТС», иной простой", {"level": 0}),
            ("Трудозатраты: часы из строк вида «по табелю 8ч, по КВР 10,3ч» или «по альфе / по КВР»", {"level": 0}),
            ("Транспорт: часы из Tcloud / путевого листа и КВР", {"level": 0}),
            ("На эталонных файлах Colab точность правил — 100%, обработка мгновенная", {"bold": True, "size": 18}),
            ("Столбец «Материалы» на этом этапе ещё не входил в парсер", {"size": 16, "color": GRAY}),
        ],
    )
    _footer(slide, prs, 4)
    _add_notes(slide, "4 заполненных СВОДа нужны были как эталон, а не как обучение модели. Правила из них выписали руками.")

    # --- 5 ---
    slide = _blank(prs)
    _band(slide, prs)
    _title_box(slide, "Этап 2. Локальный веб-интерфейс (Streamlit)")
    _bullets(
        slide,
        [
            ("Проект переписан как локальное приложение Streamlit", {"size": 18}),
            ("Загрузка Excel и выбор листа", {"level": 0}),
            ("Кнопка «Заполнить выводы» — запуск правил", {"level": 0}),
            ("Ручная правка столбца «Итоговый_вывод» в таблице", {"level": 0}),
            ("Экспорт Excel: листы «Результат», «Сводка», «Графики»", {"level": 0}),
            ("Опционально Proxy API только для спорных строк; ядро — правила", {"level": 0}),
        ],
    )
    _footer(slide, prs, 5)
    _add_notes(slide, "Показать живое приложение, если успеете. Без ключа API всё равно работает.")

    # --- 6 ---
    slide = _blank(prs)
    _band(slide, prs)
    _title_box(slide, "Доработка правил по обратной связи")
    _bullets(
        slide,
        [
            ("Итерации после первых прогонов на реальном чек-листе", {"size": 18}),
            ("Факт: «НЕТ + прокладка кабеля» → «простой не соответствует», а не «отсутствует простой»", {"level": 0}),
            ("Материалы: статус «НЕТ» → «ТМЦ не соответствует»", {"level": 0}),
            ("Пустые строки отфильтрованы: в сводке 10 цехов, без фиктивного «не указан»", {"level": 0}),
            ("Итог: 50 КВР тестового файла разобраны по принятой логике аудита", {"bold": True, "size": 18}),
        ],
    )
    _footer(slide, prs, 6)
    _add_notes(slide, "Это сильный слайд для защиты: показали, что правила правятся быстрее, чем переобучение модели.")

    # --- 7 ---
    slide = _blank(prs)
    _band(slide, prs)
    _title_box(slide, "Визуализация и отчётность")
    _bullets(
        slide,
        [
            ("Четыре вкладки в интерфейсе", {"bold": True, "size": 22, "color": GREEN}),
            ("Результаты — таблица, уверенность, правка итогового вывода", {"level": 0}),
            ("Графики — общая сходимость, разрез по цехам, четыре аудита по критериям", {"level": 0}),
            ("Сводка по цехам — объёмы, проценты, типы нарушений", {"level": 0}),
            ("Сравнение — если в файле есть эталонный столбец «Вывод»", {"level": 0}),
            ("В скачанном Excel те же графики собираются автоматически", {"bold": True}),
        ],
    )
    _footer(slide, prs, 7)
    _add_notes(slide, "Дальше показать скриншоты. Раскраски ошибок в таблице нет — не обещать.")

    # --- 8 ---
    slide = _blank(prs)
    _band(slide, prs)
    _title_box(slide, "Результаты на тестовом файле")
    _bullets(
        slide,
        [
            ("50 КВР, 10 цехов", {"bold": True, "size": 20, "color": GREEN}),
            ("С отклонениями: 25 (50%)   ·   без отклонений: 25", {"level": 0}),
            ("Транспорт: 11 недосписаний, 6 приписок", {"level": 0}),
            ("Трудозатраты: 6 недосписаний, 6 приписок, 3 сверхурочных", {"level": 0}),
            ("Материалы: 1 несоответствие ТМЦ", {"level": 0}),
            ("Простой: 4 «отсутствует простой», 1 «простой не соответствует»", {"level": 0}),
            ("На эталонах Colab правила дали 100%. На этом файле — полное совпадение с логикой аудита после итераций.", {"size": 16}),
            ("Время: с ~4 часов в месяц до нескольких минут", {"bold": True, "size": 18}),
        ],
        size=17,
    )
    _footer(slide, prs, 8)
    _add_notes(slide, "Не говорить голословно «100% всегда». Цифры — с конкретного файла за 06.07.2026.")

    # --- 9 ---
    slide = _blank(prs)
    _band(slide, prs)
    _title_box(slide, "Демонстрация интерфейса")
    _bullets(
        slide,
        [
            ("Скриншоты для вставки", {"bold": True, "size": 20, "color": GREEN}),
            ("1. Главный экран с загруженным чек-листом", {"level": 0}),
            ("2. Таблица результатов и итоговый вывод", {"level": 0}),
            ("3. Сводка по цехам", {"level": 0}),
            ("4. Графики: общая сходимость, цеха, типы нарушений", {"level": 0}),
            ("Сюда вставить скриншоты из Streamlit и листа «Графики» в Excel", {"size": 16, "color": GRAY}),
        ],
    )
    _footer(slide, prs, 9)
    _add_notes(slide, "Лучше живое демо. Скриншоты — запасной вариант, если сеть или ПК подведут.")

    # --- 10 ---
    slide = _blank(prs)
    _band(slide, prs)
    _title_box(slide, "Дальнейшие планы")
    _bullets(
        slide,
        [
            ("Публикация на внутреннем сервере — запуск без установки Python на каждом ПК", {"level": 0}),
            ("Адаптация парсера под другие отчёты: материалы, наряды-допуски", {"level": 0}),
            ("API только для по-настоящему свободных комментариев", {"level": 0}),
            ("Автогенерация краткого письменного заключения по цехам", {"level": 0}),
        ],
    )
    _footer(slide, prs, 10)
    _add_notes(slide, "Сейчас деплоя нет — это план. Локальный запуск уже достаточен для пилота.")

    # --- 11 ---
    slide = _blank(prs)
    _band(slide, prs)
    _title_box(slide, "Заключение")
    _bullets(
        slide,
        [
            ("Для структурированной сверки КВР правила оказались сильнее дообучения LLM", {"level": 0}),
            ("Приложение автоматизирует заполнение вывода, сводку и графики", {"level": 0}),
            ("Аудитор может поправить итоговый вывод вручную", {"level": 0}),
            ("Инструмент готов к локальной работе и может масштабироваться на соседние процессы", {"level": 0}),
        ],
    )
    _footer(slide, prs, 11)
    _add_notes(slide, "Закрыть кругом: Colab показал границы ML, Streamlit дал рабочий инструмент.")

    # --- 12 ---
    slide = _blank(prs)
    bg = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), Inches(0), prs.slide_width, prs.slide_height)
    bg.fill.solid()
    bg.fill.fore_color.rgb = GREEN
    bg.line.fill.background()
    box = slide.shapes.add_textbox(Inches(0.8), Inches(2.6), Inches(11.7), Inches(2.4))
    tf = box.text_frame
    _set_run(tf.paragraphs[0], "Спасибо за внимание", size=44, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
    p = tf.add_paragraph()
    _set_run(p, "Вопросы?", size=28, color=LIGHT, align=PP_ALIGN.CENTER)
    _add_notes(slide, "Готовые ответы: почему не Qwen; зачем API; что будет, если интерфейс Excel изменится.")

    prs.save(OUTPUT)
    print(f"Сохранено: {OUTPUT}")


if __name__ == "__main__":
    create_presentation()
