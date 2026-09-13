# 06 · Agentes como herramientas (composición jerárquica)

## Descripción

Un orquestador con dos herramientas. Las dos son **agentes**: funciones `@tool` de tres líneas que
llaman a un `Agent` y devuelven `str(...)`. El SDK no distingue lo que hay dentro —un `dict`, una
API, otro agente con su propio bucle de herramientas— así que la composición jerárquica no necesita
ninguna primitiva multi-agente. Toda la arquitectura de este ejemplo cabe en una línea:

```python
orchestrator = Agent(..., tools=[flights_agent, hotels_agent])   # y nada más: no hay línea de despacho
```

`06` es `05` **sin la línea que despacha**. Mismo proveedor de modelo, mismo `load_dotenv()`, mismo
`MODEL_ID`, misma fábrica de agentes, mismo `callback_handler=None`, mismo reseteo por corrida,
mismo bucle CLI. Donde `05` tenía `SPECIALISTS[route.category](request)`, aquí no hay nada: quién
corre, en qué orden y cuántas veces lo decide el modelo dentro de su propio bucle de herramientas.

```
        05 (router)                              06 (agentes como herramientas)

  request ──► classifier                   request ──► orchestrator
                  │ Route(category)                        │ el modelo elige, en su bucle
                  ▼                                        ▼
           SPECIALISTS[category]              ┌─────────────┴─────────────┐
        ┌────┬────┴────┬────┐                 ▼                           ▼
        ▼    ✗         ✗    ✗             flights_agent  @tool      hotels_agent  @tool
     billing técnico ventas other              │                           │
        │                                      ▼                           ▼
        ▼                                  flights  Agent            hotels  Agent
   la respuesta                                │                           │
                                               ▼                           ▼
   1 línea de Python despacha              search_flights            search_hotels
   coste CONSTANTE: 2 llamadas             0 líneas de Python despachan
   corre exactamente una rama              coste VARIABLE: 1, 4, 6 o 7 llamadas
                                           corren 0, 1 o 2 especialistas — o el mismo dos veces
```

La diferencia no es de topología, es de **quién decide**. En `05` el despacho era una indexación de
`dict` que podrías leer en el código y predecir de memoria. Aquí el criterio vive en los docstrings
de las dos `@tool`, lo decide el modelo en tiempo de ejecución, y el precio es que el coste del
turno ya no se puede leer en el archivo.

## Cómo Funciona

### Detalles del ejemplo

| Información | Detalles |
|---|---|
| Características de Strands | `Agent`, `@tool`, `OpenAIResponsesModel`, `callback_handler=None`, `agent.messages`, `agent.tool_names` |
| Patrón de agente | Agentes como herramientas / composición jerárquica. **Sin primitiva multi-agente**: ni `GraphBuilder`, ni `Swarm`, ni `Agent.as_tool()` |
| Herramientas | **4**: dos envuelven un agente (`flights_agent`, `hotels_agent`) y dos leen un `dict` (`search_flights`, `search_hotels`) |
| Modelo | `gpt-5.4-nano` (configurable con `MODEL_ID`) |
| Complejidad | Intermedio |
| Dependencias externas | Ninguna: no hay servidor MCP ni API externa, solo la API directa de OpenAI |

### Conceptos clave

- **Un agente-herramienta es una función `@tool` que llama a un `Agent` y devuelve `str(...)`.**
  Tres líneas de cuerpo: la traza, la llamada y el `str()`. No hay una clase que heredar ni un
  registro donde apuntarse. Para el orquestador, `flights_agent` es indistinguible de la
  `convert_units` de `01`: una función con type hints y un docstring.
- **El docstring es el criterio de despacho.** El resumen y el bloque `Returns:` van a la
  `description` de la tool; cada entrada de `Args:` va a la descripción de su parámetro. Eso —y no
  un `if`— es lo que el modelo lee para decidir a quién llamar. Es el mismo principio que en `01`
  (los type hints **son** el esquema) y que el `Field(description=...)` de `05`. Si el despacho
  sale mal, el sitio donde se arregla es el docstring.
- **Quién decide cambió de sitio.** En `05` decidía una línea de Python después de que el modelo
  produjera un `Route`; el modelo clasificaba pero no despachaba. Aquí el modelo hace las dos
  cosas dentro de su bucle de herramientas, y `agent.py` no tiene una sola línea de despacho:
  `grep -cE "^\s*elif" agent.py` da `0`, y no hay ninguna llamada a `flights(...)` fuera de su
  envoltorio.
- **No delegar también es una decisión.** Una pregunta general (*"¿necesito pasaporte en la UE?"*)
  se resuelve con **1** llamada, `0` `toolUse` y **ninguna** traza `[tool]`. No es un error ni un
  silencio: es el orquestador decidiendo que no hace falta un especialista. Un router no puede
  hacer eso sin una rama `other` escrita a mano.
- **Los dos niveles, y por qué el especialista necesita su propia tool.** Cada especialista tiene su
  `@tool` de datos con valores arbitrarios. Sin ella, "agente como herramienta" se leería igual que
  "prompt como herramienta": no habría forma de distinguir a un sub-agente que trabaja de uno que
  improvisa. Con ella, `IB-4417` en la respuesta final es la prueba de que hubo dos niveles.
- **La frontera entre niveles es una cadena de texto.** El especialista no ve la petición original
  ni el historial del orquestador: solo recibe el argumento `request` que el modelo escribió para
  él. Es la misma frontera débil de `03` y `04`, ahora entre niveles de la jerarquía. Si el
  orquestador resume mal la petición, el especialista trabaja sobre el resumen y no se entera.
- **El coste ya no se lee en el código.** `05` costaba 2 llamadas fijas, con 4 ramas o con 40. Aquí
  son 1, 4, 6 o 7 según lo que decida el modelo (tabla más abajo). Ese es el precio real de mover
  la decisión del código al modelo, y conviene mirarlo antes de anidar un tercer nivel.
- **La profundidad es finita por construcción.** El grafo de herramientas es acíclico: el
  orquestador conoce a los especialistas, los especialistas no le conocen a él ni entre sí. Por eso
  el ejemplo no necesita un contador de profundidad ni un límite de recursión. Si un día dos
  agentes se tuvieran como herramienta mutuamente, haría falta — y ahí ya estarías pidiendo un
  `Swarm`.
- **Los dos especialistas corren a la vez, sin una línea de `asyncio`.** Cuando el orquestador
  emite los dos `toolUse` en el mismo turno, el `Agent` los ejecuta con su `ConcurrentToolExecutor`
  por defecto. Medido con un proveedor falso de 0,4 s por llamada: **1,62 s de reloj frente a los
  2,40 s** que costarían las seis llamadas en secuencia, y **3 hilos distintos** vieron una llamada
  al modelo. `04` paralelizaba escribiendo `asyncio.gather`; aquí el paralelismo aparece sin
  escribir nada — y por eso mismo tampoco se controla desde el ejemplo.

**Por qué la llamada anidada no se bloquea.** Es el riesgo técnico obvio del patrón: `flights_agent`
llama a un `Agent` síncrono **desde dentro** del bucle de herramientas del orquestador, que ya corre
sobre un bucle de `asyncio`. Debería ser un bucle anidado, y no lo es. `Agent.__call__` no ejecuta
nada en el hilo del llamante: delega en `strands._async.run_async`, que lanza `asyncio.run(...)` en
un hilo de un `ThreadPoolExecutor` y espera el `future`. No hay bucle dentro de otro bucle: hay
**otro hilo con su propio bucle**. La consecuencia práctica es que el envoltorio tiene que ser
síncrono (`def` + `str(flights(request))`), que es exactamente lo que hace este archivo. La versión
`async def` + `await flights.invoke_async(...)` también funcionaría, pero es material de otro
ejemplo y aquí sobraría.

### Las cinco diferencias con `05`, y por qué

| Diferencia | Por qué |
|---|---|
| **Vuelven las `@tool`**, cuatro, tras dos ejemplos sin ninguna | Son el contenido del ejemplo: dos envuelven un agente y dos dan de comer al segundo nivel. Sin las de datos, "agente como herramienta" no se distinguiría de "prompt como herramienta" |
| **Desaparecen `pydantic` y `enum`** | El criterio de despacho ya no es un esquema validado, es un docstring en lenguaje natural. Se gana una dependencia menos y dos importaciones menos; se pierde el conjunto cerrado de destinos: el modelo puede llamar a cero, a uno, a los dos o al mismo dos veces, y eso no lo cierra nadie |
| **Tres agentes en vez de cinco** | Un orquestador y dos especialistas. Menos agentes pero más piezas, porque ahora cada especialista tiene su propia herramienta y su propio bucle. El archivo mide **110 líneas** frente a las 83 de `05` |
| **El coste deja de ser constante** | De 2 llamadas fijas a 1, 4, 6 o 7. Es la consecuencia directa de mover la decisión del código al modelo, y por eso el README la tabula en vez de esconderla |
| **La prueba principal cambia de sitio** | `05` demostraba su tesis con los **historiales vacíos** de las ramas que no corrieron. Aquí la prueba son los **`toolUse`** del orquestador: qué herramientas llamó el modelo. Los historiales vacíos siguen valiendo, pero como prueba secundaria |

### `Agent.as_tool()`: el primitivo nativo que este ejemplo no usa

Strands trae este patrón de fábrica, y conviene saberlo para no reimplementar a mano algo que ya
existe **sin saber que existe**. La firma real de la versión instalada (1.55.1):

```python
Agent.as_tool(*, name=None, description=None, preserve_context=False, delegate=False) -> AgentTool
```

Este ejemplo escribe el envoltorio a mano **a propósito**: el objetivo es enseñar que un
agente-herramienta no es magia del framework, sino una función que llama a un `Agent`. Si lo
resolviéramos con `as_tool()`, el lector vería una llamada a un método y no el mecanismo. Las
diferencias que importan si decides usarlo:

| | Envoltorio a mano (este ejemplo) | `Agent.as_tool()` |
|---|---|---|
| Nombre de la tool | El de la función (`flights_agent`) | El argumento `name=`, o el del agente |
| Descripción | El docstring: resumen + `Returns:` | El argumento `description=` |
| Parámetro | El que tú declares, con **tu** descripción (`request: The trip in one sentence, in the user's language.`) | **Siempre** `input: str`, con la descripción fija *"The input to send to the agent tool."* |
| Historial del sub-agente | Se resetea **por corrida**, en `run_trip()` | `preserve_context=False` por defecto: se resetea **por llamada** |
| Última llamada del orquestador | Siempre la hace, para redactar el plan | `delegate=True` devuelve la respuesta del sub-agente directamente al usuario y se la ahorra |

La diferencia del parámetro es la que más pesa en la práctica: con `as_tool()` pierdes el sitio
donde este ejemplo pone la mitad del criterio de despacho. Disponibilidad por versión: `as_tool()`
desde **1.47.0**, el argumento `delegate=` desde **1.53.0**.

## Configuración y Pruebas

### Prerrequisitos

- Python 3.10 o superior
- Una `OPENAI_API_KEY` en un `.env` local
- **Sin AWS** y **sin Node.js**, igual que en `03`, `04` y `05`.
- El `requirements.txt` **quita** una línea frente a `05`: sale `pydantic`, que este ejemplo no
  importa, y vuelve a ser idéntico al de `01`–`04`. El ejemplo con más piezas de los seis —tres
  agentes, cuatro herramientas, dos niveles— tiene el `requirements.txt` más corto.

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

> **Las líneas `[tool] … ──►` salen a mitad de la espera.** Aparecen en cuanto el orquestador decide
> llamar, antes de que el especialista empiece a pensar, y el silencio que viene después es el
> segundo nivel trabajando: el streaming está desactivado (`callback_handler=None`). Que la traza
> vaya **antes** de la llamada no es cosmético — es lo que hace visible la delegación mientras
> ocurre, igual que el `[router]` de `05` salía antes del especialista. Si no ves ninguna línea
> `[tool]`, el orquestador decidió contestar él.

### Transcripción de ejemplo

Corrida real contra `gpt-5.4-nano`, con las cuatro peticiones seguidas en la misma sesión.

```
TripDesk: Tell me about your trip. Type 'exit' to quit.

Using LLM model: gpt-5.4-nano

Trip >   [tool] flights_agent ──►
  [tool] hotels_agent ──►

**Vuelos (especialista de vuelos):** Para Lisboa, encontré el vuelo **IB-4417 (08:05-09:25) por 412 EUR**.

**Hotel (especialista de hoteles):** Encontré **“Casa Kraken, Alfama”** ( **94 EUR/noche** ) para Lisboa.

Trip >   [tool] hotels_agent ──►

En Oporto, esta agencia te recomienda **Pensao Vela Roja (Ribeira)** — **77 EUR/noche**.

Trip > 
En general, para viajar dentro de la UE necesitas un documento de identidad válido (normalmente pasaporte o DNI según el país), pero no suele ser obligatorio “pasaporte” si tu DNI es aceptado para ese destino; revisa siempre los requisitos exactos del país al que vas y que tu documento esté vigente.

Trip >   [tool] flights_agent ──►

No encuentro “Tokyo” en el listado de vuelos disponibles (solo aparecen opciones a Lisboa, Oporto y Oslo). ¿A qué ciudad exacta te refieres o tienes un aeropuerto/país alternativo cercano a Tokio?

Trip > exit
```

Las cuatro peticiones fueron, en orden: *"3 días en Lisboa, necesito vuelo y hotel"*, *"¿dónde duermo
en Oporto?"*, *"¿necesito pasaporte para viajar dentro de la UE?"* y *"quiero volar a Tokio la semana
que viene"*. Fíjate en el recuento de trazas: **dos**, **una**, **ninguna**, **una**. Ese recuento no
lo decide `agent.py`.

**Dónde está la prueba de que hubo dos niveles.** En los `toolUse` de los historiales. Esta es la
salida de un driver que importa el `agent.py` real, llama a `run_trip()` una vez con la petición de
Lisboa y luego lee `agent.messages` en los tres agentes:

```
orquestador: ['flights_agent', 'hotels_agent'] 4 msgs
flights: ['search_flights'] 4 msgs
hotels: ['search_hotels'] 4 msgs
IB-4417 en el plan: True | Casa Kraken en el plan: True
```

Tres cosas que la prosa no puede fingir. El orquestador llamó a **los dos especialistas** y no a
otra cosa. Cada especialista llamó a **su** herramienta: ninguno contestó de memoria. Y `IB-4417`
—que no está en ningún prompt, solo en un `dict` de Python— sobrevivió los **cuatro saltos**
(`search_flights` → `flights` → `flights_agent` → `orchestrator`) hasta el plan final. Los
historiales vacíos siguen valiendo como prueba secundaria, igual que en `05`: en la petición de
Oporto, `flights` termina la corrida con **0 mensajes**, porque nadie le llamó.

**El coste de que decida el modelo.** Medido con un proveedor falso, guionando los cuatro escenarios:

| Escenario | Llamadas al modelo `(orquestador, flights, hotels)` | Total | `toolUse` del orquestador |
|---|---|---|---|
| No delega (pregunta general) | `(1, 0, 0)` | **1** | `[]` |
| Un especialista | `(2, 0, 2)` | **4** | `['hotels_agent']` |
| Los dos especialistas | `(2, 2, 2)` | **6** | `['flights_agent', 'hotels_agent']` |
| El mismo, dos veces en un turno | `(3, 4, 0)` | **7** | `['flights_agent', 'flights_agent']` |

Frente a las **2 llamadas fijas** de `05`, con 4 ramas o con 40. Y el último escenario enseña algo
que el reseteo hace explícito: `flights` acumula **8 mensajes** y dos `search_flights` en ese turno,
porque `messages.clear()` es **por corrida**, no por llamada. Un especialista al que llaman dos
veces recuerda la primera.

## Información Adicional

**Los datos son inventados.** El catálogo tiene tres ciudades y los códigos, horarios y precios no
corresponden a ningún vuelo ni hotel real: `IB-4417`, `Casa Kraken`, `Pensao Vela Roja`. Son
arbitrarios a propósito, porque ningún modelo puede adivinarlos y por eso sirven de prueba. Para
cualquier otra ciudad la tool devuelve un texto de error con el catálogo —no lanza una excepción— y
el especialista lo transmite tal cual: eso es la cuarta petición de la transcripción, y está ahí a
propósito. No trates ninguna de estas respuestas como información de viaje real.

**Una nota sobre la ciudad en otro idioma.** La primera corrida de este ejemplo falló en la petición
de Oporto: el especialista llamó a `search_hotels("Oporto")`, que no está en el catálogo, y el plan
acabó pidiendo confirmación en vez de dar el hotel. Se arregló donde manda el patrón —en el
docstring, que ahora dice `Destination city, in English: translate it first, e.g. "Oporto" is
"Porto"`— y no con una tabla de sinónimos ni con un `if`. La transcripción de arriba es la corrida
posterior al arreglo.

### Estructura del proyecto

```
06-agents-as-tools/
├── agent.py            # catálogos + 2 tools de datos + 3 prompts + specialist() + 2 especialistas + 2 envoltorios + orchestrator + run_trip + CLI (110 líneas, 4 @tool)
├── requirements.txt    # 3 líneas — idéntico al de 01–04
├── .env.example        # 2 variables
├── README.md           # este archivo
└── .env                # tu clave; ignorado por git, no se commitea
```

### Limpieza

No hay nada que limpiar: el ejemplo no crea recursos, no lanza subprocesos y no escribe ningún
archivo. Los tres historiales se vacían al principio de cada corrida, y los hilos que el SDK usa
para los sub-agentes mueren con el proceso. Para borrar el entorno: `rm -rf .venv`.

### Recursos adicionales

- [Strands Agents — documentación](https://strandsagents.com/)
- [Agentes como herramientas](https://strandsagents.com/latest/documentation/docs/user-guide/concepts/multi-agent/agents-as-tools/)
  — el patrón de este ejemplo, y de donde sale `Agent.as_tool()`
- [Herramientas en Strands: el decorador `@tool`](https://strandsagents.com/latest/documentation/docs/user-guide/concepts/tools/python-tools/)
  — por qué el docstring y los type hints **son** el esquema que lee el modelo
- [Modelos de OpenAI en Strands](https://strandsagents.com/latest/documentation/docs/user-guide/concepts/model-providers/openai/)
- [Multi-agent en Strands](https://strandsagents.com/latest/documentation/docs/user-guide/concepts/multi-agent/multi-agent-patterns/)
  — el catálogo de primitivas. `07-agent-graph` y `08-agent-swarm` son las **dos respuestas del
  framework a esta misma pregunta**: una declara la topología y la fija, la otra la disuelve del
  todo. Este ejemplo existe, entre otras cosas, para poder compararlas con algo escrito a mano
