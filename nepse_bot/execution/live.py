"""Live execution (Phase 15) — intentionally blocked."""

from __future__ import annotations


class LiveExecutionBlockedError(RuntimeError):
    pass


class LiveExecutionAdapter:
    mode = "live"
    ENABLED = False

    def __init__(self, *args, **kwargs):
        raise LiveExecutionBlockedError(
            "Live execution is disabled. "
            "No officially supported retail NEPSE trading API is integrated. "
            "Do not bypass TMS authentication, CAPTCHA, 2FA, or rate limits. "
            "Use PaperBroker for simulated orders."
        )

    def submit(self, *args, **kwargs):
        raise LiveExecutionBlockedError("Live execution blocked")
