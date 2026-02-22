"""Tests para app/core/session_store.py — Store de sesiones in-memory."""
import time

import pytest

from app.core.session_store import (
    SessionStore,
    _MAX_HISTORY_IN_PROMPT,
    _MAX_MESSAGES_PER_SESSION,
    _SESSION_TTL_SECONDS,
    _MAX_SESSIONS,
)


class TestGetHistory:
    """Tests para SessionStore.get_history()."""

    def test_unknown_session_returns_empty(self, session_store):
        assert session_store.get_history("nonexistent") == []

    def test_returns_messages_after_exchange(self, session_store):
        session_store.add_exchange("s1", "hola", "respuesta")
        history = session_store.get_history("s1")
        assert len(history) == 2
        assert history[0] == {"role": "user", "content": "hola"}
        assert history[1] == {"role": "assistant", "content": "respuesta"}

    def test_truncates_to_max_history_in_prompt(self, session_store):
        # Añadir más mensajes que el límite de prompt
        for i in range(_MAX_HISTORY_IN_PROMPT):
            session_store.add_exchange("s1", f"msg{i}", f"resp{i}")

        history = session_store.get_history("s1")
        # Cada exchange = 2 msgs, max prompt = 12
        assert len(history) == _MAX_HISTORY_IN_PROMPT


class TestAddExchange:
    """Tests para SessionStore.add_exchange()."""

    def test_creates_session_on_first_call(self, session_store):
        session_store.add_exchange("new", "q", "a")
        assert "new" in session_store._store
        assert len(session_store._store["new"]["messages"]) == 2

    def test_appends_to_existing_session(self, session_store):
        session_store.add_exchange("s1", "q1", "a1")
        session_store.add_exchange("s1", "q2", "a2")
        msgs = session_store._store["s1"]["messages"]
        assert len(msgs) == 4

    def test_truncates_messages_at_max(self, session_store):
        # Rellenar hasta superar el límite
        for i in range(_MAX_MESSAGES_PER_SESSION):
            session_store.add_exchange("s1", f"q{i}", f"a{i}")

        msgs = session_store._store["s1"]["messages"]
        assert len(msgs) <= _MAX_MESSAGES_PER_SESSION

    def test_evicts_oldest_session_at_max_sessions(self, session_store):
        now = time.time()
        # Crear exactamente _MAX_SESSIONS sesiones directamente
        # para evitar el overhead de add_exchange y cleanup
        for i in range(_MAX_SESSIONS):
            session_store._store[f"s{i}"] = {
                "messages": [{"role": "user", "content": "q"}, {"role": "assistant", "content": "a"}],
                "last_access": now + i,  # s0 es la más antigua
                "created_at": now + i,
            }

        assert len(session_store._store) == _MAX_SESSIONS

        # Añadir una más → debería evictar s0 (la más antigua)
        session_store.add_exchange("new_session", "q", "a")
        assert "s0" not in session_store._store
        assert "new_session" in session_store._store


class TestClearSession:
    """Tests para SessionStore.clear_session()."""

    def test_returns_true_for_existing(self, session_store):
        session_store.add_exchange("s1", "q", "a")
        assert session_store.clear_session("s1") is True
        assert "s1" not in session_store._store

    def test_returns_false_for_unknown(self, session_store):
        assert session_store.clear_session("nope") is False


class TestGetStats:
    """Tests para SessionStore.get_stats()."""

    def test_empty_store(self, session_store):
        stats = session_store.get_stats()
        assert stats["total_sessions"] == 0
        assert stats["active_sessions"] == 0
        assert stats["max_sessions"] == _MAX_SESSIONS

    def test_with_active_sessions(self, session_store):
        session_store.add_exchange("s1", "q", "a")
        session_store.add_exchange("s2", "q", "a")
        stats = session_store.get_stats()
        assert stats["total_sessions"] == 2
        assert stats["active_sessions"] == 2


class TestTTLCleanup:
    """Tests para limpieza de sesiones expiradas."""

    def test_expired_sessions_cleaned_on_add(self, session_store):
        session_store.add_exchange("old", "q", "a")
        # Forzar expiración manipulando last_access
        session_store._store["old"]["last_access"] = time.time() - _SESSION_TTL_SECONDS - 1

        # El próximo add_exchange debería limpiar la sesión expirada
        session_store.add_exchange("new", "q", "a")
        assert "old" not in session_store._store
        assert "new" in session_store._store

    def test_fresh_sessions_not_cleaned(self, session_store):
        session_store.add_exchange("fresh", "q", "a")
        session_store.add_exchange("another", "q", "a")
        assert "fresh" in session_store._store


class TestSingleton:
    """Test para get_session_store()."""

    def test_returns_same_instance(self):
        from app.core.session_store import get_session_store
        a = get_session_store()
        b = get_session_store()
        assert a is b
