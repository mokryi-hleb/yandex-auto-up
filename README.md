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

## Запуск как служба Linux (systemd)

Сохраните секреты в `/etc/yc-vm-watchdog.env` с правами `600`, затем создайте `/etc/systemd/system/yc-vm-watchdog.service`:

```ini
[Unit]
Description=Yandex Cloud VM watchdog
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=watchdog
WorkingDirectory=/opt/yc-vm-watchdog
EnvironmentFile=/etc/yc-vm-watchdog.env
ExecStart=/usr/bin/python3 /opt/yc-vm-watchdog/watchdog.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Активируйте службу:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now yc-vm-watchdog
sudo journalctl -u yc-vm-watchdog -f
```

Не храните токены в Git и не передавайте их в командной строке: они могут попасть в историю shell или список процессов.
