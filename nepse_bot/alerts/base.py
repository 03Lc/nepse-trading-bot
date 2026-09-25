"""Alert system with deduplication (Phase 12)."""

from __future__ import annotations

import hashlib
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

log = logging.getLogger("nepse_bot.alerts")


@dataclass
class Alert:
    symbol: str
    title: str
    body: str
    priority: str = "normal"
    price: Optional[float] = None
    signal: Optional[str] = None
    data_age_sec: Optional[float] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    extra: dict[str, Any] = field(default_factory=dict)

    def fingerprint(self) -> str:
        raw = f"{self.symbol}|{self.title}|{self.signal}|{self.priority}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def format_text(self) -> str:
        lines = [
            f"[{self.priority.upper()}] {self.symbol} — {self.title}",
            f"Time: {self.timestamp.isoformat()}",
        ]
        if self.price is not None:
            lines.append(f"Price: {self.price}")
        if self.signal:
            lines.append(f"Signal: {self.signal}")
        if self.data_age_sec is not None:
            lines.append(f"Data age: {self.data_age_sec:.3f}s")
        lines.append(self.body)
        return "\n".join(lines)


class AlertBackend(ABC):
    @abstractmethod
    def send(self, alert: Alert) -> bool:
        ...


class ConsoleAlertBackend(AlertBackend):
    def send(self, alert: Alert) -> bool:
        print(alert.format_text())
        print("-" * 40)
        return True


class TelegramAlertBackend(AlertBackend):
    def __init__(self, token: Optional[str] = None, chat_id: Optional[str] = None):
        import os
        self.token = token or os.environ.get("TELEGRAM_BOT_TOKEN")
        self.chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID")

    def send(self, alert: Alert) -> bool:
        if not self.token or not self.chat_id:
            log.warning("Telegram backend not configured")
            return False
        try:
            import urllib.request
            import urllib.parse
            url = f"https://api.telegram.org/bot{self.token}/sendMessage"
            data = urllib.parse.urlencode({"chat_id": self.chat_id, "text": alert.format_text()}).encode()
            req = urllib.request.Request(url, data=data, method="POST")
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status == 200
        except Exception as e:
            log.error("Telegram send failed: %s", e)
            return False


class EmailAlertBackend(AlertBackend):
    def send(self, alert: Alert) -> bool:
        log.info("Email backend not fully configured; logged: %s", alert.title)
        return False


class AlertManager:
    def __init__(self, backends: Optional[list[AlertBackend]] = None, dedupe_ttl_sec: float = 300.0):
        self.backends = backends or [ConsoleAlertBackend()]
        self.dedupe_ttl_sec = dedupe_ttl_sec
        self._sent: dict[str, float] = {}

    def emit(self, alert: Alert) -> bool:
        fp = alert.fingerprint()
        now = time.time()
        self._sent = {k: v for k, v in self._sent.items() if now - v < self.dedupe_ttl_sec}
        if fp in self._sent:
            return False
        ok_any = False
        for b in self.backends:
            try:
                if b.send(alert):
                    ok_any = True
            except Exception as e:
                log.error("Backend failed: %s", e)
        if ok_any:
            self._sent[fp] = now
        return ok_any
