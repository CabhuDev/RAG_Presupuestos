"""
Store de sesiones en memoria para conversaciones RAG.
Gestiona el historial de mensajes por sesión con TTL automático.

Diseño deliberadamente simple (in-memory):
- El historial se pierde al reiniciar el servidor.
- No requiere base de datos ni migraciones adicionales.
- Apropiado para uso single-user o equipos pequeños.
- Los métodos son síncronos y se usan dentro de un único event loop,
  por lo que no requieren locks adicionales.
"""
import time
from typing import Optional

# Configuración
_MAX_MESSAGES_PER_SESSION = 20   # Máximo de mensajes (user + assistant) por sesión
_MAX_HISTORY_IN_PROMPT = 12      # Últimos N mensajes que se incluyen en el prompt
_SESSION_TTL_SECONDS = 7200      # 2 horas de inactividad → sesión expirada
_MAX_SESSIONS = 500              # Límite global para prevenir consumo excesivo de RAM


class SessionStore:
    """
    Store in-memory para historial de conversaciones.
    Los métodos son síncronos y se invocan dentro del event loop de FastAPI.
    """

    def __init__(self):
        self._store: dict[str, dict] = {}

    def get_history(self, session_id: str) -> list[dict]:
        """
        Obtiene el historial de una sesión.
        Devuelve los últimos _MAX_HISTORY_IN_PROMPT mensajes para no saturar el contexto.

        Args:
            session_id: ID de la sesión.

        Returns:
            Lista de mensajes {"role": "user"|"assistant", "content": str}.
        """
        session = self._store.get(session_id)
        if not session:
            return []

        # Actualizar último acceso
        session["last_access"] = time.time()

        messages = session.get("messages", [])
        # Devolver solo los últimos N mensajes
        return messages[-_MAX_HISTORY_IN_PROMPT:]

    def add_exchange(self, session_id: str, user_message: str, assistant_message: str) -> None:
        """
        Añade un intercambio (user + assistant) al historial de la sesión.
        Crea la sesión si no existe. Limpia sesiones expiradas en cada escritura.

        Args:
            session_id: ID de la sesión.
            user_message: Mensaje del usuario.
            assistant_message: Respuesta del asistente.
        """
        now = time.time()

        # Limpieza lazy de sesiones expiradas
        self._cleanup_expired(now)

        if session_id not in self._store:
            # Verificar límite global de sesiones
            if len(self._store) >= _MAX_SESSIONS:
                # Eliminar la sesión más antigua
                oldest_id = min(
                    self._store.keys(),
                    key=lambda k: self._store[k]["last_access"]
                )
                del self._store[oldest_id]

            self._store[session_id] = {
                "messages": [],
                "last_access": now,
                "created_at": now,
            }

        session = self._store[session_id]
        session["last_access"] = now

        messages = session["messages"]
        messages.append({"role": "user", "content": user_message})
        messages.append({"role": "assistant", "content": assistant_message})

        # Mantener solo los últimos _MAX_MESSAGES_PER_SESSION mensajes
        if len(messages) > _MAX_MESSAGES_PER_SESSION:
            session["messages"] = messages[-_MAX_MESSAGES_PER_SESSION:]

    def clear_session(self, session_id: str) -> bool:
        """
        Elimina una sesión del store.

        Args:
            session_id: ID de la sesión a eliminar.

        Returns:
            True si existía y fue eliminada, False si no existía.
        """
        if session_id in self._store:
            del self._store[session_id]
            return True
        return False

    def get_stats(self) -> dict:
        """Devuelve estadísticas del store para monitorización."""
        now = time.time()
        active = sum(
            1 for s in self._store.values()
            if now - s["last_access"] < _SESSION_TTL_SECONDS
        )
        return {
            "total_sessions": len(self._store),
            "active_sessions": active,
            "max_sessions": _MAX_SESSIONS,
            "session_ttl_hours": _SESSION_TTL_SECONDS / 3600,
        }

    def _cleanup_expired(self, now: float) -> None:
        """Elimina sesiones cuyo TTL ha expirado (limpieza lazy)."""
        expired = [
            sid for sid, data in self._store.items()
            if now - data["last_access"] > _SESSION_TTL_SECONDS
        ]
        for sid in expired:
            del self._store[sid]


# Instancia singleton del store
_session_store: Optional[SessionStore] = None


def get_session_store() -> SessionStore:
    """Retorna la instancia singleton del SessionStore."""
    global _session_store
    if _session_store is None:
        _session_store = SessionStore()
    return _session_store
