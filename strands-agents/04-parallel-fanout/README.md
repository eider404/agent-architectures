# 04 · Abanico paralelo de agentes (fan-out / fan-in)

Tres agentes leen **la misma** propuesta a la vez —uno busca los pros, otro los contras, otro los
riesgos— y un cuarto espera a los tres y dicta un veredicto. El abanico entero es **una línea de
Python**: un `asyncio.gather` sobre `invoke_async`. No hay orquestador, ni `GraphBuilder`, ni
`Swarm`, ni hilos, ni procesos, ni herramientas.

`04` es `03` con la misma fábrica de agentes y la topología cambiada: **donde había una fila hay
un abanico.** Mismo proveedor de modelo, mismo `load_dotenv()`, mismo `MODEL_ID`, mismo
`callback_handler=None`, mismo reseteo por corrida, mismo bucle CLI, las mismas tres
dependencias. Lo único que cambia es quién espera a quién — y por eso el ejemplo puede demostrar
su tesis con un reloj.

```
        03 (secuencial)                        04 (abanico)

  topic ──► research ──► notes          proposal ──┬──► pros  ──┐
              │                                    ├──► cons  ──┤ asyncio.gather
              ▼                                    └──► risks ──┘   (a la vez)
            outline ──► outline                              │
              │                                              ▼
              ▼                                          synthesis ──► VERDICT
             draft ──► draft
                                          3 ramas + 1 fan-in · cero herramientas
  total = suma de las etapas              total ≈ la rama más lenta
```

La condición para pasar de lo primero a lo segundo no es técnica, es de **dependencias**: se
paraleliza lo que no se necesita entre sí.

## Detalles del ejemplo

| Información | Detalles |
|---|---|
| Características de Strands | `Agent`, `Agent.invoke_async`, `OpenAIResponsesModel`, `callback_handler=None`, `agent.messages` |
| Patrón de agente | Fan-out / fan-in: tres ramas en paralelo y un agregador, sin orquestador |
| Herramientas | **Ninguna** — el ejemplo no define ni consume ninguna |
| Modelo | `gpt-5.4-nano` (configurable con `MODEL_ID`) |
| Complejidad | Principiante |

## Conceptos clave

- **`asyncio.gather` sobre `invoke_async` no es una API multi-agente.** Es `asyncio` con otra
  ropa. Strands no aporta aquí una primitiva de paralelismo: aporta un método `async` por agente,
  y el resto lo pone la biblioteca estándar. Todo el andamiaje asíncrono del archivo cabe en
  **tres líneas**: `import asyncio`, el `gather` y el `asyncio.run` del CLI.
- **La regla: se paraleliza lo que no se necesita entre sí.** El contraejemplo es el propio `03`:
  allí el `outline_agent` no puede empezar sin las viñetas del `research_agent`, así que un
  `gather` no habría ahorrado ni un segundo. Aquí ninguna rama necesita a otra, y por eso el
  total es ≈ la más lenta en vez de la suma. La pregunta no es *"¿puedo paralelizar esto?"* sino
  *"¿alguna de estas llamadas necesita el resultado de otra?"*.
- **El paralelismo es de E/S, en un solo hilo.** No hay `threading` ni `multiprocessing`. Las
  tres llamadas están esperando a la red al mismo tiempo dentro del mismo bucle de eventos, que
  es exactamente para lo que sirve `asyncio` y exactamente lo que hace falta aquí.
- **La trampa del patrón: el lock de invocación es por instancia de `Agent`.** Cada `Agent` trae
  su propio controlador de concurrencia en modo `THROW`, así que reusar **el mismo** agente en
  dos ramas del `gather` no da una respuesta mezclada: lanza en tiempo de ejecución. Por eso
  `branch()` construye una instancia por rama y son cuatro objetos distintos. Es el error clásico
  al pasar de secuencial a paralelo.
- **Dentro de una corrutina hay que usar `invoke_async`, no `__call__`.** `agent(...)` es el
  invocable síncrono de `01`–`03`; llamarlo dentro de un `async def` arranca un bucle de eventos
  anidado y revienta. Las **cuatro** llamadas al modelo de este archivo tienen la misma forma,
  incluido el fan-in, que no necesita concurrencia pero sí coherencia.
- **El contrato entre ramas sigue siendo texto sin estructura.** Las etiquetas `P1..R3` son una
  convención sostenida por un `system_prompt`, igual que en `03`: la forma más frágil de las del
  repositorio. `12-structured-output` existe para arreglar eso.
- **Un agente es conversacional por defecto; un abanico no.** Cada corrida empieza vaciando
  `agent.messages` de los **cuatro** agentes — es fácil olvidarse del agregador.

## Prerrequisitos

- Python 3.10 o superior
- Una `OPENAI_API_KEY` en un `.env` local
- **Sin AWS** y **sin Node.js**, igual que en `03`.
- El ejemplo que introduce la concurrencia **no añade ni una dependencia**: `asyncio` y `time`
  son biblioteca estándar, y el `requirements.txt` es idéntico, línea por línea, al de `01` y
  `03`.

## Estructura del ejemplo

| Archivo | Descripción |
|---|---|
| `agent.py` | Los cuatro prompts, la fábrica `branch()`, `ANALYSTS` + `synthesis_agent`, `timed()`, `run_fanout()` y el CLI |
| `requirements.txt` | Las 3 dependencias, idénticas a las de `01` y `03` |
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

> **La consola se queda en silencio mientras las tres ramas piensan.** El streaming está
> desactivado (`callback_handler=None`), así que tras el `[fan-out] lanzando 3 analistas en
> paralelo...` no se imprime nada durante unos segundos. La señal de vida son las tres líneas de
> tiempo, y salen **en cuanto cada rama termina**: por eso aparecen en desorden respecto a como
> están declaradas. Ese desorden es la prueba visual de que corrieron a la vez.

## Transcripción de ejemplo

Corrida real contra `gpt-5.4-nano`, con dos propuestas seguidas en la misma sesión.

```
ParallelFanout: Give me a proposal. Type 'exit' to quit.

Using LLM model: gpt-5.4-nano

Proposal > migrar el monolito a microservicios en 6 meses

[fan-out] lanzando 3 analistas en paralelo...
  pros   ──►   3.1s
  cons   ──►   2.9s
  risks  ──►   3.9s
  total:   4.4s  (en secuencia habrian sido 9.9s)

## PROS
P1 - Plazo claro de 6 meses para completar la migración, reduciendo incertidumbre y acelerando el time-to-value.
P2 - Enfoque en microservicios mejora escalabilidad y flexibilidad al aislar funciones y permitir despliegues independientes.
P3 - Moderniza la arquitectura, facilitando mantenimiento y evolución continua sin depender de un monolito rígido.

## CONS
C1 - Plazo de 6 meses es poco realista para un monolito grande, con alto riesgo de retrasos y deuda técnica.
C2 - Migración a microservicios sin estrategia gradual incrementa fallos de integración, latencia y complejidad operativa.
C3 - Falta de detalle sobre datos, compatibilidad y pruebas end-to-end puede provocar pérdida de funcionalidad en producción.

## RISKS
R1 - Plazo de 6 meses insuficiente para refactorizar y estabilizar la arquitectura, elevando riesgo de fallos en producción.
R2 - Integraciones y dependencias del monolito pueden romperse durante la descomposición, causando inconsistencias de datos y caídas.
R3 - Falta de diseño de observabilidad, seguridad y gestión de configuraciones en microservicios puede derivar en vulnerabilidades.

[fan-in] synthesis ──►
VERDICT: conditional
- La propuesta da claridad de time-to-value con plazo de 6 meses y moderniza hacia microservicios para mejorar escalabilidad/mantenimiento. (P1, P2, P3)
- El plazo parece insuficiente para la complejidad real y falta estrategia gradual, elevando retrasos, deuda técnica y complejidad operativa. (C1, C2, R1)
- Hay brechas críticas en datos/pruebas, además de observabilidad/seguridad/configuración, con riesgo de fallos en producción y vulnerabilidades. (C3, R2, R3)

Proposal > adoptar la semana laboral de 4 dias

[fan-out] lanzando 3 analistas en paralelo...
  risks  ──►   1.4s
  cons   ──►   1.7s
  pros   ──►   1.7s
  total:   1.7s  (en secuencia habrian sido 4.9s)

## PROS
P1 - Puede aumentar la productividad y el rendimiento al reducir la fatiga y mejorar la concentración.
P2 - Disminuye el ausentismo y mejora la satisfacción del personal, fortaleciendo la retención del talento.
P3 - Reduce costes y emisiones al concentrar horas laborales y optimizar el uso de recursos.

## CONS
C1 - Podría reducir productividad en sectores dependientes de continuidad, elevando costos de coordinación y cobertura.
C2 - Riesgo de impacto en salarios, incentivos y calidad del servicio por redistribución de turnos.
C3 - Evidencia mixta y limitada; resultados podrían no generalizarse a todas las industrias o contextos laborales.

## RISKS
R1 - Disminución de productividad y cumplimiento de plazos por reducción de horas efectivas.
R2 - Conflictos operativos y cobertura insuficiente de turnos, generando retrasos y sobrecarga del personal.
R3 - Riesgo de costes ocultos (horas extra, contratación temporal) que erosionen los beneficios esperados.

[fan-in] synthesis ──►
VERDICT: conditional
- Beneficios potenciales: mayor productividad/concentración y posible reducción de ausentismo, mejorando satisfacción y retención. (P1, P2)
- La viabilidad operativa depende del contexto: puede caer productividad o requerir coordinación para cobertura continua. (C1, R2)
- Hay incertidumbre y "costes ocultos"/impactos en incentivos o cumplimiento; requiere mitigación y piloto antes de escalar. (C3, C2, R3)

Proposal > exit
```

**Dónde está la prueba de que hubo paralelismo.** El reloj, y lo imprime el propio ejemplo: la
primera propuesta tardó **4.4 s** cuando las tres ramas suman **9.9 s**, y el total es ≈ la rama
más lenta (3.9 s) más el arranque. La segunda es aún más clara: **1.7 s** contra **4.9 s**, y el
total coincide con la rama más lenta. Ese número no se puede fingir con prosa: o el abanico corre
a la vez, o no cuadra.

Lo que se reproduce de esta transcripción es la **relación** entre los tiempos, no los valores.
En otra corrida los segundos serán otros —dependen de la red, del modelo y de la longitud de cada
respuesta—; lo que se mantiene es que el total sea mucho menor que la suma.

En la segunda propuesta las líneas de tiempo salieron en orden `risks, cons, pros`, que no es el
orden en que están declaradas las ramas: es el orden en que **llegaron**. El `briefing`, en
cambio, siempre sale como `PROS / CONS / RISKS`, porque `gather` devuelve los resultados en orden
de declaración pase lo que pase. Salida reproducible arriba, concurrencia real debajo.

**Dónde está la prueba de que hubo fan-in.** Los tres bullets del veredicto citan etiquetas de
las tres familias —`P`, `C` y `R`— y esas etiquetas no existían en la propuesta que escribió el
usuario: las inventaron las ramas. El agregador solo pudo conocerlas porque recibió el briefing
entero. Es lo que aquí sustituye al `62.1371 mi` de `01` y al `8642` de `02`.

En la misma sesión, el segundo veredicto no menciona ni el monolito ni los microservicios. Eso lo
garantiza el `messages.clear()` sobre los cuatro agentes, no la buena voluntad del modelo.

**Este ejemplo no está fundamentado.** Las cuatro ramas trabajan de memoria: no tienen
herramientas ni acceso a la web. Aquí eso es correcto, porque `04` enseña una **topología**, no a
fundamentar — igual que `03` enseñaba a componer. No trates sus veredictos como análisis
verificados.

### Las cuatro diferencias con `03`, y por qué

| Diferencia | Por qué |
|---|---|
| Aparecen `asyncio` y dos `async def` (`timed`, `run_fanout`) | Es el precio literal de la tesis: sin corrutinas no hay concurrencia de E/S. Se paga una sola vez y se ve entero — tres líneas de `asyncio` y dos corrutinas. El bloque `__main__` sigue siendo **síncrono**: la única frontera entre los dos mundos es el `asyncio.run(...)` del bucle |
| Hay un cronómetro (`time.perf_counter`) | `03` podía demostrar el encadenado a ojo, mirando los títulos copiados. El paralelismo no se ve: se mide. Sin las dos líneas de tiempo el ejemplo afirmaría su tesis en vez de demostrarla, así que el cronómetro no es instrumentación opcional, es la prueba |
| `callback_handler=None` pasa de conveniente a **obligatorio** | En `03` evitaba imprimir cada etapa dos veces. Aquí, con el handler por defecto, tres respuestas en streaming se intercalarían carácter a carácter en la misma consola y la salida sería ilegible. Es la primera vez que desactivar el streaming deja de ser una comodidad |
| Las ramas viven en un dict `ANALYSTS` y no en tres constantes sueltas | En `03` las tres etapas tenían nombre propio porque cada una hacía algo distinto y en un orden fijo. Aquí son intercambiables, así que van en una estructura sobre la que se itera: es lo que permite que el `gather` sea una sola expresión generadora y no un `for` con `create_task` — o sea, un mini orquestador |

## Estructura del proyecto

```
04-parallel-fanout/
├── agent.py            # 4 prompts + branch() + ANALYSTS + timed + run_fanout + CLI (94 líneas, cero herramientas)
├── requirements.txt    # 3 líneas — las mismas de 01 y 03
├── .env.example        # 2 variables
├── README.md           # este archivo
└── .env                # tu clave; ignorado por git, no se commitea
```

## Limpieza

No hay nada que limpiar: el ejemplo no crea recursos, no lanza subprocesos y no escribe ningún
archivo. El bucle de eventos se abre y se cierra dentro de cada `asyncio.run`, y el historial de
los cuatro agentes se vacía al principio de cada corrida. Para borrar el entorno: `rm -rf .venv`.

## Recursos adicionales

- [Strands Agents — documentación](https://strandsagents.com/)
- [`asyncio.gather` — documentación de Python](https://docs.python.org/3/library/asyncio-task.html#asyncio.gather)
  — la única "primitiva de paralelismo" que usa este ejemplo, y no es de Strands
- [Multi-agent en Strands](https://strandsagents.com/latest/documentation/docs/user-guide/concepts/multi-agent/multi-agent-patterns/)
  — el catálogo de primitivas (grafos, swarms, agentes como herramientas) que este ejemplo
  **deliberadamente no usa**. `07-agent-graph` construirá este mismo abanico con `GraphBuilder`,
  y la comparación entre los dos es la mejor forma de ver qué aporta y qué cuesta un orquestador
- [Modelos de OpenAI en Strands](https://strandsagents.com/latest/documentation/docs/user-guide/concepts/model-providers/openai/)
- [Prompt engineering — Anthropic](https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/overview)
