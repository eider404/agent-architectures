"""TraceHooks: un observador del ciclo de vida del agente. El agente no sabe que existe."""
import json
import time
from strands.hooks import (
    HookProvider, HookRegistry, BeforeInvocationEvent, AfterInvocationEvent,
    BeforeModelCallEvent, AfterModelCallEvent, BeforeToolCallEvent, AfterToolCallEvent,
)


def _short(value, limit: int = 44) -> str:
    """Un valor listo para consola: los numeros crudos, el resto como JSON recortado."""
    if isinstance(value, (int, float)):
        return str(value)
    text = json.dumps(value, ensure_ascii=False)
    return text if len(text) <= limit else text[:limit] + '..."'


class TraceHooks(HookProvider):
    def __init__(self, jsonl_path: str) -> None:
        self.jsonl_path = jsonl_path
        self.seq = 0            # numero de evento, global a la sesion
        self.turn = 0           # numero de invocacion: sube en cada BeforeInvocationEvent
        self.tools = 0          # tools ejecutadas en ESTE turno
        self.totals = (0, 0)    # (ciclos, tokens): las metricas del SDK no se reinician por turno

    # El UNICO punto de contacto con el SDK: seis suscripciones por tipo de evento.
    def register_hooks(self, registry: HookRegistry) -> None:
        registry.add_callback(BeforeInvocationEvent, self.on_invocation_start)
        registry.add_callback(BeforeModelCallEvent, self.on_model_start)
        registry.add_callback(AfterModelCallEvent, self.on_model_end)
        registry.add_callback(BeforeToolCallEvent, self.on_tool_start)
        registry.add_callback(AfterToolCallEvent, self.on_tool_end)
        registry.add_callback(AfterInvocationEvent, self.on_invocation_end)

    # Un solo punto de emision: cambiar de destino, o enmascarar datos, es tocar solo esto.
    def _emit(self, event: str, **fields) -> None:
        self.seq += 1
        record = {"seq": self.seq, "ts": time.time(), "turn": self.turn, "event": event, **fields}
        with open(self.jsonl_path, "a") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        # El JSONL guarda el valor entero; la consola lo recorta y envuelve a 100 columnas.
        head = f"[trace] {self.seq:03d} turn={self.turn} {event:<18} "
        line = head
        for part in (f"{k}={_short(v)}" for k, v in fields.items()):
            if len(line) + len(part) > 100:
                print(line.rstrip())
                line = " " * len(head)
            line += part + "  "
        print(line.rstrip())

    def on_invocation_start(self, event: BeforeInvocationEvent) -> None:
        # No existe un campo 'prompt': el texto del usuario viaja dentro de event.messages.
        text = event.messages[-1]["content"][0].get("text", "") if event.messages else ""
        self.turn += 1
        self.tools = 0
        self._emit("before_invocation", prompt=text)

    def on_model_start(self, event: BeforeModelCallEvent) -> None:
        self._emit("before_model_call", messages=len(event.agent.messages))

    def on_model_end(self, event: AfterModelCallEvent) -> None:
        self._emit("after_model_call",
                   stop_reason=event.stop_response.stop_reason if event.stop_response else "error")

    def on_tool_start(self, event: BeforeToolCallEvent) -> None:
        self._emit("before_tool_call", tool=event.tool_use["name"], input=event.tool_use["input"])

    def on_tool_end(self, event: AfterToolCallEvent) -> None:
        # duration lo mide el SDK; cronometrar entre callbacks incluiria a los demas hooks.
        self.tools += 1
        self._emit("after_tool_call", tool=event.tool_use["name"], status=event.result["status"],
                   duration_ms=round((event.duration or 0.0) * 1000, 2),
                   result=event.result["content"][0].get("text", ""))

    def on_invocation_end(self, event: AfterInvocationEvent) -> None:
        # result es None si la invocacion no completo; y las metricas del SDK son ACUMULADAS,
        # asi que el resumen de ESTE turno es la diferencia contra el turno anterior.
        metrics = event.result.metrics if event.result else None
        if metrics is None:
            return self._emit("after_invocation", result="none")
        totals = (metrics.cycle_count, metrics.accumulated_usage["totalTokens"])
        self._emit("after_invocation", cycles=totals[0] - self.totals[0], tools=self.tools,
                   tokens=totals[1] - self.totals[1])
        self.totals = totals
