# 10 · Agente observable

`09` cambió el eje de `01` de *"qué hace el agente"* a *"qué sobrevive al reinicio"*. `10` abre el
segundo ejemplo del arco de infraestructura y cambia el eje otra vez: no qué persiste, sino **qué
pasó durante el turno**. Vuelve a un agente único con herramientas, como `01`, y la comparación es
literal:

```python
# 01-09: el agente no deja rastro de su propio ciclo de vida
agent = Agent(model=..., system_prompt=..., tools=[...])

# 10: la misma llamada, mas una linea
agent = Agent(model=..., system_prompt=..., tools=[...], hooks=[TraceHooks(jsonl_path=TRACE_PATH)])
```

No hay un solo `print()` metido dentro de una `@tool` ni del bucle CLI. Todo el rastro sale de un
observador externo que se engancha al ciclo de vida del agente sin que el agente sepa que existe:

```
grep -n print agent.py   → solo las 3 líneas de la cabecera de la CLI y la del bucle
grep -c "@tool" agent.py → 3
```

## Descripción

Concierge es un asistente de reservas de un hotel (`check_availability`, `book_room`,
`cancel_booking`) con **tres** `@tool`, igual de simple que `01`. Lo que enseña el ejemplo no es el
dominio, sino `observability.py`: un `HookProvider` propio, `TraceHooks`, que se suscribe a seis
eventos del ciclo de vida del agente y escribe cada uno en dos salidas — consola (recortada, legible)
y `trace.jsonl` (completo, para `jq`).

Un segundo eje, bajo el flag `--otel`, conecta un exportador a las trazas de OpenTelemetry que el SDK
**ya venía emitiendo desde `01`** y que nadie escuchaba: `TraceHooks` es instrumentación que
escribimos nosotros; `--otel` es instrumentación que Strands trae de fábrica y solo hay que exportar.

| Arranque | Qué añade |
|---|---|
| `python agent.py` | El log de seis eventos, consola + `trace.jsonl` |
| `python agent.py --otel` | Además, los spans OTel del SDK por consola (JSON) |

## Cómo Funciona

### Detalles del ejemplo

| Información | Detalles |
|---|---|
| **Características de Strands** | `strands.hooks` (`HookProvider`, `HookRegistry`, `add_callback`) + `strands.telemetry.StrandsTelemetry` |
| **Patrón de agente** | Agente único con observabilidad externa al ciclo de vida |
| **Herramientas** | 3 (`check_availability`, `book_room`, `cancel_booking`) |
| **Modelo** | `gpt-5.4-mini` por la API directa de OpenAI (configurable con `MODEL_ID`) |
| **Archivos de código** | 2: `agent.py` (96 líneas) + `observability.py` (84 líneas) |
| **Dependencias nuevas** | **Cero**: `requirements.txt` es idéntico al de `09` — `opentelemetry-sdk` ya entraba como dependencia transitiva de `strands-agents` |

### El orden real de los diez eventos

Instrumentados los diez eventos de agente único (modelo falso, sin red, sin credencial):

```
  AgentInitializedEvent                                    <- al construir el Agent
--- invocacion 1: con tool ---
  BeforeInvocationEvent      messages=[...'reserva...'] agent.messages=0
  MessageAddedEvent          role=user
  BeforeModelCallEvent       n_messages=1 projected=250
  AfterModelCallEvent        stop_reason=tool_use exception=None
  MessageAddedEvent          role=assistant
  BeforeToolsEvent
  BeforeToolCallEvent        tool=book_room input={"date": "2026-10-04", "guest": "Ada"}
  AfterToolCallEvent         tool=book_room status=success duration=0.0006...
  AfterToolsEvent
  MessageAddedEvent          role=user                     <- el RESULTADO de la tool (trampa 2)
  BeforeModelCallEvent       n_messages=3 projected=129
  AfterModelCallEvent        stop_reason=end_turn exception=None
  MessageAddedEvent          role=assistant
  AfterInvocationEvent       cycles=2 tools={'book_room': 1} usage={'totalTokens': 240}
```

`TraceHooks` registra **seis** de esos diez, no los diez:

| Evento que SÍ se registra | Por qué |
|---|---|
| `BeforeInvocationEvent` | Marca el inicio del turno y trae el prompt del usuario |
| `BeforeModelCallEvent` / `AfterModelCallEvent` | El motivo por el que el modelo paró (`tool_use` / `end_turn`) |
| `BeforeToolCallEvent` / `AfterToolCallEvent` | Qué tool, con qué input, con qué resultado y en cuánto tiempo |
| `AfterInvocationEvent` | El resumen del turno: ciclos, tools, tokens |

| Evento que NO se registra | Por qué se deja fuera |
|---|---|
| `AgentInitializedEvent` | Dispara una sola vez, al construir el agente — no es parte de un turno |
| `MessageAddedEvent` (×2-4 por turno) | Redundante con `Before/AfterModelCallEvent` y `Before/AfterToolCallEvent`: cada mensaje que añade ya quedó registrado por el evento que lo causó |
| `BeforeToolsEvent` / `AfterToolsEvent` | Envuelven el lote completo de tool calls de un ciclo; con una sola tool por ciclo en este ejemplo no aportan nada que `BeforeToolCallEvent`/`AfterToolCallEvent` no digan ya |

Seis suscripciones, no diez: menos ruido en la consola sin perder ninguna de las tres preguntas que
importan (*qué se llamó, cuánto costó, cómo terminó el turno*).

### Qué NO se ve en el log

- **El razonamiento del modelo.** `AfterModelCallEvent` trae `stop_reason`, no el porqué.
- **El cuerpo HTTP de la llamada a OpenAI.** El log vive en el hook, un nivel por encima del cliente
  `openai`; para eso está `--otel`, que sí expone `gen_ai.request.model` y los tokens, pero tampoco
  las cabeceras ni la petición cruda.
- **El interior de una `@tool`.** `AfterToolCallEvent` ve el input y el `result` que la tool devolvió,
  no las líneas que ejecutó para llegar ahí.
- **Los tokens en streaming.** El SDK entrega la respuesta completa a `AfterModelCallEvent`; no hay
  un evento por chunk.

### Las cinco trampas, medidas

**1. El `callback_handler` por defecto ya imprimía.** Por defecto, `Agent` usa
`PrintingCallbackHandler`, y su salida sale intercalada con la nuestra, en la misma línea:

```
[trace] BeforeModelCallEvent

Tool #1: book_room
[trace] AfterModelCallEvent
[trace] BeforeToolCallEvent
[trace] AfterToolCallEvent
[trace] BeforeModelCallEvent
Reservado.[trace] AfterModelCallEvent
```

`agent.py` pasa `callback_handler=None` (→ `null_callback_handler`) precisamente para apagarlo: sin
esa línea, el log queda limpio y es el propio `[trace]` el que decide qué se ve.

**2. El resultado de la tool entra como `role=user`.** Tras `AfterToolCallEvent` hay un
`MessageAddedEvent role=user`: el SDK le devuelve el resultado de la tool al modelo como si fuera un
mensaje del usuario. No es un bug del hook — es cómo Strands arma la siguiente llamada al modelo.

**3. `status=success` no es éxito de negocio.** Cuando una tool **devuelve** un error como string
(`"Unknown booking code: 'ZZZ-0000'."`), `AfterToolCallEvent` trae `status=success`,
`exception=None`: el SDK considera la llamada exitosa porque la función no lanzó. Si la tool
**lanza** de verdad, ahí sí: `status=error`, `exception=ValueError(...)`. Medido con las dos
tools reales:

```
status = error
exception = ValueError('la tool exploto')
content = [{'text': 'Error: la tool exploto'}]
```

`status` mide si la llamada Python completó, no si el negocio salió bien. `on_tool_end` en
`observability.py` registra `status` tal cual llega del SDK — leer el `result` es lo que distingue
un error de negocio de uno de infraestructura.

**4. `duration` ya viene medido.** `AfterToolCallEvent.duration` es un `float` poblado por el SDK
(`duration=0.00060...`); no hace falta cronometrar nada a mano en el hook — hacerlo incluiría además
el tiempo de los demás callbacks.

**5. El tracing OTel corre siempre; falta el exportador.** Sin `--otel`, `trace.get_tracer_provider()`
devuelve un `ProxyTracerProvider` y los spans son `NonRecordingSpan` (`is_recording() == False`): el
SDK ya está creando spans en cada turno desde `01`, simplemente nadie los exporta. Con
`StrandsTelemetry().setup_console_exporter()`: `TracerProvider` real y **6 spans** por turno con tool
(`chat`, `execute_tool <nombre>`, `execute_event_loop_cycle` ×2, `chat`,
`invoke_agent Strands Agents`). Sus eventos internos incluyen `gen_ai.user.message`,
`gen_ai.tool.message` y `gen_ai.choice`: **el contenido de la conversación acaba en stdout** — ver la
nota de seguridad más abajo.

### Los dos hallazgos que corrigen la exploración inicial

- **`BeforeInvocationEvent` no tiene campo `prompt`.** Trae `messages`, `invocation_state`, `cancel`.
  El texto del usuario se extrae así:

  ```python
  text = event.messages[-1]["content"][0].get("text", "") if event.messages else ""
  ```

- **Las métricas de `AfterInvocationEvent` son acumuladas de la sesión, no del turno.**
  `EventLoopMetrics` no se reinicia entre invocaciones: en tres turnos seguidos, `cycle_count` fue
  `2 → 3 → 5` y `accumulated_usage["totalTokens"]` fue `240 → 360 → 600`. Un log ingenuo diría que el
  turno 3 (una sola pasada, sin tools) tuvo 5 ciclos. `on_invocation_end` guarda `self.totals` y
  reporta la **diferencia** contra el turno anterior — por eso la transcripción real de abajo muestra
  `cycles=2 tools=1 tokens=624` en el turno 1 y no una cifra creciente en los siguientes.

### Las diferencias con `01`

| | `01-basic-tool-agent` | `10-observable-agent` |
|---|---|---|
| Llamada a `Agent(...)` | `model`, `system_prompt`, `tools` | `model`, `system_prompt`, `tools`, **`hooks`**, `callback_handler=None` |
| Herramientas | 2 (`@tool`) | 3 (`@tool`) |
| Archivos de código | 1 (`agent.py`) | 2: `agent.py` (96 líneas) + `observability.py` (84 líneas) |
| Escribe en disco | No | Sí: `trace.jsonl`, junto a `agent.py`, y solo al invocar — nunca al importar |
| Dependencias | 3 | Las mismas 3 |

## Configuración y Pruebas

### Prerrequisitos

- Python 3.10 o superior
- Una `OPENAI_API_KEY` en un `.env` local
- **Sin AWS** y **sin Node.js**
- `requirements.txt` es **idéntico al de `09`** (`diff` sin salida): la observabilidad no cuesta una
  dependencia nueva — `opentelemetry-sdk` ya entraba de forma transitiva con `strands-agents`

### Cómo ejecutarlo

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt   # solo la primera vez
cp .env.example .env            # y pon tu clave real en el .env

.venv/bin/python agent.py             # 1. el log de seis eventos, consola + trace.jsonl
.venv/bin/python agent.py --otel      # 2. ademas, los seis spans OTel por consola
```

| Variable | Descripción |
|---|---|
| `OPENAI_API_KEY` | Tu clave de OpenAI. La lee el cliente de `openai` por su cuenta; ninguna línea de código la menciona |
| `MODEL_ID` | Modelo a usar. Por defecto `gpt-5.4-mini` |

> **Borrar la instrumentación es borrar una línea.** Quitando `hooks=[TraceHooks(...)]` (y su import)
> de `agent.py`, el agente sigue funcionando exactamente igual y `trace.jsonl` deja de crearse.
> Probado sobre una copia: import limpio, las tres tools responden, cero rastro en disco.

### Transcripción de ejemplo

Corrida **real** contra `gpt-5.4-nano` (vía `MODEL_ID` en `.env`), en un solo proceso, tres turnos:

```
Concierge: Hotel Kraken bookings. Type 'exit' to quit.

Using LLM model: gpt-5.4-nano
Trace: .../10-observable-agent/trace.jsonl

You > hay sitio el 4 de octubre?
[trace] 001 turn=1 before_invocation  prompt="hay sitio el 4 de octubre?"
[trace] 002 turn=1 before_model_call  messages=1
[trace] 003 turn=1 after_model_call   stop_reason="tool_use"
[trace] 004 turn=1 before_tool_call   tool="check_availability"  input={"date": "2026-10-04"}
[trace] 005 turn=1 after_tool_call    tool="check_availability"  status="success"  duration_ms=0.34
                                      result="7 rooms free on 2026-10-04."
[trace] 006 turn=1 before_model_call  messages=3
[trace] 007 turn=1 after_model_call   stop_reason="end_turn"
[trace] 008 turn=1 after_invocation   cycles=2  tools=1  tokens=624

Concierge > Sí, hay sitio el **4 de octubre de 2026** (quedan **7 habitaciones libres**). ¿Quieres que reserve para alguien en concreto? Dime el **nombre** del huésped.

You > cancela la reserva ZZZ-0000
[trace] 009 turn=2 before_invocation  prompt="cancela la reserva ZZZ-0000"
[trace] 010 turn=2 before_model_call  messages=5
[trace] 011 turn=2 after_model_call   stop_reason="tool_use"
[trace] 012 turn=2 before_tool_call   tool="cancel_booking"  input={"code": "ZZZ-0000"}
[trace] 013 turn=2 after_tool_call    tool="cancel_booking"  status="success"  duration_ms=0.43
                                      result="Unknown booking code: 'ZZZ-0000'."
[trace] 014 turn=2 before_model_call  messages=7
[trace] 015 turn=2 after_model_call   stop_reason="end_turn"
[trace] 016 turn=2 after_invocation   cycles=2  tools=1  tokens=820

Concierge > No puedo cancelarla: **el código de reserva ZZZ-0000 no existe** (o no es válido).

You > que eres?
[trace] 017 turn=3 before_invocation  prompt="que eres?"
[trace] 018 turn=3 before_model_call  messages=9
[trace] 019 turn=3 after_model_call   stop_reason="end_turn"
[trace] 020 turn=3 after_invocation   cycles=1  tools=0  tokens=488

Concierge > Soy **la Concierge (asistente de reservas) del Hotel Kraken**. Ayudo a **comprobar disponibilidad**, **hacer reservas** y **cancelar reservas** usando los sistemas del hotel.
```

Nótese el turno 3: `cycles=1 tools=0`, no una cifra acumulada creciendo — el Hallazgo 2 aplicado.

Fragmento real de `trace.jsonl` (una línea de las veinte, JSON válido en cada una,
`jq -e . trace.jsonl` → `OK`):

```json
{"seq": 5, "ts": 1789453369.0717711, "turn": 1, "event": "after_tool_call", "tool": "check_availability", "status": "success", "duration_ms": 0.34, "result": "7 rooms free on 2026-10-04."}
```

Un span OTel real de la corrida con `--otel` (`execute_tool check_availability`, recortado):

```json
{
    "name": "execute_tool check_availability",
    "kind": "SpanKind.INTERNAL",
    "attributes": {
        "gen_ai.operation.name": "execute_tool",
        "gen_ai.tool.name": "check_availability",
        "gen_ai.tool.call.id": "call_2qJSkijC4md4zKHGmHv3B1de",
        "gen_ai.tool.json_schema": "{\"properties\": {\"date\": {...}}, \"required\": [\"date\"], \"type\": \"object\"}",
        "gen_ai.tool.status": "success"
    },
    "events": [
        {"name": "gen_ai.tool.message", "attributes": {"content": "{\"date\": \"2026-10-04\"}", ...}},
        {"name": "gen_ai.choice", "attributes": {"message": "[{\"text\": \"7 rooms free on 2026-10-04.\"}]", ...}}
    ]
}
```

Los seis spans reales de ese turno, en orden de cierre: `chat`, `execute_tool check_availability`,
`execute_event_loop_cycle`, `chat`, `execute_event_loop_cycle`, `invoke_agent Strands Agents`.

## Información Adicional

**`trace.jsonl` guarda el turno en claro.** Igual que `sessions/` en `09`, cada línea trae el prompt
del usuario y el resultado de cada tool sin cifrar. `_emit()`, en `observability.py`, es el único
punto de escritura del archivo — y por tanto el único lugar donde habría que enmascarar datos
sensibles si este ejemplo fuera a producción. `--otel` es peor en este sentido: los seis spans llevan
el contenido íntegro de la conversación en `gen_ai.user.message` / `gen_ai.choice`, así que
`*.jsonl` está en el `.gitignore` de la raíz y `--otel` queda detrás de un flag explícito, nunca
encendido por defecto.

**`requirements.txt` es idéntico al de `09`.** La observabilidad de este ejemplo no cuesta una
dependencia: `HookProvider`/`HookRegistry` son parte de `strands-agents`, y `opentelemetry-sdk` ya
entraba de forma transitiva — solo hacía falta escucharlo.

**Pasar a un backend real de trazas** es cambiar una línea: `StrandsTelemetry().setup_console_exporter()`
por `StrandsTelemetry().setup_otlp_exporter()`, apuntando a un colector OTLP (Jaeger, Honeycomb,
Datadog...). El resto — los seis spans, sus atributos `gen_ai.*` — no cambia.

**Corrección de rango de código fuente.** La exploración de este plan citaba
`strands/agent/agent.py:556-561` para el registro de `hooks=`; en la versión instalada (1.55.1) el
rango real es **557-565**, y el registro usa `isinstance(hook, HookProvider)` sobre un `Protocol`
`runtime_checkable`, no un chequeo de atributo `hasattr(hook, "register_hooks")`.

**Lo que sigue.** `10` observa un único agente con hooks propios. `11` cierra el arco con el bucle
autónomo; `12`, la evaluación.

### Estructura del proyecto

```
10-observable-agent/
├── agent.py            # constantes + 3 @tool + Agent(hooks=...) + CLI (96 líneas)
├── observability.py    # TraceHooks: HookProvider, 6 add_callback, un punto de emision (84 líneas)
├── requirements.txt    # 3 líneas — idéntico al de 09
├── .env.example        # 2 variables
├── README.md           # este archivo
├── .env                # tu clave; ignorado por git, no se commitea
└── trace.jsonl          # el rastro de cada corrida; ignorado por git (*.jsonl)
```

### Limpieza

```bash
rm -f trace.jsonl    # borra el rastro
rm -rf .venv          # borra el entorno
```

### Recursos adicionales

- [Strands Agents — documentación](https://strandsagents.com/)
- [Hooks en Strands](https://strandsagents.com/latest/documentation/docs/user-guide/concepts/agents/hooks/)
  — `HookProvider`, `HookRegistry`, los eventos del ciclo de vida
- [Observabilidad en Strands](https://strandsagents.com/latest/documentation/docs/user-guide/observability/)
  — OpenTelemetry, `StrandsTelemetry`, métricas y trazas
- [Modelos de OpenAI en Strands](https://strandsagents.com/latest/documentation/docs/user-guide/concepts/model-providers/openai/)
