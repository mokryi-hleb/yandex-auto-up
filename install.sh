#!/usr/bin/env bash
# Install Yandex Cloud VM watchdog as a systemd service.
set -euo pipefail

SERVICE_NAME="yc-vm-watchdog"
INSTALL_DIR="/opt/${SERVICE_NAME}"
ENV_FILE="/etc/${SERVICE_NAME}.env"
UNIT_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run this installer with sudo: sudo ./install.sh" >&2
  exit 1
fi

if ! command -v systemctl >/dev/null; then
  echo "systemd is required." >&2
  exit 1
fi

if ! command -v python3 >/dev/null; then
  echo "Python 3 is required. Install it first (for example: sudo apt install python3)." >&2
  exit 1
fi

if ! python3 -c 'import sys; raise SystemExit(sys.version_info < (3, 10))'; then
  echo "Python 3.10 or newer is required." >&2
  exit 1
fi

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if [[ ! -f "${SCRIPT_DIR}/watchdog.py" ]]; then
  echo "watchdog.py was not found next to install.sh." >&2
  exit 1
fi

read -r -p "Yandex Cloud VM ID to monitor: " INSTANCE_ID
while [[ -z "${INSTANCE_ID}" ]]; do
  read -r -p "VM ID cannot be empty. Enter VM ID: " INSTANCE_ID
done

echo "Recommended: choose metadata when this watchdog runs on another Yandex Cloud VM with a service account attached."
read -r -p "Authentication [metadata/IAM] (default: metadata): " TOKEN_TYPE
TOKEN_TYPE="${TOKEN_TYPE:-metadata}"
case "${TOKEN_TYPE,,}" in
  metadata)
    TOKEN_VARIABLE="YC_USE_METADATA_TOKEN"
    TOKEN="true"
    ;;
  oauth)
    echo "OAuth tokens from Yandex ID issued after 1 June 2026 are not supported by Yandex Cloud." >&2
    exit 1
    ;;
  iam)
    TOKEN_VARIABLE="YC_OAUTH_TOKEN"
    TOKEN_VARIABLE="YC_IAM_TOKEN"
    echo "Paste an IAM token (input is hidden):"
    read -r -s TOKEN
    echo
    while [[ -z "${TOKEN}" ]]; do
      echo "Token cannot be empty. Paste an IAM token:"
      read -r -s TOKEN
      echo
    done
    echo "Warning: IAM tokens expire. Re-run this installer or update ${ENV_FILE} when it expires." >&2
    ;;
  *)
    echo "Unknown authentication type. Enter metadata or IAM." >&2
    exit 1
    ;;
esac

if ! id -u "${SERVICE_NAME}" >/dev/null 2>&1; then
  useradd --system --no-create-home --shell /usr/sbin/nologin "${SERVICE_NAME}"
fi

install -d -o root -g root -m 0755 "${INSTALL_DIR}"
install -o root -g root -m 0755 "${SCRIPT_DIR}/watchdog.py" "${INSTALL_DIR}/watchdog.py"

umask 077
cat > "${ENV_FILE}" <<EOF
YC_INSTANCE_ID=${INSTANCE_ID}
${TOKEN_VARIABLE}=${TOKEN}
CHECK_INTERVAL_SECONDS=60
REQUEST_TIMEOUT_SECONDS=15
LOG_LEVEL=INFO
EOF
chmod 0600 "${ENV_FILE}"
chown root:root "${ENV_FILE}"
unset TOKEN

cat > "${UNIT_FILE}" <<EOF
[Unit]
Description=Yandex Cloud VM watchdog
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${SERVICE_NAME}
WorkingDirectory=${INSTALL_DIR}
EnvironmentFile=${ENV_FILE}
ExecStart=/usr/bin/python3 ${INSTALL_DIR}/watchdog.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now "${SERVICE_NAME}.service"
systemctl --no-pager --full status "${SERVICE_NAME}.service"

echo "Installed. Logs: sudo journalctl -u ${SERVICE_NAME} -f"
