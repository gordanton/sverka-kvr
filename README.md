## Что это
Локальное Streamlit-приложение для сверки чек-листов КВР: автоматическое заполнение столбца «Вывод», сводка по цехам и графики.
## Как запустить/проверить
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
Откроется http://localhost:8501. Загрузите Excel-чек-лист и нажмите «Заполнить выводы».
## Что я сделал(а)
- инициализировал репозиторий (`git init`);
- сделал коммиты и отправил проект на GitHub;
- оформил README;
- собрал приложение сверки КВР (правила + Streamlit + выгрузка Excel).
## Что было сложным / что понял(а)
Сложным было не залить в git секреты (`.env`) и рабочие Excel. Понял, что репозиторий — это история коммитов, а не «просто папка на GitHub»: сначала init и commit, потом origin и push.

# Сверка КВР

Локальное веб-приложение на Streamlit для автоматического заполнения столбца «Вывод» в чек-листах аудита КВР (факт/простой, трудозатраты, материалы, транспорт).

Ядро — правиловый парсер чисел и шаблонных формулировок. Опционально строки с низкой уверенностью можно отправить в OpenAI-совместимый Proxy API.

## Возможности

- загрузка Excel и выбор листа;
- заполнение вывода по правилам;
- правка итогового вывода в таблице;
- сводка по цехам;
- графики аудита в интерфейсе и в Excel;
- выгрузка книги с листами «Результат», «Сводка», «Графики».

## Запуск

Нужен Python 3.10+.

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

Откроется адрес вида `http://localhost:8501`.

### Переменные окружения

Файл `.env` в репозиторий не входит. Скопируйте значения из `EnvExample`:

```
PROXY_API_KEY=
PROXY_BASE_URL=https://api.proxyapi.ru/openai/v1
PROXY_MODEL=gpt-4o-mini
```

Без ключа приложение работает полностью: API нужен только если включить сверку спорных строк.

## Деплой на сервер (Docker + SSH)

Приложение слушает порт **8501**. Секреты живут только в `.env` на сервере, в образ они не попадают.

### 0. Что взять из панели ihor

- публичный IP сервера;
- логин (часто `root`);
- пароль из письма — он нужен **один раз**, чтобы положить свой SSH-ключ.

Подставьте свой IP вместо `SERVER_IP`.

### 1. SSH-ключ на своём Windows

В PowerShell:

```powershell
# Есть ли уже ключ
Get-ChildItem $env:USERPROFILE\.ssh

# Если id_ed25519 нет — создать (Enter, Enter, Enter)
ssh-keygen -t ed25519 -C "sverka-kvr"
```

Публичный ключ — это файл `id_ed25519.pub`. Приватный `id_ed25519` никуда не копируйте и не вставляйте в чат.

Положите публичный ключ на сервер (первый раз спросит пароль из панели ihor):

```powershell
Get-Content $env:USERPROFILE\.ssh\id_ed25519.pub | ssh root@SERVER_IP "mkdir -p ~/.ssh; chmod 700 ~/.ssh; cat >> ~/.ssh/authorized_keys; chmod 600 ~/.ssh/authorized_keys"
```

Дальше вход без пароля:

```powershell
ssh root@SERVER_IP
```

Если ключ не подхватился: `ssh -i $env:USERPROFILE\.ssh\id_ed25519 root@SERVER_IP`.

### 2. Один раз на сервере: Docker и git

```bash
apt update && apt install -y git
curl -fsSL https://get.docker.com | sh
docker --version
docker compose version
```

Откройте порт в панели ihor (Firewall) и, если включён ufw:

```bash
ufw allow OpenSSH
ufw allow 8501/tcp
ufw enable
```

### 3. Код и запуск контейнера

На сервере:

```bash
git clone https://github.com/gordanton/sverka-kvr.git
cd sverka-kvr
cp EnvExample .env
nano .env
```

В `.env` впишите `PROXY_API_KEY`, сохраните (`Ctrl+O`, Enter, `Ctrl+X`). Затем:

```bash
docker compose up -d --build
docker compose ps
docker compose logs -f --tail=50
```

Сайт: `http://SERVER_IP:8501`.

Проверка у себя в PowerShell, без входа на сервер:

```powershell
ssh root@SERVER_IP "docker compose -f ~/sverka-kvr/docker-compose.yml ps"
```

### 4. Обновить код после правок

```bash
cd ~/sverka-kvr
git pull
docker compose up -d --build
```

Полезные команды:

```bash
docker compose logs -f        # логи
docker compose restart        # перезапуск
docker compose down           # остановить
```

Локально тот же compose: в папке проекта `docker compose up --build` и открыть http://localhost:8501.

Streamlit без пароля: кто знает IP и порт, может пользоваться приложением и тратить токены API. Для учебы достаточно порта 8501; для постоянной работы лучше закрыть порт чужим IP через firewall.

## Структура

```
app.py                 # Streamlit
src/                   # парсер, правила, сводка, графики, API
EnvExample             # шаблон переменных
Dockerfile             # образ приложения
docker-compose.yml     # запуск контейнера
.streamlit/            # адрес 0.0.0.0 и порт 8501
requirements.txt
presentation/          # генератор презентации и готовый pptx
```

Чек-листы с реальными данными в репозиторий не кладутся: загружайте свой Excel через интерфейс.

## Презентация

```powershell
pip install python-pptx
python presentation/presentation.py
```

## Лицензия

Учебный итоговый проект курса «Специалист по ИИ-системам», Университет Иннополис, 2026.
