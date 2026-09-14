# 08 · Enjambre de agentes (sin control central)

Tres agentes de texto a texto, una lista y unos topes. **Ninguna línea de este archivo relaciona a dos
agentes**: no hay aristas, ni condiciones, ni orden, ni punto de entrada explícito.

```python
PEERS = [peer("researcher", "Turns a vague request into numbered requirements. Writes no code.", RESEARCHER_PROMPT),
         peer("coder", "Writes and fixes the Python code.", CODER_PROMPT),
         peer("reviewer", "Reviews code against the requirements and gives the final answer.", REVIEWER_PROMPT)]
swarm = Swarm(PEERS, max_handoffs=6, max_iterations=6, node_timeout=60.0,
              repetitive_handoff_detection_window=4, repetitive_handoff_min_unique_agents=3)
```

Eso es la arquitectura entera. `grep -cE "add_node|add_edge|condition=|tools=" agent.py` → `0`.

**A diferencia de `05`, `06` y `07`, este ejemplo cambia de dominio a propósito.** `05` y `07`
compartían mostrador de soporte para que la comparación fuera de mecanismo y no de dominio; aquí no se
puede. Un ticket de soporte no vuelve atrás: se clasifica, se atiende y se responde. La tesis de `08`
es justamente el recorrido que **ningún grafo acíclico puede producir** —
`researcher ──► coder ──► reviewer ──► coder ──► reviewer` — y para que un par pueda devolverle el
trabajo a otro hace falta un dominio donde devolver signifique algo. Un equipo de desarrollo lo es; un
mostrador de soporte, no.

## Descripción

```
             07 GRAFO                                    08 SWARM

  ticket ──► triage                             task ──► researcher
                │ TECHNICAL / BUSINESS                        │
                ▼                                             ▼  ¿a quién le toca?
     ┌──────condición──────┐                              ┌────┴────┐
     ▼         ▼           ▼                              │  coder  │◄──┐
   logs     impact     business                           └────┬────┘   │ "falta el
     │         │           │                                   │        │  caso None"
     └────┬────┘           │                                   ▼        │
          ▼                ▼                              ┌─────────┐   │
      ┌───── responder ────┘                              │ reviewer├───┘
            │                                             └────┬────┘
            ▼                                                  ▼
       la respuesta                                       la respuesta
                                                          (del último que habló)

  6 aristas + 3 condiciones ESCRITAS            0 líneas que relacionen dos agentes
  coste DECLARADO: 4 o 3 llamadas               coste DESCONOCIDO hasta terminar: 1 … 12
  el recorrido se lee en el archivo             el recorrido se lee en node_history
  no puede haber ciclos                         el ciclo ES la tesis del ejemplo
```

Las tres respuestas de la serie a la misma pregunta —**quién decide el recorrido**:

| | Quién decide | Cuándo | Qué cuesta |
|---|---|---|---|
| `06` agentes-como-tool | **un** modelo, el orquestador, jerárquicamente | en su turno | 1, 4, 6 o 7 llamadas |
| `07` grafo | **nadie en tiempo de ejecución**: lo decidió quien escribió las aristas | antes de correr | 4 (técnica) o 3 (negocio), sabido de antemano |
| `08` enjambre | **cada par, sobre la marcha**, sin ver el conjunto | durante la corrida | entre 1 y 12 llamadas — no se sabe hasta terminar |

El precio del ejemplo está en esa última celda, y se dice sin adornos: **aquí el coste deja de ser
legible en el archivo.**

## Cómo Funciona

### Detalles del ejemplo

| Información | Detalles |
|---|---|
| Características de Strands | `Swarm`, `Agent(name=, description=)`, `swarm.stream_async()`, `SwarmResult` (`node_history`, `results`, `status`), la tool inyectada `handoff_to_agent`, `OpenAIResponsesModel`, `callback_handler=None` |
| Patrón de agente | Enjambre: pares autónomos que se traspasan el control, sin orquestador ni topología |
| Herramientas | **Ninguna escrita por nosotros**: `grep -c '@tool' agent.py` → `0`. La única tool del sistema, `handoff_to_agent`, la inyecta el `Swarm` |
| Pares / conexiones | **3** pares, **0** conexiones declaradas, **5** topes explícitos |
| Modelo | `gpt-5.4-nano` (configurable con `MODEL_ID`) |
| Complejidad | Intermedio–avanzado |
| Dependencias externas | Ninguna: ni servidor MCP ni API externa, solo la API directa de OpenAI |

### Conceptos clave

**La arquitectura es una lista.** En `07` el bloque equivalente eran catorce líneas de
`add_node`/`add_edge`/`set_entry_point`. Aquí son dos: la lista y los topes. No hay `entry_point=`
porque el primero de la lista ya lo es.

**`description=` es la tercera encarnación del criterio de enrutado.** En `06` era el docstring de un
`@tool` que leía el orquestador; en `07`, una función Python (`condition=`) que leía el estado del
grafo. Aquí es una frase en inglés que el `Swarm` inyecta en el roster que recibe **cada** par:

```
Other agents available for collaboration:
Agent name: researcher. Agent description: Turns a vague request into numbered requirements. Writes no code.
Agent name: reviewer. Agent description: Reviews code against the requirements and gives the final answer.
```

La `description` no es documentación: es lo **único** por lo que un par decide a quién pasarle el
control. Si la dejas vacía, el par elige a ciegas.

**Qué hace el `Swarm` por ti**, y cuándo. Cuatro cosas, todas al construirlo — no al invocarlo:

1. Inyecta la tool `handoff_to_agent` en cada par.
2. Construye el roster a partir de los `name=` y las `description=`.
3. Mantiene la memoria compartida (el `context` que un par adjunta al traspaso).
4. Aplica los topes y devuelve un `SwarmResult` con el recorrido.

Lo de la tool se comprueba **sin red y sin credencial**, porque `_inject_swarm_tools()` se llama desde
`Swarm.__init__`:

```
antes de Swarm(...):  [[], [], []]
despues de Swarm(...): [['handoff_to_agent'], ['handoff_to_agent'], ['handoff_to_agent']]
```

**La terminación vive en un prompt, no en el código.** Un swarm termina cuando un par **se calla**:
si no llama a `handoff_to_agent`, la corrida se da por acabada. Eso significa que la condición de
parada de este ejemplo está escrita en `REVIEWER_PROMPT` (*"If the code works on the stated cases, do
NOT hand off"*), en inglés, dentro de una cadena de texto. Ninguna línea de Python la comprueba. Es la
diferencia más incómoda con `07`, donde el grafo terminaba porque se acababan las aristas.

### Qué ve un par

La entrada literal que recibe `coder` la primera vez, capturada de una corrida **real**:

```
Context:
Handoff Message: Need implementation for Spanish request: group list of dicts by a given key.

User Request: Una funcion que agrupe una lista de diccionarios por una clave

Previous agents who worked on this: researcher

Shared knowledge from previous agents:
• researcher: {'requirements': ['1) Input: list[dict] items and key (str or callable selector) plus optional default for missing keys.', '2) Output: dict mapping key_value -> list of original dicts (preserve order within groups).', '3) Edge: missing key in some dicts (either skip or use default bucket).', '4) Edge: key_value unhashable (e.g., list/dict) => raise or convert deterministically.', '5) Edge: empty input; non-dict elements; key type validation and error messages.']}

Other agents available for collaboration:
Agent name: researcher. Agent description: Turns a vague request into numbered requirements. Writes no code.
Agent name: reviewer. Agent description: Reviews code against the requirements and gives the final answer.

You have access to swarm coordination tools if you need help from other agents. If you don't hand off to another agent, the swarm will consider the task complete.
```

Cinco consecuencias, y la primera es la que más duele:

1. **No trae el texto del par anterior.** Compáralo con el `From <nodo>:` de `07`, donde cada nodo
   recibía la salida completa del anterior. Aquí `researcher` escribió sus requisitos y **eso no
   viaja**: lo único que llega es el `Handoff Message` y el `context` que él decidió adjuntar.
2. Por eso `RESEARCHER_PROMPT` exige meter los requisitos en el `context` del traspaso, y por eso
   `CODER_PROMPT` exige pegar **la función entera** en el mensaje de traspaso. Sin esas dos frases el
   revisor pide el código, el coder se lo vuelve a prometer, y la corrida muere en los topes (medido:
   pasó exactamente eso en el primer intento de la corrida real).
3. El `Shared knowledge` sí es acumulativo y va por par: `• researcher: {...}`.
4. El roster sale entero de las `description=`, y es lo mismo para todos.
5. La última frase la pone el framework, y es la que define la terminación por silencio.

### Las cuatro trampas

**Trampa 1 — `results` no tiene todos los turnos.** Sobre la misma corrida de cinco turnos:

```
node_history: ['researcher', 'coder', 'reviewer', 'coder', 'reviewer']   ← 5
results keys: ['researcher', 'coder', 'reviewer']                        ← 3
```

`results` guarda **el último resultado de cada par**, no un turno por entrada. Si cuentas los turnos
con `len(result.results)` te faltan dos.

**Trampa 2 — `str(result)` filtra las frases de traspaso al usuario.** Es lo que sale si lo imprimes
tal cual (corrida real, la misma de arriba):

~~~
researcher: 1) **Inputs:** `items` (list of dicts), `key` (str key name), optional `default` for dicts missing the key.
...
coder: ```python
def group_dicts_by_key(items, key, default_bucket=None):
...
reviewer: No puedo aprobar: hay un defecto concreto en el comportamiento para claves faltantes (requisito #3). ... Hand off al agente coder para que corrija la función completa.
~~~

Tres bloques con el `node_id` delante, y el del medio es el trabajo intermedio del `coder`, no la
respuesta. Por eso `agent.py` lee **un par concreto**, y cuál sea no se sabe hasta terminar:

```python
answer = str(result.results[result.node_history[-1].node_id])
```

**Trampa 3 — un `Agent` sin `name=` rompe el `Swarm`.** Los siete ejemplos anteriores construían los
agentes sin nombre; aquí el nombre es el identificador del nodo, y dos agentes sin nombre colisionan:

```
ValueError: Node ID 'Strands Agents' is not unique. Each agent must have a unique name.
```

**Trampa 4 — los nombres de evento del stream no son los que dice el docstring.** Medido en
`strands-agents 1.55.1`: el docstring de `stream_async` anuncia `multi_agent_*`, **con** guion bajo, y
los eventos salen `multiagent_*`, **sin** él. Los cinco tipos reales, con su recuento en una corrida
de cinco turnos:

```
{'multiagent_node_start': 5, 'multiagent_node_stream': 108, 'multiagent_node_stop': 5,
 'multiagent_handoff': 4, 'multiagent_result': 1}
```

Es la peor de las cuatro porque **falla en silencio**: un `elif kind == "multi_agent_handoff"` nunca
entra, no lanza nada, y simplemente no imprimes los traspasos. Por eso el aviso va en la propia línea
del filtro en `agent.py`.

### Los cinco topes, y qué corta cada uno

Sin orquestador, los topes son lo **único** que acota la corrida. Con los valores por defecto
(`max_handoffs=20`, `max_iterations=20`, detector desactivado), un ping-pong entre dos pares cuesta
**20 turnos y 40 llamadas** al modelo antes de parar. Ese es el número que justifica la línea.

| Tope | Valor aquí | Por defecto | Qué corta de verdad |
|---|---|---|---|
| `max_handoffs` | `6` | `20` | El número total de traspasos |
| `max_iterations` | `6` | `20` | Los turnos de par. **El único que corta siempre**, incluidas las rotaciones de tres |
| `node_timeout` | `60.0` s | `300.0` s | Un par colgado, no un bucle |
| `repetitive_handoff_detection_window` | `4` | `0` (desactivado) | Nada por sí solo: es la ventana que mira el detector |
| `repetitive_handoff_min_unique_agents` | `3` | `0` | Con `3`, corta los ping-pong de **dos** pares a los 5 turnos. Con `2` es **inerte** |

Los dos topes están puestos porque cubren cosas distintas, y medirlo lo deja claro:

```
ping-pong coder ⇄ reviewer, con estos topes    5 turnos, 10 llamadas, FAILED   ← lo corta el DETECTOR
ping-pong coder ⇄ reviewer, por defecto       20 turnos, 40 llamadas, FAILED   ← lo corta max_handoffs
rotacion researcher ──► coder ──► reviewer ──► researcher ──► coder ──► reviewer
                                               6 turnos, 12 llamadas, FAILED   ← lo corta max_iterations
```

El detector **no es una salvaguarda universal**: es ciego a la rotación de tres, porque cualquier
ventana de 4 turnos contiene 3 pares únicos y su condición se cumple. `max_iterations` es el que no
falla nunca, y es el que fija el techo real del ejemplo en **12 llamadas**.

### Las cuatro diferencias con `07`

| | `07` grafo | `08` enjambre |
|---|---|---|
| Arquitectura | 14 líneas: 5 `add_node`, 6 `add_edge`, entry point, tope | 2 líneas: una lista y unos topes |
| Sincronía | `graph(ticket)` síncrono | `async` + `asyncio.run()`, como en `04` |
| Reseteo por corrida | `for agent in AGENTS.values(): agent.messages.clear()` | **ninguno** |
| Traza | **después** de la corrida, desde `execution_order` | **durante**, desde el stream |

Sobre el `asyncio`, que vuelve de `04`: no es estética. El **motivo** de cada traspaso —lo que un par
escribe al soltar el control, que es la coordinación entera del sistema— **no existe** en el
`SwarmResult`. Sólo aparece en el evento `multiagent_handoff` del stream. Si quieres verlo, el
consumidor tiene que ser asíncrono; si te conformas con `swarm(task)`, lo pierdes.

Sobre el reseteo que desaparece: medido, los historiales de los pares **no crecen** entre
invocaciones (`{'researcher': 4, 'coder': 4, 'reviewer': 2}` tras la primera corrida, y lo mismo tras
la segunda), y la corrida 2 no ve la tarea de la 1. `grep -c 'messages.clear()' agent.py` → `0`, y no
es un olvido: sobra.

### Coste

La fórmula, medida en los cinco escenarios: **`llamadas = turnos + handoffs`**. Un traspaso cuesta
**dos** llamadas, no una — el par llama al modelo para decidir el traspaso, y otra vez para cerrar su
turno tras el `toolResult`.

| Escenario | Turnos | Llamadas | Estado |
|---|---|---|---|
| `researcher` responde solo y se calla | 1 | **1** | COMPLETED |
| `researcher ──► coder ──► reviewer`, sin reproceso | 3 | **5** | COMPLETED |
| Con una ronda de revisión (`coder ──► reviewer` otra vez) | 5 | **9** | COMPLETED |
| Ping-pong cortado por el detector | 5 | **10** | FAILED |
| Rotación de tres cortada por `max_iterations` | 6 | **12** | FAILED |

Puesto junto al resto de la serie, es la comparación que vertebra estos cuatro ejemplos:

- `05` router: **2** llamadas, siempre. Lo sabes leyendo el archivo.
- `06` agentes-como-tool: **1, 4, 6 o 7**. Lo sabes enumerando lo que el orquestador puede elegir.
- `07` grafo: **4 o 3**. Lo sabes mirando las aristas.
- `08` enjambre: **entre 1 y 12**. No lo sabes hasta que la corrida termina.

## Configuración y Pruebas

### Prerrequisitos

- Python 3.10 o superior
- Una `OPENAI_API_KEY` en un `.env` local
- **Sin AWS** y **sin Node.js**, igual que en `03`–`07`
- El `requirements.txt` es **idéntico al de `07`** (`diff` sin salida), y por tanto al de `01`–`04` y
  `06`: la tercera primitiva multi-agente de la serie sigue sin añadir ni una dependencia

### Cómo ejecutarlo

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt   # solo la primera vez
cp .env.example .env            # y pon tu clave real en el .env
.venv/bin/python agent.py       # escribe 'exit' para salir
```

| Variable | Descripción |
|---|---|
| `OPENAI_API_KEY` | Tu clave de OpenAI. La lee el cliente de `openai` por su cuenta; ninguna línea de código la menciona |
| `MODEL_ID` | Modelo a usar. Por defecto `gpt-5.4-nano` |

`MODEL_ID=gpt-5.4 .venv/bin/python agent.py` cambia el modelo para una sola corrida.

> **Aquí la traza sale DURANTE la corrida, no después.** Es la vuelta exacta de lo que decía `07`, y
> el motivo es medible: el `message` de cada traspaso no está en el `SwarmResult`, sólo en el evento
> del stream. Si esperas al final, lo has perdido. La línea `[swarm] … (status)` sí sale al terminar,
> construida desde `node_history`. No hay hooks ni métricas por par: eso es `10-observable-agent`.

> **Los prompts de este ejemplo NO llevan *"in the ticket's language"***, a diferencia de `03`–`07`.
> Es un ejemplo de código: los identificadores, los mensajes de error y los comentarios salen en
> inglés por naturaleza, y forzar el idioma de la petición sólo produciría código con nombres en
> español. Verás la tarea en español y la conversación del equipo mezclando los dos idiomas; eso es lo
> que hace el modelo, y está copiado tal cual.

### Transcripción de ejemplo

Corrida real contra `gpt-5.4-nano`, con las dos tareas seguidas en la misma sesión. Es larga a
propósito: **la conversación entre los pares es el ejemplo**, no un detalle de la salida.

```
DevSwarm: Ask the team for a small function. Type 'exit' to quit.

Using LLM model: gpt-5.4-nano

Task > 
[researcher] pensando...
  researcher ──► coder: Need implement function to group list of dicts by a key when some dicts may miss it. Use requirements provided in context.

[coder] pensando...
  coder ──► reviewer: Implement this function:

def group_dicts_by_key(items, key, default_bucket=None):
    """Group a list of dicts by dict[key]. Missing-key dicts go to default_bucket."""
    from collections import defaultdict
    buckets = defaultdict(list)
    for item in items:
        if not isinstance(item, dict):
            raise TypeError("All items must be dicts")
        if key in item:
            buckets[item[key]].append(item)
        else:
            buckets[default_bucket].append(item)
    return dict(buckets)

Review against requirements: handle empty list; raise on non-dict items; missing key -> default label; preserve order per bucket; key value can be None; decide behavior for unhashable values (current uses dict key directly, may raise). If you find defects, return a corrected whole function.

[reviewer] pensando...
  reviewer ──► coder: Defect: ... Main concrete issue: unhashable values for item[key] will raise TypeError when used as dict key; requirements ask to 'decide behavior' but not just let it crash. We need to handle unhashable values explicitly (e.g., convert to str or raise with clear message). Please fix whole function accordingly.

[coder] pensando...
  coder ──► reviewer: Defect noted: handle unhashable values (currently would crash when used as dict key) and ensure missing-key bucket uses provided default_bucket label (including None) and exists even if empty. Please review this whole function as pasted below and fix if needed.

    ... (la función corregida, con el try/except alrededor del append) ...

[reviewer] pensando...

[swarm] researcher ──► coder ──► reviewer ──► coder ──► reviewer  (completed)
**Defect:** La función no cumple con "manejar valores no hashable" sin crashear: ... A falta de
claridad, apruebo: el bucket falta solo si no se llama setdefault, y aquí sí.  

✅ **Aprobado.** Mantiene el bucket `default_bucket` vía `setdefault` y respeta el agrupamiento y
manejo de faltantes.

Task > 
[researcher] pensando...
  researcher ──► coder: Turn user request into code requirements for a duration parser (e.g., '1h30m' → seconds).

[coder] pensando...
  coder ──► reviewer: Please review the following Python function for parsing duration strings like '1h30m' into total seconds.

    ... (la función, con su bucle carácter a carácter) ...

[reviewer] pensando...

[swarm] researcher ──► coder ──► reviewer  (completed)
**Defect found:** The function accepts whitespace inside tokens ... Handing off to **coder** to decide
whether to tighten parsing rules (e.g., disallow whitespace between number and unit).

Task > exit
```

Las dos tareas fueron: *"Una funcion que agrupe una lista de diccionarios por una clave, donde a
algunos diccionarios les falta esa clave"* y *"Una funcion que parsee una duracion como '1h30m' a
segundos"*. Lo que hay que mirar son **las dos trazas `[swarm]`**:

- **Cinco** turnos en la primera, con `coder` y `reviewer` **repetidos**: el revisor encontró un
  defecto concreto, lo devolvió, el coder lo corrigió y la segunda revisión aprobó. Ese recorrido no
  cabe en el grafo de `07`, y ninguna línea de `agent.py` lo pidió.
- **Tres** en la segunda, sobre el mismo archivo, los mismos prompts y la misma sesión. La
  variabilidad no es un fallo: es la propiedad del patrón.

Y un detalle que enseña dónde está de verdad la coordinación: la respuesta de la segunda tarea
**dice** *"Handing off to coder"*… y el recorrido termina ahí. Anunciar un traspaso en prosa no es un
traspaso. Sólo cuenta la llamada a `handoff_to_agent`, y esa no se hizo — así que el `Swarm` dio la
tarea por terminada, exactamente como dice la última frase del roster.

> **Hizo falta endurecer los prompts, no añadir código.** En el primer intento de esta corrida el
> `coder` no pegaba la función en el traspaso, el `reviewer` la pedía, y las dos tareas murieron en
> `max_iterations` con estado `FAILED`. La respuesta fue reescribir dos frases de los prompts
> (*"hand off … with the WHOLE function pasted in the handoff message"*, *"never ask for it again"*,
> *"when in doubt, approve"*), **nunca** un `if` ni una validación del recorrido. Si hubieras añadido
> ese `if`, habrías reinventado `07` dentro de `08`.

> **Un `(failed)` no es un fallo del ejemplo, es información.** Significa que un tope hizo su trabajo,
> y entonces lo que se imprime debajo es un trabajo a medias, no una conclusión. Por eso `agent.py`
> imprime el `status` junto al recorrido: sin él, una respuesta truncada parece una respuesta.

## Información Adicional

**El código que escribe `coder` no se ejecuta nunca.** Ni aquí, ni en el `reviewer`, ni en ninguna
línea de `agent.py`: `grep -c 'exec\|eval' agent.py` → `0`. Este ejemplo mueve **texto** entre tres
agentes. El `✅ Aprobado` del revisor es la opinión de otro LLM sobre un texto, **no una prueba de que
la función funcione** — mírala tú antes de usarla. La verificación real de una salida es lo de
`12-evaluator-agent`.

**Ningún dato inventado hace de prueba aquí**, igual que en `07`. La prueba de qué corrió la da el
primitivo, en `result.node_history`.

**Lo que queda para los siguientes.** `08` cierra el arco multi-agente que abrió `03`: cadena,
abanico, router, jerarquía, grafo y enjambre. `09` mete estado persistente entre sesiones — lo que
aquí falta a propósito, porque los historiales de los pares no se reinician pero tampoco se guardan;
`10` la observabilidad, que es la respuesta honesta a que aquí el coste sólo se conozca al terminar;
y `11`–`12`, el bucle autónomo y la evaluación.

### Estructura del proyecto

```
08-agent-swarm/
├── agent.py            # 3 prompts + peer() + PEERS + Swarm(topes) + run_task async + CLI (78 líneas, 0 @tool, 0 conexiones)
├── requirements.txt    # 3 líneas — idéntico al de 07 y al de 01–04 y 06
├── .env.example        # 2 variables
├── README.md           # este archivo
└── .env                # tu clave; ignorado por git, no se commitea
```

### Limpieza

No hay nada que limpiar: el ejemplo no crea recursos, no lanza subprocesos y no escribe ningún
archivo. Tampoco hay historiales que vaciar — el `Swarm` reinicia el suyo en cada invocación, y los de
los pares no crecen entre corridas (medido). Para borrar el entorno: `rm -rf .venv`.

### Recursos adicionales

- [Strands Agents — documentación](https://strandsagents.com/)
- [Swarm en Strands](https://strandsagents.com/latest/documentation/docs/user-guide/concepts/multi-agent/swarm/)
  — `Swarm`, los topes y el `SwarmResult` de este ejemplo
- [Multi-agent en Strands](https://strandsagents.com/latest/documentation/docs/user-guide/concepts/multi-agent/multi-agent-patterns/)
  — el catálogo de primitivas, y dónde encaja el enjambre frente al grafo de `07`
- [Modelos de OpenAI en Strands](https://strandsagents.com/latest/documentation/docs/user-guide/concepts/model-providers/openai/)
