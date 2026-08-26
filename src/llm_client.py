"""Опциональные запросы к Proxy API только для спорных строк."""

from __future__ import annotations

import json
import re

from .config import get_proxy_config, proxy_ready
from .normalize import normalize_conclusion

SYSTEM_PROMPT = """Ты аудитор сервисных ремонтов нефтепромыслового оборудования.
По полям Факт, Трудозатраты, Материалы и Транспорт верни JSON вида {"labels": ["..."]}.
Можно выбрать несколько фраз, но только из списка:
- транспорт приписка
- транспорт недосписание
- трудозатраты приписка
- трудозатраты недосписание
- ТМЦ не соответствует
- отсутствует простой
- простой не соответствует
- сверхурочное время работы
Если отклонений нет, верни {"labels": []}.
Сравни числа: если часы КВР больше табеля/альфы/п/л — это приписка, если меньше — недосписание.
Если по трудозатратам приписка, а по транспорту проблем нет — используй «сверхурочное время работы».
По полю Факт:
- статус НЕТ и явно сказано, что простоя в системе нет / нет в АРМИТС → «отсутствует простой»;
- статус НЕТ и указана любая другая работа или другой простой
  (например «простои 07.07. прокладка кабеля») → «простой не соответствует»;
- голое НЕТ без комментария → «отсутствует простой»;
- при статусе НЕТ нельзя оставлять факт без одной из этих двух фраз.
Статус ДА сам по себе не даёт меток простоя.
По полю Материалы: ДА → метку ТМЦ не добавляй; НЕТ (любой комментарий) → «ТМЦ не соответствует».
Не пиши пояснений, точек, нумерации и других слов."""

FEW_SHOTS = (
    (
        "ДА",
        "НЕТ (8 по альфе, 10,75 КВР)",
        "ДА",
        "НЕТ (у976му списано в КВР-10,7ч, подписано в п/л-8,3ч.)",
        ["трудозатраты приписка", "транспорт приписка"],
    ),
    (
        "ДА",
        "НЕТ (12 по альфе, 8 КВР)",
        "ДА",
        "ДА",
        ["трудозатраты недосписание"],
    ),
    (
        "ДА",
        "НЕТ (8 по альфе, 9,5 по КВР)",
        "ДА",
        "ДА",
        ["сверхурочное время работы"],
    ),
    (
        "ДА",
        "ДА",
        "ДА",
        "ДА",
        [],
    ),
    (
        "НЕТ (в АРМИТС простоев за 06.07.2026 нет) вкладка АРМИТС",
        "да",
        "ДА",
        "ДА",
        ["отсутствует простой"],
    ),
    (
        "НЕТ (простоя за 06.07.2026 нет в АРМИТС) вкладка АРМИТС",
        "да",
        "ДА",
        "ДА",
        ["отсутствует простой"],
    ),
    (
        "НЕТ (на эту дату в системе указан другой простой)",
        "ДА",
        "ДА",
        "ДА",
        ["простой не соответствует"],
    ),
    (
        "ДА",
        "ДА",
        "НЕТ (работы выполнялись не по затраченным материалам)",
        "ДА",
        ["ТМЦ не соответствует"],
    ),
    (
        "нет(простои 07.07. прокладка кабеля)",
        "да",
        "ДА",
        "ДА",
        ["простой не соответствует"],
    ),
)


def _user_prompt(fact, labour, transport, materials="") -> str:
    return (
        f"Факт: {fact}\n"
        f"Трудозатраты: {labour}\n"
        f"Материалы: {materials}\n"
        f"Транспорт: {transport}\n"
        "Верни JSON."
    )


def _parse_labels(content: str) -> str:
    text = (content or "").strip()
    labels: list[str] = []
    try:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        payload = json.loads(match.group(0) if match else text)
        raw_labels = payload.get("labels", [])
        if isinstance(raw_labels, str):
            raw_labels = [raw_labels]
        labels = [str(item) for item in raw_labels]
    except (json.JSONDecodeError, TypeError, AttributeError):
        labels = [text]
    return normalize_conclusion(", ".join(labels))


def predict_conclusion(fact, labour, transport, materials="") -> str:
    if not proxy_ready():
        raise RuntimeError("Proxy API не настроен. Заполните PROXY_API_KEY и PROXY_BASE_URL в .env")

    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("Установите пакет openai: pip install openai") from exc

    cfg = get_proxy_config()
    client = OpenAI(api_key=cfg["api_key"], base_url=cfg["base_url"])
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for fact_ex, labour_ex, materials_ex, transport_ex, labels in FEW_SHOTS:
        messages.append(
            {"role": "user", "content": _user_prompt(fact_ex, labour_ex, transport_ex, materials_ex)}
        )
        messages.append({"role": "assistant", "content": json.dumps({"labels": labels}, ensure_ascii=False)})
    messages.append({"role": "user", "content": _user_prompt(fact, labour, transport, materials)})

    kwargs = {
        "model": cfg["model"],
        "messages": messages,
        "temperature": 0,
        "max_tokens": 120,
    }
    try:
        response = client.chat.completions.create(response_format={"type": "json_object"}, **kwargs)
    except Exception:
        response = client.chat.completions.create(**kwargs)

    content = ""
    if response.choices:
        content = response.choices[0].message.content or ""
    return _parse_labels(content)