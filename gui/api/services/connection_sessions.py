from __future__ import annotations

import secrets
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field

from oracle_relationship_discovery.models import SchemaSummary


@dataclass(slots=True)
class RuntimeCredentials:
    host: str
    port: int
    service_name: str
    username: str
    _password: bytearray = field(repr=False)

    @classmethod
    def create(
        cls,
        *,
        host: str,
        port: int,
        service_name: str,
        username: str,
        password: str,
    ) -> RuntimeCredentials:
        return cls(host, port, service_name, username, bytearray(password.encode("utf-8")))

    def password_text(self) -> str:
        if not self._password:
            raise RuntimeError("Connection credentials have been cleared")
        return self._password.decode("utf-8")

    def clear(self) -> None:
        for index in range(len(self._password)):
            self._password[index] = 0
        self._password.clear()

    @property
    def is_cleared(self) -> bool:
        return not self._password


@dataclass(slots=True)
class RuntimeConnectionSession:
    connection_id: str
    schemas: tuple[SchemaSummary, ...]
    created_at: float
    last_accessed_at: float


class SessionNotFoundError(LookupError):
    pass


class ConnectionSessionStore:
    def __init__(
        self,
        *,
        idle_timeout_seconds: int = 900,
        max_sessions: int = 16,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if idle_timeout_seconds <= 0 or max_sessions <= 0:
            raise ValueError("Session limits must be greater than zero")
        self.idle_timeout_seconds = idle_timeout_seconds
        self.max_sessions = max_sessions
        self._clock = clock
        self._sessions: dict[str, RuntimeConnectionSession] = {}
        self._lock = threading.RLock()

    def create(
        self,
        schemas: tuple[SchemaSummary, ...],
        *,
        replace_connection_id: str | None = None,
    ) -> RuntimeConnectionSession:
        with self._lock:
            now = self._clock()
            self._cleanup_expired_locked(now)
            if replace_connection_id:
                self._remove_locked(replace_connection_id)
            while len(self._sessions) >= self.max_sessions:
                oldest = min(self._sessions.values(), key=lambda item: item.last_accessed_at)
                self._remove_locked(oldest.connection_id)
            connection_id = self._new_id()
            session = RuntimeConnectionSession(connection_id, schemas, now, now)
            self._sessions[connection_id] = session
            return session

    def get(self, connection_id: str) -> RuntimeConnectionSession:
        with self._lock:
            now = self._clock()
            self._cleanup_expired_locked(now)
            session = self._sessions.get(connection_id)
            if session is None:
                raise SessionNotFoundError(connection_id)
            session.last_accessed_at = now
            return session

    def delete(self, connection_id: str) -> bool:
        with self._lock:
            self._cleanup_expired_locked(self._clock())
            return self._remove_locked(connection_id)

    def cleanup_expired(self) -> int:
        with self._lock:
            return self._cleanup_expired_locked(self._clock())

    def clear(self) -> None:
        with self._lock:
            for connection_id in tuple(self._sessions):
                self._remove_locked(connection_id)

    def _cleanup_expired_locked(self, now: float) -> int:
        expired = [
            item.connection_id
            for item in self._sessions.values()
            if now - item.last_accessed_at >= self.idle_timeout_seconds
        ]
        for connection_id in expired:
            self._remove_locked(connection_id)
        return len(expired)

    def _remove_locked(self, connection_id: str) -> bool:
        return self._sessions.pop(connection_id, None) is not None

    def _new_id(self) -> str:
        while True:
            connection_id = secrets.token_urlsafe(32)
            if connection_id not in self._sessions:
                return connection_id
