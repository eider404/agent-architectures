"""TracePlugin: un observador del ciclo de vida del agente. El agente no sabe que existe."""
import json
import time

from google.adk.plugins.base_plugin import BasePlugin


def _short(value, limit: int = 44) -> str:
    """Un valor listo para consola: los numeros crudos, el resto como JSON recortado."""
    if isinstance(value, (int, float)):
        return str(value)
    text = json.dumps(value, ensure_ascii=False, default=str)
    return text if len(text) <= limit else text[:limit] + '..."'


class TracePlugin(BasePlugin):
    def __init__(self, jsonl_path: str) -> None:
        super().__init__(name="trace")
        self.jsonl_path = jsonl_path
        self.seq = 0            # numero de evento, global al proceso
        self.turn = 0           # numero de invocacion: sube en cada before_run
        self.cycles = self.tools = self.tokens = 0   # contadores de ESTE turno
        self.started = {}       # function_call_id -> hora de arranque de la tool

    # Un solo punto de emision: cambiar de destino, o enmascarar datos, es tocar solo esto.
    def _emit(self, event: str, **fields) -> None:
        self.seq += 1
        record = {"seq": self.seq, "ts": time.time(), "turn": self.turn, "event": event, **fields}
        with open(self.jsonl_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
        # El JSONL guarda el valor entero; la consola lo recorta y envuelve a 100 columnas.
        head = f"[trace] {self.seq:03d} turn={self.turn} {event:<18} "
        line = head
        for part in (f"{k}={_short(v)}" for k, v in fields.items()):
            if len(line) + len(part) > 100:
                print(line.rstrip())
                line = " " * len(head)
            line += part + "  "
        print(line.rstrip())

    # Los callbacks son el UNICO contacto con el SDK. Devolver None = observar sin intervenir.
    async def before_run_callback(self, *, invocation_context):
        self.turn += 1
        self.cycles = self.tools = self.tokens = 0
        content = invocation_context.user_content
        self._emit("before_invocation", prompt=content.parts[0].text if content else "")

    async def before_model_callback(self, *, callback_context, llm_request):
        self._emit("before_model_call", messages=len(llm_request.contents))

    async def after_model_callback(self, *, callback_context, llm_response):
        if llm_response.partial:
            return
        self.cycles += 1
        if usage := llm_response.usage_metadata:
            self.tokens += usage.total_token_count or 0
        parts = (llm_response.content and llm_response.content.parts) or []
        # ADK no distingue "paro para usar una tool": se deduce del contenido.
        reason = "tool_use" if any(p.function_call for p in parts) else "end_turn"
        self._emit("after_model_call", stop_reason="error" if llm_response.error_code else reason)

    async def before_tool_callback(self, *, tool, tool_args, tool_context):
        self._emit("before_tool_call", tool=tool.name, input=tool_args)
        self.started[tool_context.function_call_id] = time.perf_counter()

    def _tool_end(self, tool, tool_context, status: str, result) -> None:
        started = self.started.pop(tool_context.function_call_id, time.perf_counter())
        self.tools += 1
        self._emit("after_tool_call", tool=tool.name, status=status,
                   duration_ms=round((time.perf_counter() - started) * 1000, 2), result=result)

    async def after_tool_callback(self, *, tool, tool_args, tool_context, result):
        self._tool_end(tool, tool_context, "success", result)

    # Si la tool o la corrida lanzan una excepcion, ADK avisa por un callback aparte.
    async def on_tool_error_callback(self, *, tool, tool_args, tool_context, error):
        self._tool_end(tool, tool_context, "error", str(error))

    async def after_run_callback(self, *, invocation_context):
        self._emit("after_invocation", cycles=self.cycles, tools=self.tools, tokens=self.tokens)

    async def on_run_error_callback(self, *, invocation_context, error):
        self._emit("after_invocation", result="none")
