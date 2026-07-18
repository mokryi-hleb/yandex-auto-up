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
| `YC_IAM_TOKEN` | IAM-токен. Приоритетнее OAuth-токена. |
| `YC_OAUTH_TOKEN` | OAuth-токен: watchdog сам получает из него IAM-токен и обновляет его по мере работы. |
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

Установщик запросит ID VM и токен скрытым вводом, скопирует приложение в `/opt/yc-vm-watchdog`, сохранит настройки в `/etc/yc-vm-watchdog.env` с правами `600` и включит службу. Для долгой работы предпочтителен OAuth-токен: скрипт сам получает из него свежие IAM-токены.

Проверка и журналы:

```bash
sudo systemctl status yc-vm-watchdog
sudo journalctl -u yc-vm-watchdog -f
```

Не храните токены в Git и не передавайте их в командной строке: они могут попасть в историю shell или список процессов.
