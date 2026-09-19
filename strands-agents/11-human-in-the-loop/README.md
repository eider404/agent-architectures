# 11 · Human-in-the-loop

`10` cerró con esta frase: *"Hooks que intervienen (`cancel_tool`, `retry`, `selected_tool`, `resume`)
convierten al observador en un controlador. Ese salto es `11-human-in-the-loop`"*. Este ejemplo es
exactamente ese salto: el mismo bus de eventos, usado para **detener** la ejecución, no solo para
mirarla.

```python
# 10 — el hook mira y deja pasar todo
class TraceHooks(HookProvider):
    def register_hooks(self, registry): registry.add_callback(AfterToolCallEvent, self.on_tool_end)

# 11 — el hook decide si algo pasa
class ApprovalHook(HookProvider):
    def register_hooks(self, registry): registry.add_callback(BeforeToolCallEvent, self.approve)
```

La frontera no está en la forma (`HookProvider` + `add_callback`), está en el permiso que cada evento
declara:

```python
# hooks/events.py — AfterToolCallEvent (10): solo puede anotar
def _can_write(self, name): return name in ["result"]

# hooks/events.py:231-232 — BeforeToolCallEvent (11): puede CONTROLAR
def _can_write(self, name): return name in ["cancel_tool", "selected_tool", "tool_use"]
```

`10` se suscribía a **seis** eventos para escribir un rastro. `11` se suscribe a **uno**
(`BeforeToolCallEvent`) y usa dos de sus campos escribibles para detener el turno entero:
`event.interrupt(...)` lo pausa, `event.cancel_tool` lo cancela. Ese diff — seis suscripciones de
solo lectura frente a una que controla — es la lección completa.

## Descripción

Mailbot es un asistente de correo con dos `@tool` de riesgo muy distinto: `draft_email` (sin efecto
de lado, nunca interrumpe) y `send_email` (la acción sensible, siempre interrumpe). `send_email` **no
sabe que la vigilan**: no recibe `tool_context`, no tiene una línea de lógica de aprobación dentro de
su cuerpo — es una `@tool` tan simple como `check_availability` en `10`. Toda la intervención vive en
`approval.py`, 20 líneas.

Antes de que el cuerpo de `send_email` corra una sola línea, `ApprovalHook` pausa la ejecución
completa del agente, muestra al humano en la terminal el destinatario/asunto/cuerpo propuestos, y solo
si la respuesta es `y` deja pasar la llamada real. Si la respuesta es cualquier otra cosa, la tool
**nunca se ejecuta**: el hook la cancela y el modelo recibe un error de texto, la misma convención de
"errores como string" que trae la serie desde `01`.

| Tool | ¿Se vigila? | Efecto |
|---|---|---|
| `draft_email` | No | Escribe en `DRAFTS`, nunca interrumpe |
| `send_email` | Sí | `ApprovalHook.approve()` pausa antes de correr; exige un draft previo |

## Cómo Funciona

### Detalles del ejemplo

| Información | Detalles |
|---|---|
| **Características de Strands** | `strands.hooks.BeforeToolCallEvent` (`_Interruptible`): `event.interrupt()` + `event.cancel_tool` |
| **Patrón de agente** | Agente único con un hook que interviene, no solo observa |
| **Herramientas** | 2 (`draft_email`, `send_email`) |
| **Modelo** | `gpt-5.4-mini` por la API directa de OpenAI (configurable con `MODEL_ID`) |
| **Archivos de código** | 2: `agent.py` (80 líneas) + `approval.py` (20 líneas) |
| **Dependencias nuevas** | **Cero**: `requirements.txt` es idéntico al de `09`/`10` — el sistema de interrupciones ya viene en `strands-agents` |

### El ciclo completo, medido contra un modelo guionizado (sin red, sin clave)

```
=== 1. primera llamada: interrumpe ===
stop_reason   -> 'interrupt'
n interrupts  -> 1
id            -> v1:before_tool_call:t1:8259d5a7-1e64-5166-bbcc-7c319e293a79
name          -> mailer-approval
reason        -> {'to': 'boss@example.com', 'subject': 'Q3 report', 'body': 'See attached.'}
SENT          -> []

=== 2. NEGAR ===
stop_reason   -> 'end_turn'
SENT          -> []
historial toolResult:
{
  "toolResult": {
    "toolUseId": "t1",
    "status": "error",
    "content": [ { "text": "User denied permission to send the email" } ]
  }
}

=== 3. APROBAR (corrida nueva) ===
stop_reason   -> 'end_turn'
SENT          -> [{'to': 'boss@example.com', 'subject': 'Q3 report', 'body': 'See attached.'}]

=== 4. draft_email NO interrumpe ===
stop_reason   -> 'end_turn'
```

El id de interrupción no es aleatorio: `v1:before_tool_call:t1:8259d5a7-...` termina en
`uuid5(NAMESPACE_OID, "mailer-approval")` — el mismo nombre que se le pasa a `event.interrupt(...)`
determina el id, siempre. Verificado también en el `.venv` propio de este ejemplo
(`strands-agents 1.56.0`, no `1.55.1` como en `10` — el contrato no cambió entre versiones, ver
"Correcciones frente al PRD").

### El flujo de una corrida con aprobación

```
usuario -> agent("envía el correo a boss@example.com")
             |
             |-- BeforeModelCallEvent -> el modelo decide llamar a send_email
             |-- AfterModelCallEvent   stop_reason=tool_use
             |-- BeforeToolCallEvent  ------> ApprovalHook.approve(event)
             |                                  event.tool_use["name"] == "send_email" -> sigue
             |                                  event.interrupt("mailer-approval", reason=...)
             |                                    -> no hay respuesta todavia
             |                                    -> raise InterruptException(interrupt)  [types/interrupt.py:111]
             v
   agent(...) NO propaga la excepcion: la captura el propio Agent y devuelve
   AgentResult(stop_reason="interrupt", interrupts=[Interrupt(id=..., name="mailer-approval", reason={...})])
             |
   [fuera del agente, en la CLI]
   humano ve reason, responde "y", se arma:
     [{"interruptResponse": {"interruptId": <id>, "response": "y"}}]
             |
             v
   agent(ese_payload)   <- NO es un prompt nuevo: reanuda el MISMO turno
             |
             |-- BeforeToolCallEvent  ------> ApprovalHook.approve(event) se ejecuta OTRA VEZ
             |                                  event.interrupt(...) encuentra interrupt_.response == "y"
             |                                  -> devuelve "y" en vez de lanzar; approve() no cancela
             |-- se ejecuta send_email(...) DE VERDAD -> "Sent to ... Message id: MSG-4471."
             |-- AfterToolCallEvent
             |-- BeforeModelCallEvent / AfterModelCallEvent   stop_reason=end_turn
             v
          respuesta final
```

Reanudar **no es un prompt nuevo**: es una lista de `interruptResponse` contra el mismo turno. Por eso
`_resolve_interrupts()` llama a `agent(responses)`, no a `agent(user_input)` de nuevo.

### Las tres trampas, medidas

**1. Dos trampas de forma** — reanudar con el payload equivocado no falla en silencio:

```python
>>> agent(["y"])
TypeError: content_types=<['y']> | must resume from interrupt with list of interruptResponse's

>>> agent([{"interruptResponse": {"interruptId": "no-existe", "response": "y"}}])
KeyError: 'interrupt_id=<no-existe> | no interrupt found'
```

**El primer mensaje corrige al PRD.** `interrupt.py:137-139` comprueba `content_types` iterando
`for content_type in content` sobre cada elemento del prompt: si el elemento es un `dict`, itera sus
claves (`"text"` — lo que documentaba el PRD); si es un **string** — que es justo lo que pasa un
`agent(["y"])` —, itera sus **caracteres**. Con `"y"` el resultado medido es `['y']`, no `['text']`.
Un prompt `agent([{"text": "y"}])` sí produciría `['text']`. §11 pide el mensaje real, no
parafraseado, así que el texto de arriba es literal, no el que trae `10`.

**2. `approve()` se re-ejecuta entera al reanudar**, no continúa desde donde lanzó la excepción:

```
calls tras interrumpir: ['send_email']
calls tras reanudar   : ['send_email', 'send_email', "got='y'"]
stop_reason: end_turn
```

`event.interrupt(...)` devuelve la respuesta guardada (`'y'`) en vez de volver a lanzar; el código
que corre *antes* de esa llamada —aquí, el `if event.tool_use["name"] != "send_email": return`— se
ejecuta dos veces por diseño. Es la razón por la que ese chequeo tiene que ser barato e idempotente,
nunca con efectos de lado.

### `callback_handler=None`: aquí importa más que en `10`

Sin apagar el `PrintingCallbackHandler` por defecto, su salida se intercala con el prompt de
aprobación: el `input("Approve sending? (y/n): ")` quedaría mezclado con texto del modelo en la misma
línea, y el humano no podría leer con confianza el `reason` antes de responder. En `10` el problema
era estético (un log sucio); aquí es funcional — se aprueba a ciegas.

### El `toolResult` de cancelación completo

```json
{
  "toolResult": {
    "toolUseId": "t1",
    "status": "error",
    "content": [{ "text": "User denied permission to send the email" }]
  }
}
```

El modelo no distingue *"la tool falló"* de *"un humano la vetó"* salvo por el texto de `content`. Es
la misma forma que cualquier otro error de tool en la serie desde `01`: `status: "error"`, sin
excepción sin capturar.

### El camino de error de dominio, fuera de la aprobación

`send_email` exige un draft previo — un guardarraíl real, no solo una instrucción confiada al
`SYSTEM_PROMPT`:

```python
if to not in DRAFTS:
    return f"No draft for '{to}'. Call draft_email first."
```

```
send_email x@example.com     -> No draft for 'x@example.com'. Call draft_email first.
```

Este error aparece **precisamente cuando** el modelo se salta el `SYSTEM_PROMPT` ("Always draft an
email with draft_email before sending it"), y se recupera en el mismo turno — la misma convención de
errores-como-texto que el resto de la serie.

### Las diferencias con `10`

| | `10-observable-agent` | `11-human-in-the-loop` |
|---|---|---|
| Eventos suscritos | 6 | 1 (`BeforeToolCallEvent`) |
| Qué hace el hook | Lee y anota | Decide y detiene |
| Campos que escribe | `on_tool_end` solo lee | `event.interrupt(...)`, `event.cancel_tool` |
| Efecto sobre el turno | Ninguno — el turno sigue igual | El turno se pausa hasta que un humano responde |
| Archivos de código | `agent.py` (96) + `observability.py` (84) | `agent.py` (80) + `approval.py` (20) |
| Escribe en disco | Sí (`trace.jsonl`) | No |

### Lo que existe y no se usa

| Símbolo | Por qué no |
|---|---|
| `tool_context.interrupt()` | Movería la decisión de pausar dentro de la tool; este ejemplo la deja fuera, en el hook, para que `send_email` siga pareciendo una `@tool` cualquiera de la serie |
| `BeforeToolsEvent` (`hooks/events.py:137`) | Interrumpe el *lote* completo de tool calls de un ciclo; aquí hay como mucho una tool interrumpible por turno |
| `BeforeNodeCallEvent` (`hooks/events.py:411`) | El mismo mecanismo aplicado a nodos de un grafo multiagente (`07`); fuera de alcance de un agente único |
| `strands.vended_interventions.hitl` | El manejador de alto nivel del SDK: resolvería aprobar/denegar/confiar-siempre en un parámetro del `Agent`, pero escondería justo el mecanismo (`event.interrupt`, `cancel_tool`, el bucle de reanudación) que este ejemplo existe para mostrar. Atajo de producción, no implementación de aquí |

### Cómo llevarte `approval.py`

Cambia `"send_email"` por el nombre de tu tool sensible y el texto de `event.cancel_tool` por tu
mensaje de denegación. Nada más: el `__init__`, el `register_hooks()` de una línea y el `approve()`
de cuatro no dependen del dominio.

## Configuración y Pruebas

### Prerrequisitos

- Python 3.10 o superior
- Una `OPENAI_API_KEY` en un `.env` local
- **Sin AWS** y **sin Node.js**
- `requirements.txt` es **idéntico al de `09`/`10`** (`diff` sin salida): interrumpir no cuesta una
  dependencia nueva

### Cómo ejecutarlo

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt   # solo la primera vez
cp .env.example .env            # y pon tu clave real en el .env

.venv/bin/python agent.py       # type 'exit' to quit
```

| Variable | Descripción |
|---|---|
| `OPENAI_API_KEY` | Tu clave de OpenAI. La lee el cliente de `openai` por su cuenta; ninguna línea de código la menciona |
| `MODEL_ID` | Modelo a usar. Por defecto `gpt-5.4-mini` |

### Los límites duros, medidos sobre los archivos finales

```
wc -l agent.py approval.py                  # 80 / 20   (topes: 80 / 30)
grep -c "@tool" agent.py                    # 2
grep -c "add_callback" approval.py          # 1
grep -c "tool_context" agent.py approval.py # 0 / 0
grep -rn "api_key\|sk-" agent.py approval.py        # sin resultados
diff requirements.txt ../10-observable-agent/requirements.txt   # sin salida
awk '{print length}' agent.py approval.py | sort -rn | head -1  # 96 (norma de la serie: <= 99)
```

### Transcripción de ejemplo

Corridas **reales** contra `gpt-5.4-nano` (vía `MODEL_ID` en `.env`), una por cada corrida de HU-1 a
HU-3. Se corrieron como tres procesos separados en vez de una sola sesión continua: en una sesión
única, el modelo — al ver el `SYSTEM_PROMPT` que pide confirmación antes de enviar — respondía con una
pregunta de vuelta en lugar de reintentar `send_email` de inmediato tras la negación, así que las
respuestas guionizadas (`n`, luego `y`) dejaban de alinearse con los prompts reales. Tres procesos
cortos, cada uno con una sola petición explícita, son la forma honesta de mostrar las tres corridas sin
adivinar cómo reaccionaría el modelo a una negación previa.

**Corrida 1 — solo redactar, sin pausa (HU-4):**

```
Mailbot: email assistant (gpt-5.4-nano). Type 'exit' to quit.

You > redacta (sin enviar) un correo para ana@example.com contandole que llego tarde

Mailbot > Asunto: Disculpa por llegar tarde

Hola Ana,

Lamento informarte que voy a llegar tarde. Lo siento por las molestias.

Gracias por tu comprensión.

Saludos,
[Tu nombre]
```

Ningún `[approval]` en la salida: el hook vigila `send_email`, no `draft_email`.

**Corrida 2 — enviar y negar (HU-1, HU-2):**

```
You > ya tengo el borrador listo para boss@example.com (asunto: Reporte Q3, cuerpo: "See attached."). Envialo ahora, no pidas mas confirmacion.

[approval] mailer-approval
  to: boss@example.com
  subject: Reporte Q3
  body: See attached.
  Approve sending? (y/n): n

Mailbot > No pude enviarlo: **permission denied** (el sistema bloqueó el envío).

Si quieres, puedo volver a intentarlo pero necesito que me des permiso explícito, o dime si debo
usar el borrador existente (si ya está registrado en el sistema) y confirmo los datos exactos.
```

`SENT` quedó vacío tras esta corrida — verificado también sin modelo en la Tarea 5.

**Corrida 3 — enviar y aprobar (HU-3):**

```
You > ya tengo el borrador listo para boss@example.com (asunto: Reporte Q3, cuerpo: "See attached."). Envialo ahora, no pidas mas confirmacion.

[approval] mailer-approval
  to: boss@example.com
  subject: Reporte Q3
  body: See attached.
  Approve sending? (y/n): y

[approval] mailer-approval
  to: boss@example.com
  subject: Reporte Q3
  body: See attached.
  Approve sending? (y/n): y

Mailbot > Listo—envié el correo a **boss@example.com** (Asunto: **"Reporte Q3"**).
ID del mensaje: **MSG-4471**.
```

**Nota honesta sobre esta corrida:** el modelo real emitió **dos** llamadas a `send_email` en el mismo
turno (probablemente redundantes, no una decisión del hook) — algo que el PRD (§4, fuera de alcance)
anticipó como posible pero no como escenario a construir a propósito: *"Múltiples tool calls
concurrentes interrumpiendo en paralelo ... se documenta como nota, no se construye un escenario para
probarlo"*. Ocurrió solo, sin guion. `_resolve_interrupts()` lo maneja sin cambios: itera
`result.interrupts` (dos elementos esa vez) y pide una aprobación por cada uno antes de reanudar — el
mecanismo no asume una sola interrupción por turno, aunque el ejemplo esté pensado para mostrar una.
`MSG-4471` confirma que `send_email` corrió de verdad.

## Información Adicional

### El gate vive dentro del mismo proceso — nota de seguridad

Hay que decirlo sin rodeos, con el mismo estándar que `09` aplicó a la sesión en claro y `10` al
rastro sin redactar:

- La aprobación ocurre **dentro del mismo proceso Python** que corre el agente. No hay una barrera de
  proceso, red o permisos entre "el modelo decidió llamar a `send_email`" y "el humano aprobó" — solo
  una función que bloquea en `input()`. Quien pueda inyectar entrada en ese `input()` (automatizando
  la terminal) puede aprobar en lugar de la persona.
- `reason=event.tool_use["input"]` expone al humano exactamente lo que el modelo va a ejecutar, sin
  redactar campos sensibles. En un dominio real (pagos, borrados de datos), ese `reason` es el mismo
  punto que `10` marcó como el lugar donde iría el enmascarado — tampoco se implementa aquí.
- El texto de `event.cancel_tool` viaja al modelo tal cual: no debe llevar nada que el modelo no deba
  ver (credenciales, motivos internos de negación). Es responsabilidad de quien escriba el hook.

**Fuera de alcance, explícito:** control de acceso sobre quién responde la aprobación, auditoría de
quién aprobó qué (se cruzaría con `10`), redacción de `reason`, aprobación fuera de proceso (un
servicio HTTP, un bot de Slack).

### `requirements.txt` es idéntico al de `09`/`10`

Interrumpir no cuesta una dependencia: `strands.hooks` y el sistema de interrupciones
(`strands.types.interrupt`) ya vienen en el paquete base de `strands-agents`.

### Correcciones frente al PRD

- **El mensaje de la primera trampa de forma no es el que cita `10`** (ver arriba, sección de
  trampas): el PRD citaba `['text']`; el medido, en ambos venvs probados, es `['y']`. Causa
  identificada en `interrupt.py:137-139`.
- **La versión instalada no es `1.55.1`, es `1.56.0`.** El plan de este ejemplo pedía re-medir el
  contrato completo si la versión cambiaba — se hizo (Tarea 2) contra este `.venv` nuevo: mismos
  `stop_reason`, mismo formato de id, mismo `toolResult` de cancelación, mismos dos mensajes de error,
  y la misma re-ejecución de `approve()` al reanudar. El contrato de interrupciones no se movió entre
  `1.55.1` y `1.56.0`.
- **La corrida de las tres escenas de §7 no ocurrió en una sola sesión**, como pedía el plan, sino en
  tres procesos separados — ver la nota en "Transcripción de ejemplo" arriba.

### Lo que sigue

`11` cierra el arco de intervención que abrió `10`. `12` cierra la serie con evaluación.

### Estructura del proyecto

```
11-human-in-the-loop/
├── agent.py            # constantes + 2 @tool + Agent(hooks=...) + CLI con reanudacion (80 lineas)
├── approval.py         # ApprovalHook: HookProvider, 1 add_callback, interrupt()+cancel_tool (20 lineas)
├── requirements.txt    # 3 líneas — idéntico al de 09/10
├── .env.example         # 2 variables
├── README.md            # este archivo
├── .env                 # tu clave; ignorado por git, no se commitea
└── .venv/               # ignorado por git
```

### Limpieza

```bash
rm -rf .venv    # borra el entorno
```

### Recursos adicionales

- [Strands Agents — documentación](https://strandsagents.com/)
- [Hooks en Strands](https://strandsagents.com/latest/documentation/docs/user-guide/concepts/agents/hooks/)
  — `HookProvider`, `HookRegistry`, los eventos del ciclo de vida
- [Modelos de OpenAI en Strands](https://strandsagents.com/latest/documentation/docs/user-guide/concepts/model-providers/openai/)
