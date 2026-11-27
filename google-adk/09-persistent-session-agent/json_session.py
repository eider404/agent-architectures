import uuid
from pathlib import Path

from google.adk.sessions import BaseSessionService, Session
from google.adk.sessions.base_session_service import ListSessionsResponse


class JsonSessionService(BaseSessionService):
    """Un archivo JSON por sesion. ADK no trae este almacen: se implementa su contrato.

    Version didactica: ignora el filtro 'config' y no reparte estado 'app:' ni 'user:'.
    """

    def __init__(self, storage_dir: str):
        self.root = Path(storage_dir)

    # Ayudantes: donde vive una sesion y como se escribe. Session es un modelo Pydantic.
    def _path(self, app_name: str, user_id: str, session_id: str) -> Path:
        return self.root / app_name / user_id / f"{session_id}.json"

    def _save(self, session: Session) -> None:
        path = self._path(session.app_name, session.user_id, session.id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(session.model_dump_json(indent=2), encoding="utf-8")

    async def create_session(self, *, app_name, user_id, state=None, session_id=None):
        session = Session(id=session_id or uuid.uuid4().hex, app_name=app_name,
                          user_id=user_id, state=state or {})
        self._save(session)
        return session

    async def get_session(self, *, app_name, user_id, session_id, config=None):
        path = self._path(app_name, user_id, session_id)
        return Session.model_validate_json(path.read_text(encoding="utf-8")) if path.exists() else None

    async def list_sessions(self, *, app_name, user_id=None):
        files = (self.root / app_name).glob(f"{user_id or '*'}/*.json")
        return ListSessionsResponse(
            sessions=[Session.model_validate_json(f.read_text(encoding="utf-8")) for f in files])

    async def delete_session(self, *, app_name, user_id, session_id):
        self._path(app_name, user_id, session_id).unlink(missing_ok=True)

    # El Runner llama aqui con cada mensaje: la clase base lo agrega y nosotros guardamos.
    async def append_event(self, session, event):
        event = await super().append_event(session, event)
        if not event.partial:
            self._save(session)
        return event
