# 05 · Router de agentes (clasificar y despachar)

Un agente lee la petición y devuelve **una decisión tipada**, no texto: un `Route` con una
`category` sacada de un `Enum` cerrado y un `reason` de doce palabras. Con esa categoría, el código
indexa un `dict` y llama a **un** especialista de los cuatro. Los otros tres no se enteran. El
router entero son dos líneas de Python, y solo la primera la pone Strands.

`05` es `04` con la misma fábrica de agentes y el compromiso cambiado: **donde corrían las tres
ramas, ahora corre una.** Mismo proveedor de modelo, mismo `load_dotenv()`, mismo `MODEL_ID`, mismo
`callback_handler=None`, mismo reseteo por corrida, mismo bucle CLI. Lo único que cambia es que hay
una decisión en medio — y por eso el ejemplo puede demostrar su tesis con los historiales.

```
        04 (abanico)                           05 (router)

  proposal ──┬──► pros  ──┐            request ──► classifier
             ├──► cons  ──┤ gather                     │ Route(category, reason)
             └──► risks ──┘                            ▼
                       │                        SPECIALISTS[category]
                       ▼                     ┌────┬────┴────┬────┐
                   synthesis                 ▼    ✗         ✗    ✗
                                          billing técnico ventas other
   3 ramas + 1 fan-in                        │
   coste LINEAL en el nº de ramas            ▼
   siempre corren las tres               la respuesta
                                   2 llamadas, sean 4 ramas o 40
                                   coste CONSTANTE · corre exactamente una
```

La diferencia no es de topología solamente, es de coste: el abanico paga todas las ramas siempre;
el router paga dos llamadas aunque haya cuarenta destinos.

## Detalles del ejemplo

| Información | Detalles |
|---|---|
| Características de Strands | `Agent`, `structured_output_model=` en la **invocación**, `AgentResult.structured_output`, `OpenAIResponsesModel`, `callback_handler=None`, `agent.messages` |
| Patrón de agente | Router / dispatcher: el modelo clasifica, el código despacha. Sin orquestador |
| Herramientas | **Ninguna escrita a mano** — pero el SDK genera una en tiempo de ejecución a partir del esquema |
| Modelo | `gpt-5.4-nano` (configurable con `MODEL_ID`) |
| Complejidad | Principiante |

## Conceptos clave

- **Un router es salida estructurada + una tabla, y solo lo primero lo pone Strands.** La primera
  línea (`classifier(request, structured_output_model=Route).structured_output`) es del framework;
  la segunda (`SPECIALISTS[route.category](request)`) es una indexación de `dict` que podría estar
  en cualquier programa sin LLM. Esa asimetría es la tesis, la misma forma que en `03` (encadenar
  es asignar) y `04` (paralelizar es `gather`).
- **El `Enum` cierra el conjunto de destinos.** El modelo no puede devolver una quinta categoría:
  el valor viaja al esquema como `"enum": ["billing","technical","sales","other"]`. Y si lo
  intenta, Pydantic lo rechaza, el SDK le devuelve el error y el modelo se corrige — **sin una
  línea de código de reintento en `agent.py`**. Un `str` libre obligaría a normalizar, comparar y
  fallar en silencio con la tercera forma en que el modelo escriba la categoría.
- **El criterio vive en los `Field(description=...)`, no en el `system_prompt`.** Es lo que el
  modelo recibe de verdad. Por eso el `CLASSIFIER_PROMPT` es el prompt más corto del archivo, y por
  eso ajustar la clasificación se hace tocando el `description`, nunca añadiendo un `if`. Mismo
  principio que en `01`: los type hints y el docstring de un `@tool` **son** el esquema.
- **La tabla de despacho es total.** `other` es una rama con su agente, no un `else`. `SPECIALISTS`
  tiene una entrada por cada valor del `Enum`, así que `[c for c in Category if c not in
  SPECIALISTS]` está vacío. Olvidarse de una rama sería un `KeyError` inmediato y ruidoso; un
  `else` lo convertiría en una respuesta silenciosamente mala.
- **El coste es constante en el número de ramas.** Dos llamadas al modelo por turno, haya 4
  destinos o 40. El abanico de `04` es lineal: paga las tres siempre. Cuando las ramas no se
  necesitan entre sí y **todas** aportan, el abanico; cuando solo una aplica, el router.
- **La trampa: `str(result)` no devuelve el texto.** `AgentResult.__str__` da prioridad a la salida
  estructurada, así que `str(classifier(..., structured_output_model=Route))` devuelve el **JSON**
  del objeto. Hay que leer `.structured_output`. Por eso las dos llamadas del archivo se leen
  distinto a propósito: `.structured_output` en la del clasificador, `str(...)` en la del
  especialista, que no lleva esquema y sí devuelve texto.
- **`Agent.structured_output()` está deprecado.** Casi toda la documentación y los tutoriales de
  fuera siguen enseñando ese método; el SDK instalado emite un `DeprecationWarning` que dice
  literalmente *"You should pass in `structured_output_model` directly into the agent invocation"*.
  Este ejemplo usa el argumento de invocación. Si lo ves con el método viejo por ahí fuera, está
  desactualizado, no es otra forma igual de válida.
- **La llamada con esquema SÍ escribe historial.** Tras clasificar, el clasificador tiene 3
  mensajes (`user` / `assistant` con el `toolUse` / `user` con el `toolResult`). Por eso el
  `messages.clear()` alcanza a los **cinco** agentes sin excepciones — era el método deprecado, y
  no este, el que no tocaba el historial.
- **El contrato de vuelta sigue siendo texto libre.** El especialista devuelve prosa sin estructura,
  igual que en `03` y `04`. Este ejemplo arregla **media** frontera: la de ida.
  `12-structured-output` va a por la otra.

**Sobre la tool que no escribiste.** `grep -c "@tool" agent.py` da `0` y es cierto: el autor no
define ninguna herramienta. Pero en tiempo de ejecución **sí hay una tool**. El SDK construye un
`StructuredOutputTool` a partir del `BaseModel`, lo registra con el nombre de la clase (`Route`) y
lo mete en el `tool_spec` de esa única invocación; el modelo la llama, y el SDK saca el objeto del
`toolUse`. Las descripciones de tus `Field` son las descripciones de los parámetros de esa tool.
Merece la pena decirlo en voz alta en vez de esconderlo tras el `grep`: la salida estructurada no
es un modo aparte del modelo, es una llamada a herramienta con el resultado desempaquetado.

## Prerrequisitos

- Python 3.10 o superior
- Una `OPENAI_API_KEY` en un `.env` local
- **Sin AWS** y **sin Node.js**, igual que en `03` y `04`.
- El `requirements.txt` añade **una sola línea** frente a `01`–`04`: `pydantic>=2.4.0`. No instala
  nada nuevo — `strands-agents` ya la exigía con ese mismo piso, así que ya estaba en el entorno.
  Se declara porque `agent.py` la importa directamente, y todo lo que un ejemplo importa y no es
  biblioteca estándar tiene que estar en su `requirements.txt`.

## Estructura del ejemplo

| Archivo | Descripción |
|---|---|
| `agent.py` | `Category` + `Route`, los cinco prompts, la fábrica `desk()`, `classifier` + `SPECIALISTS`, `run_router()` y el CLI |
| `requirements.txt` | 4 dependencias: las 3 de `01`–`04` más `pydantic` |
| `.env.example` | Plantilla de las 2 variables; se copia a `.env` |
| `README.md` | Este archivo |

## Cómo ejecutarlo

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

> **La línea `[router]` sale a mitad de la espera.** Aparece en cuanto vuelve la primera llamada, y
> el silencio que viene después es el especialista pensando: el streaming está desactivado
> (`callback_handler=None`). Ese orden no es cosmético — imprimir la decisión **antes** del efecto
> es lo que hace depurable un router: si la respuesta es mala, ya sabes si falló la clasificación o
> el especialista.

## Transcripción de ejemplo

Corrida real contra `gpt-5.4-nano`, con las cinco peticiones seguidas en la misma sesión.

```
SupportRouter: Describe your issue. Type 'exit' to quit.

Using LLM model: gpt-5.4-nano

Request > me habéis cobrado dos veces la factura de marzo

[router] billing ──► Cobro duplicado de la factura de marzo
Entiendo. Para revisar un doble cobro necesito: número de factura de marzo, fecha e importe de ambos cargos, y método de pago (tarjeta/PayPal) con los últimos 4 dígitos. También, si puedes, captura o IDs de transacción. Yo comprobaría en el sistema si son dos cargos separados o una retención/reverso.

Request > la app peta al abrir desde la última actualización

[router] technical ──► La app Peta falla al abrir tras actualizar
Entiendo. La app "Peta" falla al abrir tras la última actualización. Primero: reinicia el móvil y fuerza cierre de la app. Luego borra caché (y si sigue, datos) y actualiza/desinstala-reinstala. Confirma: modelo, versión de Android/iOS, versión de la app y si aparece algún mensaje/error. ¿Pasa en Wi‑Fi o también con datos?

Request > ¿cuánto cuesta subir al plan de equipos?

[router] sales ──► Pregunta sobre precio y plan de equipos
Depende de tu plan actual, del número de equipos/usuarios y del país/moneda. Para decirte el precio exacto de "subir al plan de equipos", dime: tu plan actual, cuántos equipos quieres incluir y tu país (o moneda). Si prefieres, también puedo prepararte una cotización.

Request > ¿trabajáis los festivos?

[router] other ──► Consulta sobre horarios de atención en festivos
No puedo confirmarlo aún porque esto no encaja en una especialidad; ¿me dices en qué ciudad/sucursal y para qué tipo de festivo (local o nacional) necesitas saber si atendemos?

Request > me han cobrado de más por culpa de un error de la app

[router] billing ──► Cobro excesivo por error en la app; solicitar ajuste/reembolso
Lamento el error. Para revisarlo, necesito: fecha y hora del cobro, importe, moneda, método de pago (tarjeta/PayPal/etc.) y el número de factura/últimos 4 dígitos. Verificaría el cargo correcto vs. duplicado/importe aplicado, historial de suscripción y notas de la plataforma. En cuanto me pases esos datos, te indico cómo solicitar reembolso.

Request > exit
```

**Dónde está la prueba de que hubo selección y no abanico.** En los historiales. `04` lo demostraba
con un reloj; aquí el reloj no sirve —solo corre una rama— y la prueba es que las otras tres
**no tienen ni un mensaje**. Esta es la salida de un driver de cuatro líneas que importa el
`agent.py` real, llama a `run_router()` una vez y luego cuenta `len(agent.messages)` en los cinco:

```
[router] billing ──► Cobro duplicado de la factura de marzo
Entiendo. Para revisar por qué os han cobrado dos veces la factura de marzo, necesito: número de factura, fecha e importe de ambos cargos, método de pago (tarjeta/transferencia), y los últimos 4 dígitos o referencia bancaria. Comprobaré si se trata de un cargo duplicado o una retención/rectificación y, si procede, iniciamos el reembolso.
classifier 3
billing 2
technical 0
sales 0
other 0
```

`classifier 3` (la petición, el `toolUse` del modelo, el `toolResult`), `billing 2` (la petición y
su respuesta) y **tres ceros**. Tres historiales vacíos no se pueden fingir con prosa: o el
despacho eligió una rama, o no salen a cero. Son también el recuento de las llamadas al modelo:
`3 + 2` mensajes son exactamente **dos** invocaciones, ni una más, sean cuatro las ramas o cuarenta.

**Dónde está la prueba de que la decisión la tomó el modelo.** En el `reason`. *"Cobro duplicado de
la factura de marzo"* y *"Consulta sobre horarios de atención en festivos"* no están en ninguna
parte de `agent.py`: el código solo imprime `f"[router] {route.category.value} ──► {route.reason}"`.
Si el motivo lo pusiera el código, sería el mismo texto en los cinco turnos.

**El caso frontera está en la transcripción a propósito.** La quinta petición —*"me han cobrado de
más por culpa de un error de la app"*— lleva la palabra *error* y aun así sale `billing`, que es lo
que el usuario necesita. Eso lo sostienen dos cosas, ninguna de las cuales es un `if`: la línea
`Judge what the user needs, not the words they used` del `CLASSIFIER_PROMPT`, y unas descripciones
escritas por **competencia** y no por vocabulario. Si un día clasifica mal, el sitio donde se
arregla es el `Field(description=...)`, no el despacho.

Y la segunda petición no arrastra nada de la primera: la respuesta técnica no menciona ni la
factura ni marzo. Eso lo garantiza el `messages.clear()` sobre los cinco agentes, no la buena
voluntad del modelo.

**Este ejemplo no está fundamentado.** Los cuatro especialistas trabajan sin herramientas y sin
acceso a ninguna cuenta, sistema ni lista de precios. Por eso sus prompts les obligan a decir qué
comprobarían y qué les falta —y a `SALES` a no inventar ninguna cifra— en vez de fingir que
consultan algo. Se ve en la transcripción: los cuatro piden datos, ninguno los da. No trates sus
respuestas como información de una cuenta real.

### Las cuatro diferencias con `04`, y por qué

| Diferencia | Por qué |
|---|---|
| **Desaparece `asyncio`** y el archivo vuelve a ser síncrono | Un router es secuencial por naturaleza: primero se clasifica, después se llama a **un** especialista. No hay dos llamadas independientes que solapar, y un `gather` sobre una sola rama sería andamiaje muerto. Mantenerlo contradiría justo la regla que enseña `04`: se paraleliza lo que no se necesita entre sí. Coste aceptado: se pierde la prueba del reloj, y la sustituyen los historiales |
| **Aparecen `enum.Enum` y `pydantic`** | La decisión tiene que salir de un conjunto cerrado y llegar validada: es el contenido del ejemplo. Cuesta dos importaciones y una cuarta línea en `requirements.txt`. A cambio desaparece cualquier parseo de texto — ni un `.strip()`, ni un `.lower()`, ni un `json.loads` |
| **Cinco agentes en vez de cuatro** | Cuatro ramas más el clasificador, porque `other` es una rama con su agente y no un `else`. Cuesta cinco `system_prompt`; se contiene manteniéndolos cortos y moviendo el criterio al esquema, y el archivo mide **83 líneas** frente a las 94 de `04` |
| **El dict se indexa por `Category`, no por `str`** | Permite que `SPECIALISTS[route.category]` no tenga que normalizar nada y que la totalidad de la tabla se compruebe de un vistazo (`for c in Category`). Coste: ninguno |

**Nota: un router no necesita un LLM.** Si tienes muchas clases y ejemplos etiquetados de sobra, un
clasificador entrenado es más barato, más rápido y más estable que una llamada al modelo. La
arquitectura de este archivo no cambiaría: solo cambia **quién produce el `Route`**. El `Enum`, el
dict de despacho y la línea de la indexación se quedan exactamente igual. El LLM es una opción
razonable cuando las categorías son pocas, las fronteras son borrosas y no tienes datos
etiquetados — que es el caso de este ejemplo.

## Estructura del proyecto

```
05-router-agent/
├── agent.py            # Category + Route + 5 prompts + desk() + SPECIALISTS + run_router + CLI (83 líneas, cero @tool)
├── requirements.txt    # 4 líneas — las 3 de 01–04 más pydantic
├── .env.example        # 2 variables
├── README.md           # este archivo
└── .env                # tu clave; ignorado por git, no se commitea
```

## Limpieza

No hay nada que limpiar: el ejemplo no crea recursos, no lanza subprocesos y no escribe ningún
archivo. El historial de los cinco agentes se vacía al principio de cada corrida, y la tool que el
SDK genera a partir del esquema vive solo durante esa invocación. Para borrar el entorno:
`rm -rf .venv`.

## Recursos adicionales

- [Strands Agents — documentación](https://strandsagents.com/)
- [Salida estructurada en Strands](https://strandsagents.com/latest/documentation/docs/user-guide/concepts/agents/structured-output/)
  — la página que cita el propio `DeprecationWarning` del SDK al apuntar de `Agent.structured_output()`
  hacia `structured_output_model=` en la invocación
- [Pydantic — documentación](https://docs.pydantic.dev/latest/) — de dónde salen el `BaseModel`, el
  `Field(description=...)` que **es** el criterio de clasificación, y la validación que da el
  reintento gratis
- [Modelos de OpenAI en Strands](https://strandsagents.com/latest/documentation/docs/user-guide/concepts/model-providers/openai/)
- [Multi-agent en Strands](https://strandsagents.com/latest/documentation/docs/user-guide/concepts/multi-agent/multi-agent-patterns/)
  — el catálogo de primitivas (grafos, swarms, agentes como herramientas) que este ejemplo
  **deliberadamente no usa**. `07-agent-graph` construirá este mismo triage con `GraphBuilder` y una
  arista condicional, y comparar los dos es la mejor forma de ver qué aporta y qué cuesta declarar
  el despacho en vez de escribirlo
