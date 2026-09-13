# 07 · Grafo de agentes (topología declarada)

## Descripción

Cinco agentes de texto a texto y **seis aristas declaradas antes de que corra nada**. La arquitectura
de este ejemplo no está repartida por el archivo: es un bloque consecutivo que se lee como el
diagrama que dibuja.

```python
builder.add_edge("triage", "logs", condition=is_technical)      # la topología ES el código
builder.add_edge("triage", "impact", condition=is_technical)
builder.add_edge("triage", "business", condition=is_business)
```

`07` comparte dominio con `05` **a propósito**: el mismo mostrador de soporte, para que la comparación
sea de mecanismo y no de dominio. Mismo proveedor de modelo, mismo `load_dotenv()`, mismo `MODEL_ID`,
misma fábrica de agentes, mismo `callback_handler=None`, mismo reseteo por corrida, mismo bucle CLI.
La única diferencia es quién recorre: en `03` encadenabas, en `04` hacías `asyncio.gather`, en `05`
indexabas un `dict`, en `06` decidía el modelo. Aquí no hay ninguna línea de Python que relacione dos
agentes en tiempo de ejecución — las relaciones están declaradas y las recorre el `Graph`.

```
        05 (router)                    06 (agentes-tool)             07 (grafo)

  request ──► classifier         request ──► orchestrator       ticket ──► triage
                 │ Route(...)                 │ el modelo elige             │ TECHNICAL / BUSINESS
                 ▼                            ▼                             ▼
        SPECIALISTS[category]          ┌──────┴──────┐            ┌──────condición──────┐
      ┌────┬────┴────┬────┐            ▼             ▼            ▼         ▼           ▼
      ▼    ✗         ✗    ✗        flights_agent  hotels_agent  logs     impact     business
   billing  técnico ventas other      @tool         @tool          │        │           │
      │                                                           └───┬────┘           │
      ▼                                                               ▼                ▼
  la respuesta                                                    ┌───── responder ────┘
                                                                       │
  1 línea de Python despacha    0 líneas: decide el modelo             ▼
  coste CONSTANTE: 2 llamadas   coste VARIABLE: 1, 4, 6 o 7        la respuesta
  corre exactamente una rama    corren 0, 1 o 2 especialistas
                                                          0 líneas de Python recorren
                                                          coste DECLARADO: 4 (técnica) o 3 (negocio)
                                                          'logs' e 'impact' corren EN PARALELO
```

La diferencia no es de quién decide —eso era `06`— sino de **dónde vive la arquitectura**. En `05` y
en `06` la leías en el flujo de control; aquí la lees en una tabla de aristas, y quien la ejecuta es
el primitivo.

## Cómo Funciona

### Detalles del ejemplo

| Información | Detalles |
|---|---|
| Características de Strands | `GraphBuilder`, `add_node`, `add_edge(condition=...)`, `set_entry_point`, `set_max_node_executions`, `GraphResult` (`execution_order`, `results`, `execution_time`, `accumulated_usage`), `Agent`, `OpenAIResponsesModel`, `callback_handler=None` |
| Patrón de agente | Grafo de agentes con topología declarada y aristas condicionales |
| Herramientas | **Ninguna**: `grep -c '@tool' agent.py` → `0`. Los cinco nodos son texto a texto |
| Nodos / aristas | **5** nodos, **6** aristas, **3** de ellas con `condition=` |
| Modelo | `gpt-5.4-nano` (configurable con `MODEL_ID`) |
| Complejidad | Intermedio |
| Dependencias externas | Ninguna: ni servidor MCP ni API externa, solo la API directa de OpenAI |

### Conceptos clave

- **La topología es un dato, no un flujo de control.** Nueve líneas la fijan entera: el bucle de dos
  líneas que da de alta los cinco nodos, las seis aristas y el `set_entry_point`. La décima línea del
  bloque, `set_max_node_executions`, **no es topología, es configuración** — no cuenta. Fuera de ese
  bloque, `grep -n 'add_edge\|add_node' agent.py | wc -l` da **7** y no hay ninguna otra línea del
  archivo que relacione dos agentes.

- **Una condición es una función de Python que lee el resultado de otro nodo.** Nada más:

  ```python
  def is_technical(state) -> bool:
      return "TECHNICAL" in str(state.results["triage"].result).upper()
  ```

  Y aquí está la parte incómoda que este README **no disimula**: esto es **más débil** que el `05`.
  Allí el veredicto pasaba por un `Route` de Pydantic, un esquema validado que el modelo tenía que
  rellenar. Aquí es un `in` sobre texto libre. Si `triage` contesta *"Creo que es TECHNICAL, aunque
  también podría ser BUSINESS"*, el `in` dice `True` y se va por la rama técnica sin quejarse. El
  primitivo te regala el recorrido; el criterio de enrutado sigue siendo tuyo, y aquí es más frágil
  que en el ejemplo anterior.

- **Nadie cierra el conjunto de destinos por ti.** Por eso la segunda condición es un `not` y no una
  segunda comprobación independiente:

  ```python
  def is_business(state) -> bool:
      return not is_technical(state)
  ```

  Si las dos condiciones pudieran fallar a la vez, ninguna arista saldría de `triage`, el grafo
  terminaría en `COMPLETED` con un solo nodo ejecutado y **el cliente se quedaría sin respuesta**. El
  `not` garantiza que siempre sale exactamente una. Medido con el veredicto basura *"I am not sure,
  maybe both?"*: `['triage', 'business', 'responder']`, `Status.COMPLETED` — `responder` **sí** corre.

- **Qué pone el SDK y qué pones tú.** El SDK pone: el orden de ejecución por *batches* de nodos
  listos, la concurrencia dentro de cada batch, la construcción de la entrada de cada nodo a partir de
  sus dependencias (`_build_node_input`), y un `GraphResult` con `execution_order`, `results`,
  `execution_time` y `accumulated_usage`. Tú pones: los nodos, las aristas, las condiciones y el
  punto de entrada.

### Qué ve cada nodo

Esto es lo que más sorprende del primitivo, y lo que hace que los prompts de rama no necesiten decir
*"eres la rama técnica, confía en que te han enrutado bien"*. La entrada de `logs` en la rama técnica,
capturada de una corrida real:

```
Original Task: La exportacion a CSV falla con error 500 desde ayer

Inputs from previous nodes:

From triage:
  - Agent: TECHNICAL
```

A `logs` le llega el ticket original **y** el veredicto, etiquetado con el `node_id` que lo produjo.
Lo mismo para `impact` y `business`. Y la entrada de `responder`, con las dos notas de la rama
técnica (corrida real contra `gpt-5.4-nano`):

```
Original Task: La exportacion a CSV falla con error 500 desde ayer

Inputs from previous nodes:

From impact:
  - Agent: Afectados: usuarios/servicios que exportan a CSV. Impacto: exportación no funciona (HTTP 500), sin confirmación de datos perdidos. Urgencia: alta, desde ayer (posible pérdida de operación/automatizaciones). Severidad: mayor para quienes dependen del CSV.


From logs:
  - Agent: Primero revisaría: (1) Logs de “CSV export” con códigos de error 500 (hora desde ayer) → causa exacta (DB/timeout/Null). (2) Métrica “export_requests/failed_requests” por intervalo → si subió y cuándo empezó. (3) Log del handler/servicio upstream (gateway/DB) con latencia/timeout → identifica dependencia bloqueando.
```

> **Cuidado al inspeccionar esto tú mismo.** La entrada de un nodo **no** es un texto: es una lista de
> `ContentBlock` dentro de un único mensaje de rol `user` — **6** bloques en el caso de `responder`.
> Leer `messages[-1]["content"][0]["text"]` devuelve solo `Original Task: ...` y parece que el grafo
> no pasa las dependencias. Hay que unirlos:
>
> ```python
> "\n".join(b["text"] for b in msg["content"])
> ```

Y una precisión que conviene no equivocar: **todos los nodos ven el ticket original**, pero el nodo de
entrada lo recibe **crudo, sin el prefijo `Original Task:`**. Cuando un nodo no tiene dependencias
satisfechas, `_build_node_input` devuelve el task tal cual. Lo que ve `triage`:

```
La exportacion a CSV falla con error 500 desde ayer
```

### Las tres trampas

**Trampa 1 — `str(result)` no es la respuesta al cliente.** Concatena **todos** los nodos ejecutados
con su `node_id` delante, veredicto interno incluido. Medido con proveedor falso, para que las notas
sean cortas y se vea la forma:

```
triage: TECHNICAL
impact: Afecta a quien intenta exportar; bloqueante, urgencia alta.
logs: Miraria el rate de 5xx del gateway y el codigo DB-4419 en el log de conexiones.
responder: Estamos con ello: RESP-OK.
```

Imprimir eso filtra al cliente el veredicto de `triage` y las notas internas de los especialistas. Por
eso `agent.py` lee **un nodo concreto**: `str(result.results["responder"])`.

**Trampa 2 — la *readiness* es un OR, no un AND.** Un nodo se ejecuta cuando **alguna** de sus
dependencias está lista, no cuando lo están todas. Si el fan-in llega en batches distintos, el nodo
final corre **dos veces**. Contraejemplo medido, con `a→b→d` más `a→d`:

```
fan-in en batches distintos: ['a', 'b', 'd', 'd']   ← 'd' dos veces
fan-in en un solo batch    : ['a', 'b', 'c', 'd']   ← 'd' una vez
```

En este ejemplo `responder` corre **una sola vez** en las tres corridas medidas, y no es casualidad:
`logs` e `impact` terminan en el **mismo batch**, así que su fan-in llega junto. Es una propiedad de
esta topología, no una garantía del primitivo.

**Trampa 3 — `add_node()` sin `node_id`.** El id por defecto sale del nombre del agente, que en todos
los `Agent` sin nombre es el mismo:

```
ValueError: Node 'Strands Agents' already exists
```

Por eso el bucle es `builder.add_node(agent, node_id)` con el id **siempre** explícito, y las claves
del `dict AGENTS` **son** los `node_id` del grafo.

**Y un aviso que no es trampa pero se ve.** Sin `set_max_node_executions`, cada arranque imprime:

```
Graph without execution limits may run indefinitely if cycles exist
```

Sale por `stderr` vía `logging`, sin que el ejemplo configure nada, y se intercala de forma
impredecible con `stdout`. `GraphBuilder` **no** comprueba que el grafo sea acíclico: con `a ⇄ b` y un
punto de entrada explícito, construye sin quejarse, corre `a, b, a, b, a, b` y termina en
`Status.FAILED` al chocar con el tope. La línea `set_max_node_executions(len(AGENTS))` silencia el
aviso y pone el techo.

### Las cuatro diferencias con `06`

| | `06` agentes como herramientas | `07` grafo de agentes |
|---|---|---|
| Dónde vive la arquitectura | En los docstrings de dos `@tool`; la decide el modelo en su bucle | En seis `add_edge`, declaradas antes de correr |
| Quién recorre | El modelo, llamando a herramientas | El `Graph`, siguiendo aristas |
| Herramientas | **4** `@tool` | **0** |
| Prueba de qué corrió | Los `toolUse` de los historiales, más un dato inventado (`IB-4417`) | `result.execution_order`, que devuelve el propio primitivo |

Lo que **no** cambia: el proveedor de modelo, el `load_dotenv()` + `MODEL_ID`, la fábrica de agentes
de una línea, el `callback_handler=None`, el reseteo por corrida y el bucle CLI. Y el
`requirements.txt`, idéntico byte a byte.

### Coste y reloj

| Ejemplo | Llamadas al modelo por turno |
|---|---|
| `05` router | **2**, fijas, con 4 ramas o con 40 |
| `06` agentes-tool | **1, 4, 6 o 7** — lo decide el modelo, no se lee en el archivo |
| `07` grafo, rama técnica | **4** (`triage`, `logs`, `impact`, `responder`) |
| `07` grafo, rama de negocio | **3** (`triage`, `business`, `responder`) |

El coste de `07` no es fijo como el de `05`, pero **sí es legible en el archivo**: cada rama del
diagrama es un número de llamadas que puedes contar antes de ejecutar. Eso es lo que `06` había
perdido.

Y el reloj, medido con proveedor falso a 0,40 s por llamada:

| | Reloj | `execution_time` |
|---|---|---|
| Rama técnica (`logs` e `impact` en paralelo) | **1,21 s** | 1207 ms |
| Las mismas 4 llamadas en secuencia | 1,60 s | — |

Las marcas por nodo enseñan el solapamiento, y el detalle que importa:

```
triage     t0=+0.00 t1=+0.40 hilo=127364407227968
impact     t0=+0.40 t1=+0.80 hilo=127364407227968
logs       t0=+0.40 t1=+0.80 hilo=127364407227968
responder  t0=+0.80 t1=+1.21 hilo=127364407227968
hilos distintos : 1
```

`logs` e `impact` empiezan y terminan a la vez, **en un solo hilo**, y `agent.py` no contiene la
palabra `asyncio` ni una vez. Compáralo con el `asyncio.gather` explícito de `04` y con los tres hilos
que `06` usaba para sus sub-agentes: aquí la concurrencia sale de la forma del grafo, no de una línea
que la pida.

## Configuración y Pruebas

### Prerrequisitos

- Python 3.10 o superior
- Una `OPENAI_API_KEY` en un `.env` local
- **Sin AWS** y **sin Node.js**, igual que en `03`–`06`
- El `requirements.txt` es **idéntico al de `06`** (`diff` sin salida), y por tanto al de `01`–`04`:
  el primer ejemplo con una primitiva multi-agente no añade ni una dependencia

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

> **La traza `[graph]` sale DESPUÉS de la corrida, no durante.** Es un cambio respecto de `05` y `06`,
> donde salía antes porque el despacho pasaba por nuestro código y teníamos dónde ponerla. Aquí el
> recorrido lo hace el `Graph` y lo cuenta al terminar, en `result.execution_order`: mientras el grafo
> trabaja no hay nada que imprimir sin meterse dentro del primitivo. Ese es exactamente el precio de
> delegar el recorrido, y la respuesta a este problema es `10-observable-agent`, no un `print` más
> aquí.

### Transcripción de ejemplo

Corrida real contra `gpt-5.4-nano`, con los dos tickets seguidos en la misma sesión.

```
SupportGraph: Describe your issue. Type 'exit' to quit.

Using LLM model: gpt-5.4-nano

Ticket > 
[graph] triage ──► logs ──► impact ──► responder
Desde ayer la exportación a CSV falla para los usuarios con error HTTP 500 (impacto completo) y no pueden exportar. Necesitamos una revisión inmediata del backend/servicio del endpoint de exportación, ya que los logs confirman la causa del 500 (posible problema de DB/servicio o serialización). Validaremos también métricas 5xx/latencia y si es incidente general o regresión, y correlacionaremos dependencias (DB/cola/servicio externo) por request_id para identificar timeouts o fallos aguas abajo.

Ticket > 
[graph] triage ──► business ──► responder
Hola, gracias por avisar. Para revisar el doble cobro, necesito por favor: fecha y hora de los cargos, importe, método de pago y el recibo/ID de cada transacción. Con esos datos comprobaré en el historial de facturación si hubo dos cuotas del mismo mes o un cargo duplicado, y si corresponde un reembolso o una corrección. Envíame esa información y lo revisamos.

Ticket > exit
```

Los dos tickets fueron, en orden: *"La exportación a CSV falla con error 500 desde ayer"* y *"Me
habéis cobrado dos veces la cuota de este mes"*. Lo que hay que mirar son **las dos trazas**:
**cuatro** nodos en el primero, **tres** en el segundo, y `logs` e `impact` no aparecen en el segundo.
Ese recuento no lo decide ninguna línea de `agent.py`.

Fíjate también en lo que **no** hay en las respuestas: ninguna menciona que existan especialistas, y
ninguna repite el veredicto `TECHNICAL` de `triage`. Eso lo pide `RESPONDER_PROMPT`, y es lo que hace
que la trampa 1 importe — la información para filtrarlo estaba ahí, en `str(result)`.

> **El orden de `logs` e `impact` no está garantizado.** Aquí salió `logs ──► impact`; en las corridas
> con proveedor falso salió `impact ──► logs`. `execution_order` **no es un orden total dentro de un
> batch**: los candidatos listos se recogen en un `set` y se lanzan a la vez. La transcripción está
> copiada tal cual salió, sin ordenarla, porque ordenarla escondería una propiedad real del primitivo.

**La prueba de que la rama no elegida no corrió.** Con un driver que importa el `agent.py` real y lee
los historiales al terminar el turno de negocio:

```
--- msgs logs/impact: {'logs': 0, 'impact': 0}
```

Cero mensajes: nadie les llamó. Y en `result.results` esas claves **no existen** — no están vacías,
no están. Misma prueba secundaria que en `05` y `06`.

## Información Adicional

**Ningún dato inventado hace de prueba aquí, y es deliberado.** En `01`–`06` la prueba de que algo
corrió era un valor que el modelo no podía adivinar (`8642`, `KRAKEN-7743`, `IB-4417`). Este ejemplo
no tiene tools ni catálogos: la prueba la da el propio primitivo, en `result.execution_order`. Es la
primera vez en la serie que no hace falta plantar un dato para saber qué se ejecutó.

**Sobre el `accumulated_usage`.** El `GraphResult` lo trae, pero este README no cita ninguna cifra de
tokens: medido con proveedor falso sale a cero (el falso no reporta uso), y una cifra de una corrida
real cambiaría con cada ticket. Instrumentar el coste de verdad es lo de `10-observable-agent`.

**Lo que queda para los siguientes.** `08-agent-swarm` va a quitar la topología sobre **este mismo
dominio**: los mismos especialistas, sin aristas y sin punto de entrada, decidiendo entre ellos a
quién pasarle el turno. `07` y `08` son las dos respuestas del framework a la pregunta que dejó
abierta `06` — una fija la arquitectura, la otra la disuelve — y comparten dominio para que se puedan
comparar. Del resto: `09` mete estado persistente, `10` la observabilidad que aquí se echa de menos en
la traza `[graph]`, y `11`–`12` el bucle autónomo y la evaluación.

### Estructura del proyecto

```
07-agent-graph/
├── agent.py            # 5 prompts + desk() + AGENTS + 2 condiciones + el bloque GraphBuilder + run_ticket + CLI (91 líneas, 0 @tool)
├── requirements.txt    # 3 líneas — idéntico al de 06 y al de 01–04
├── .env.example        # 2 variables
├── README.md           # este archivo
└── .env                # tu clave; ignorado por git, no se commitea
```

### Limpieza

No hay nada que limpiar: el ejemplo no crea recursos, no lanza subprocesos y no escribe ningún
archivo. Los cinco historiales se vacían al principio de cada corrida — el `Graph` resetea su propio
estado, pero los historiales de los agentes son suyos y sobreviven a la invocación, así que sin ese
`messages.clear()` `triage` pasaría de 4 a 6 mensajes en la segunda corrida (medido). Para borrar el
entorno: `rm -rf .venv`.

### Recursos adicionales

- [Strands Agents — documentación](https://strandsagents.com/)
- [Grafos de agentes en Strands](https://strandsagents.com/latest/documentation/docs/user-guide/concepts/multi-agent/graph/)
  — `GraphBuilder`, las aristas condicionales y el `GraphResult` de este ejemplo
- [Multi-agent en Strands](https://strandsagents.com/latest/documentation/docs/user-guide/concepts/multi-agent/multi-agent-patterns/)
  — el catálogo de primitivas, y dónde encaja el grafo frente al swarm
- [Modelos de OpenAI en Strands](https://strandsagents.com/latest/documentation/docs/user-guide/concepts/model-providers/openai/)
