"""Límite de intentos acotado y seguro frente a concurrencia para la API."""

import math
import time
from collections import OrderedDict
from threading import Lock

from app.core.errors import AppError


class LoginLimiter:
    def __init__(self, attempt_limit: int, window_seconds: int, max_keys: int) -> None:
        self.attempt_limit = attempt_limit
        self.window_seconds = window_seconds
        self.max_keys = max_keys
        self._entries: OrderedDict[str, tuple[float, int]] = OrderedDict()
        self._lock = Lock()

    def consume(self, keys: list[str]) -> None:
        now = time.monotonic()
        with self._lock:
            # El orden es por inicio de ventana, por lo que los vencidos forman un prefijo.
            while self._entries:
                first_key = next(iter(self._entries))
                if self._entries[first_key][0] + self.window_seconds > now:
                    break
                self._entries.popitem(last=False)
            for key in keys:
                started, count = self._entries.get(key, (now, 0))
                if count >= self.attempt_limit:
                    raise AppError(
                        429,
                        "LOGIN_RATE_LIMITED",
                        "Demasiados intentos. Espera antes de volver a iniciar sesión.",
                        retry_after=max(1, math.ceil(started + self.window_seconds - now)),
                    )
            new_keys = sum(key not in self._entries for key in keys)
            if len(self._entries) + new_keys > self.max_keys:
                # Rechazar hasta que venza una ventana evita expulsar claves para eludir el límite.
                raise AppError(429, "LOGIN_RATE_LIMITED", "Demasiados intentos. Inténtalo más tarde.", retry_after=self.window_seconds)
            for key in keys:
                started, count = self._entries.get(key, (now, 0))
                self._entries[key] = (started, count + 1)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
