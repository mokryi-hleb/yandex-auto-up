# Yandex Cloud VM watchdog

Небольшой watchdog, который проверяет состояние одной виртуальной машины Yandex Cloud и запускает её, если она остановлена.

## Требования

- Python 3.10+
- IAM-токен Yandex Cloud **или** OAuth-токен аккаунта, у которого есть роль `compute.editor` (либо более узкая роль, позволяющая запрашивать VM и запускать её) для нужного облака/каталога.

## Быстрый запуск

1. Скопируйте `.env.example` в `.env` и заполните `YC_INSTANCE_ID` и один из токенов.
2. Запустите:

   ```powershell
   python watchdog.py
   ```

Скрипт не читает `.env` автоматически, чтобы не зависеть от библиотек. В PowerShell можно загрузить его перед запуском:

```powershell
Get-Content .env | Where-Object { $_ -match '^[^#].+=' } | ForEach-Object {
  $key, $value = $_ -split '=', 2
  [Environment]::SetEnvironmentVariable($key, $value, 'Process')
}
python watchdog.py
```

## Переменные окружения

| Переменная | Описание |
| --- | --- |
| `YC_INSTANCE_ID` | Обязательный ID виртуальной машины. |
| `YC_USE_METADATA_TOKEN` | `true`, если watchdog работает на другой VM Yandex Cloud с подключенным сервисным аккаунтом. Рекомендуемый вариант. |
| `YC_IAM_TOKEN` | Временный IAM-токен. Приоритетнее остальных вариантов, но действует не более 12 часов. |
| `YC_OAUTH_TOKEN` | Устаревший вариант только для ранее выданных OAuth-токенов. Новые токены Yandex ID с 1 июня 2026 не поддерживаются. |
| `CHECK_INTERVAL_SECONDS` | Интервал проверки, по умолчанию `60`. |
| `REQUEST_TIMEOUT_SECONDS` | Таймаут HTTP-запроса, по умолчанию `15`. |
| `LOG_LEVEL` | Уровень логов (`INFO`, `DEBUG` и т. п.), по умолчанию `INFO`. |

При состоянии `STOPPED` watchdog вызывает `start` и ждёт следующего цикла. При `RUNNING`, `STARTING` и переходных состояниях он ничего не делает. Ошибки API логируются, но не останавливают процесс.

## Быстрая установка как службы Linux (systemd)

Watchdog должен находиться **на другой постоянно работающей машине**: если запустить его на отслеживаемой VM, он остановится вместе с ней и не сможет её включить. Подойдёт отдельная недорогая VM, сервер или домашний Linux-компьютер.

На машине watchdog выполните:

```bash
git clone https://github.com/mokryi-hleb/yandex-auto-up.git
cd yandex-auto-up
sudo ./install.sh
```

Установщик запросит ID VM и способ аутентификации, скопирует приложение в `/opt/yc-vm-watchdog`, сохранит настройки в `/etc/yc-vm-watchdog.env` с правами `600` и включит службу. По умолчанию выбран безопасный вариант `metadata`: короткоживущий IAM-токен получается автоматически из сервисного аккаунта VM.

Проверка и журналы:

```bash
sudo systemctl status yc-vm-watchdog
sudo journalctl -u yc-vm-watchdog -f
```

## Что подготовить в Yandex Cloud

Рекомендуемый вариант не требует хранить токен на Linux-машине, но сама машина watchdog должна быть отдельной VM в Yandex Cloud.

1. Найдите ID целевой VM: в [Compute Cloud → Виртуальные машины](https://yandex.cloud/ru/docs/compute/operations/vm-info/get-info) откройте нужную VM и скопируйте её идентификатор.
2. Создайте отдельный [сервисный аккаунт](https://yandex.cloud/ru/docs/iam/concepts/users/service-accounts) для watchdog.
3. В каталоге, где находится целевая VM, назначьте этому аккаунту роль `compute.editor`. Назначение роли через консоль или CLI описано в [официальной инструкции](https://yandex.cloud/ru/docs/iam/operations/sa/assign-role-for-sa). Не давайте широкую роль `editor`, если достаточно `compute.editor`.
4. Создайте отдельную постоянно включённую VM для watchdog и укажите этот сервисный аккаунт при её создании. Сервис будет получать короткоживущий IAM-токен из [сервиса метаданных VM](https://yandex.cloud/ru/docs/compute/concepts/vm-metadata), без секрета в файле.
5. Клонируйте этот репозиторий на VM watchdog и запустите `sudo ./install.sh`. На вопрос `Authentication` выберите `metadata` (значение по умолчанию).

Если отдельная VM находится не в Yandex Cloud, установщик пока принимает только IAM-токен. Его можно получить через [Yandex Cloud CLI](https://yandex.cloud/ru/docs/iam/operations/iam-token/create-for-sa), но он действует не больше 12 часов; для постоянного внешнего запуска потребуется добавить аутентификацию сервисного аккаунта по авторизованному ключу.

Не храните токены в Git и не передавайте их в командной строке: они могут попасть в историю shell или список процессов.
