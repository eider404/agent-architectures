import json
import sqlite3
from typing import Any

from strands.session import RepositorySessionManager, SessionRepository
from strands.types.session import Session, SessionAgent, SessionMessage

# Tres tablas, una por entidad del contrato. El objeto entero viaja como JSON en 'data':
# los dataclasses del SDK ya traen to_dict()/from_dict(), asi que no hay esquema que mantener.
SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (session_id TEXT PRIMARY KEY, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS agents (session_id TEXT, agent_id TEXT, data TEXT NOT NULL,
    PRIMARY KEY (session_id, agent_id));
CREATE TABLE IF NOT EXISTS messages (session_id TEXT, agent_id TEXT, message_id INTEGER,
    data TEXT NOT NULL, PRIMARY KEY (session_id, agent_id, message_id));
"""


class SqliteSessionManager(RepositorySessionManager, SessionRepository):
    """Igual que FileSessionManager, pero una base SQLite en vez de un arbol de JSON."""

    def __init__(self, session_id: str, db_path: str = "sessions.db", **kwargs: Any):
        self.db = sqlite3.connect(db_path, check_same_thread=False)
        self.db.executescript(SCHEMA)
        super().__init__(session_id=session_id, session_repository=self)

    # Ayudantes: escribir una fila y leer una fila. Todo lo demas son nueve envoltorios.
    def _write(self, sql: str, params: tuple) -> None:
        self.db.execute(sql, params)
        self.db.commit()

    def _read(self, sql: str, params: tuple):
        row = self.db.execute(sql, params).fetchone()
        return json.loads(row[0]) if row else None

    def create_session(self, session: Session, **kwargs: Any) -> Session:
        self._write("INSERT INTO sessions VALUES (?, ?)",
                    (session.session_id, json.dumps(session.to_dict())))
        return session

    def read_session(self, session_id: str, **kwargs: Any):
        data = self._read("SELECT data FROM sessions WHERE session_id = ?", (session_id,))
        return Session.from_dict(data) if data else None

    def create_agent(self, session_id: str, session_agent: SessionAgent, **kwargs: Any) -> None:
        self._write("INSERT INTO agents VALUES (?, ?, ?)",
                    (session_id, session_agent.agent_id, json.dumps(session_agent.to_dict())))

    def read_agent(self, session_id: str, agent_id: str, **kwargs: Any):
        data = self._read("SELECT data FROM agents WHERE session_id = ? AND agent_id = ?",
                          (session_id, agent_id))
        return SessionAgent.from_dict(data) if data else None

    def update_agent(self, session_id: str, session_agent: SessionAgent, **kwargs: Any) -> None:
        self._write("UPDATE agents SET data = ? WHERE session_id = ? AND agent_id = ?",
                    (json.dumps(session_agent.to_dict()), session_id, session_agent.agent_id))

    def create_message(self, session_id: str, agent_id: str, session_message: SessionMessage, **kwargs: Any) -> None:
        self._write("INSERT INTO messages VALUES (?, ?, ?, ?)",
                    (session_id, agent_id, session_message.message_id,
                     json.dumps(session_message.to_dict())))

    def read_message(self, session_id: str, agent_id: str, message_id: int, **kwargs: Any):
        data = self._read(
            "SELECT data FROM messages WHERE session_id = ? AND agent_id = ? AND message_id = ?",
            (session_id, agent_id, message_id))
        return SessionMessage.from_dict(data) if data else None

    def update_message(self, session_id: str, agent_id: str, session_message: SessionMessage, **kwargs: Any) -> None:
        self._write(
            "UPDATE messages SET data = ? WHERE session_id = ? AND agent_id = ? AND message_id = ?",
            (json.dumps(session_message.to_dict()), session_id, agent_id, session_message.message_id))

    def list_messages(self, session_id: str, agent_id: str, limit: int | None = None, offset: int = 0,
                      **kwargs: Any) -> list[SessionMessage]:
        rows = self.db.execute(
            "SELECT data FROM messages WHERE session_id = ? AND agent_id = ? ORDER BY message_id LIMIT ? OFFSET ?",
            (session_id, agent_id, limit if limit is not None else -1, offset)).fetchall()
        return [SessionMessage.from_dict(json.loads(r[0])) for r in rows]
