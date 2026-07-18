#!/usr/bin/env python3
"""Keep one Yandex Cloud VM running.

Configuration comes only from environment variables; see README.md.
"""

from __future__ import annotations

import json
import logging
import os
import signal
import sys
import time
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


COMPUTE_API = "https://compute.api.cloud.yandex.net/compute/v1/instances"
IAM_API = "https://iam.api.cloud.yandex.net/iam/v1/tokens"
METADATA_TOKEN_API = "http://169.254.169.254/computeMetadata/v1/instance/service-accounts/default/token"
STOP = False


@dataclass(frozen=True)
class Settings:
    instance_id: str
    iam_token: str | None
    oauth_token: str | None
    use_metadata_token: bool
    interval_seconds: int
    timeout_seconds: int


def positive_int(name: str, default: int) -> int:
    value = os.getenv(name, str(default))
    try:
        result = int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be a positive integer, got {value!r}") from exc
    if result <= 0:
        raise ValueError(f"{name} must be a positive integer, got {value!r}")
    return result


def read_settings() -> Settings:
    instance_id = os.getenv("YC_INSTANCE_ID", "").strip()
    iam_token = os.getenv("YC_IAM_TOKEN", "").strip() or None
    oauth_token = os.getenv("YC_OAUTH_TOKEN", "").strip() or None
    use_metadata_token = os.getenv("YC_USE_METADATA_TOKEN", "").lower() in {"1", "true", "yes"}
    if not instance_id:
        raise ValueError("YC_INSTANCE_ID is required")
    if not iam_token and not oauth_token and not use_metadata_token:
        raise ValueError("set YC_USE_METADATA_TOKEN=true, YC_IAM_TOKEN, or YC_OAUTH_TOKEN")
    return Settings(
        instance_id=instance_id,
        iam_token=iam_token,
        oauth_token=oauth_token,
        use_metadata_token=use_metadata_token,
        interval_seconds=positive_int("CHECK_INTERVAL_SECONDS", 60),
        timeout_seconds=positive_int("REQUEST_TIMEOUT_SECONDS", 15),
    )


def api_request(url: str, token: str, timeout: int, method: str = "GET", payload: dict[str, Any] | None = None) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = Request(
        url,
        data=body,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            return json.load(response)
    except HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"API returned HTTP {exc.code}: {details}") from exc
    except URLError as exc:
        raise RuntimeError(f"network error: {exc.reason}") from exc


def get_iam_token(settings: Settings) -> str:
    if settings.iam_token:
        return settings.iam_token
    if settings.use_metadata_token:
        request = Request(METADATA_TOKEN_API, headers={"Metadata-Flavor": "Google"})
        try:
            with urlopen(request, timeout=settings.timeout_seconds) as response:
                metadata = json.load(response)
        except (HTTPError, URLError) as exc:
            raise RuntimeError(f"could not get token from VM metadata service: {exc}") from exc
        token = metadata.get("access_token")
        if not isinstance(token, str) or not token:
            raise RuntimeError("metadata service response does not contain access_token")
        return token
    assert settings.oauth_token
    response = api_request(IAM_API, settings.oauth_token, settings.timeout_seconds, method="POST", payload={})
    token = response.get("iamToken")
    if not isinstance(token, str) or not token:
        raise RuntimeError("IAM API response does not contain iamToken")
    return token


def check_and_start(settings: Settings) -> None:
    token = get_iam_token(settings)
    instance_url = f"{COMPUTE_API}/{settings.instance_id}"
    instance = api_request(instance_url, token, settings.timeout_seconds)
    status = instance.get("status")
    if status == "STOPPED":
        operation = api_request(f"{instance_url}:start", token, settings.timeout_seconds, method="POST", payload={})
        logging.warning("VM was stopped; start requested (operation %s)", operation.get("id", "unknown"))
    else:
        logging.info("VM status: %s; no action needed", status or "unknown")


def request_stop(_signum: int, _frame: Any) -> None:
    global STOP
    STOP = True


def main() -> int:
    try:
        settings = read_settings()
    except ValueError as exc:
        logging.error("Configuration error: %s", exc)
        return 2

    logging.info("Watchdog started for VM %s; checking every %s seconds", settings.instance_id, settings.interval_seconds)
    while not STOP:
        try:
            check_and_start(settings)
        except RuntimeError as exc:
            logging.error("Check failed: %s", exc)
        for _ in range(settings.interval_seconds):
            if STOP:
                break
            time.sleep(1)
    logging.info("Watchdog stopped")
    return 0


if __name__ == "__main__":
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(message)s",
    )
    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)
    sys.exit(main())
