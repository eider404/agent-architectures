# 03 · Pipeline secuencial de agentes

Tres agentes encadenados en secuencia: uno investiga, otro estructura y otro redacta. La salida
de cada uno es la entrada del siguiente, y el encadenado entero son **tres asignaciones de
Python** — no hay orquestador, ni `GraphBuilder`, ni `Swarm`, ni un bucle de etapas.

`03` no es `02` más algo: es `02` **menos** las herramientas, y por tres. Aquí no se define
ninguna herramienta ni se conecta ningún servidor MCP. La única API que hace falta conocer es la
que ya usaba `01`: un `Agent` se llama con un `str` y devuelve un `AgentResult` del que se saca
texto con `str()`. Con eso, componer agentes deja de ser un tema y pasa a ser una consecuencia.

```
Usuario (stdin) ──► run_pipeline("el impacto de los LLM en la educación")
    │
    ├──► las tres etapas se resetean: cada corrida empieza en blanco
    │
    ├──[1/3]──► research_agent(topic)    ──► str() ──► notes     (5-7 viñetas)
    ├──[2/3]──► outline_agent(notes)     ──► str() ──► outline   (3 secciones con título)
    └──[3/3]──► draft_agent(outline)     ──► str() ──► draft     (3 párrafos con encabezado)
                tres agentes · cero herramientas · ningún orquestador
```

## Detalles del ejemplo

| Información | Detalles |
|---|---|
| Características de Strands | `Agent`, `OpenAIResponsesModel`, `callback_handler=None`, `agent.messages` |
| Patrón de agente | Tres agentes en secuencia, encadenados a mano, sin orquestador |
| Herramientas | **Ninguna** — el ejemplo no define ni consume ninguna |
| Modelo | `gpt-5.4-nano` (configurable con `MODEL_ID`) |
| Complejidad | Principiante |

## Conceptos clave

- **Un `Agent` es un invocable de texto a texto.** Recibe un `str` y devuelve un `AgentResult`.
  Eso es todo lo que hace falta para encadenarlos: `notes = str(research_agent(topic))`.
- **`str(AgentResult)` es el único punto donde hay que saber algo del tipo de retorno.**
  `Agent.__call__` no acepta un `AgentResult`, así que el `str()` del relevo es necesario, no
  decorativo. Se escribe explícito para dejar visible que entre etapas viaja texto plano.
- **El contrato entre etapas vive en el `system_prompt`.** En `01` lo escribía el decorador
  `@tool` a partir de los tipos y el docstring; en `02` lo declaraba el servidor MCP en el
  handshake; aquí el prompt es el único sitio donde el contrato existe. Es texto sin estructura:
  la forma **más frágil** de las tres del repositorio. `12-structured-output` existe para eso.
- **Por qué no hay orquestador.** Strands trae primitivas multi-agente (`GraphBuilder`, `Swarm`,
  agentes como herramientas), y ninguna hace falta para ejecutar tres pasos en orden fijo. Ese es
  el punto: si el grafo es una línea recta, la línea recta ya la escribe Python.
- **Por qué no hay un bucle sobre las etapas.** Un bucle de encadenado sería un mini orquestador
  y escondería lo único que se quiere enseñar. El único bucle del archivo es el del reseteo, que
  sí es una tarea homogénea y aburrida.
- **Un agente es conversacional por defecto; un pipeline no.** Por eso cada corrida empieza
  vaciando `agent.messages` de las tres etapas.

## Prerrequisitos

- Python 3.10 o superior
- Una `OPENAI_API_KEY` en un `.env` local
- **Sin AWS** y **sin Node.js**: el prerrequisito que `02` introdujo (`npx` para lanzar el
  servidor MCP) desaparece aquí. Las dependencias vuelven a ser las tres de `01`.

## Estructura del ejemplo

| Archivo | Descripción |
|---|---|
| `agent.py` | Los tres prompts, la fábrica `stage()`, los tres agentes, `run_pipeline()` y el CLI |
| `requirements.txt` | Las 3 dependencias, idénticas a las de `01` |
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

> **La consola se queda en silencio unos segundos por etapa.** El streaming está desactivado
> (`callback_handler=None`), así que entre el banner de una etapa y su salida no se imprime nada.
> El banner `[N/3]` sale **antes** de invocar la etapa, precisamente para que siempre se vea en
> qué punto está el pipeline. No está colgado: está pensando.

## Transcripción de ejemplo

Corrida real contra `gpt-5.4-nano`, recortada a las primeras viñetas de la etapa 1 por espacio;
las etapas 2 y 3 van completas.

```
WritingPipeline: Give me a topic. Type 'exit' to quit.

Using LLM model: gpt-5.4-nano

Topic > el impacto de los LLM en la educación

[1/3] research ──►
- Los LLM pueden actuar como “tutor inmediato” que explica conceptos, propone ejercicios y da
  retroalimentación rápida, pero su calidad suele variar y puede introducir errores plausibles.
- La principal tensión pedagógica es entre personalización y veracidad: respuestas adaptadas al
  alumno aumentan utilidad, pero si no hay verificación, se consolida el aprendizaje incorrecto.
- Se están reconfigurando las prácticas de evaluación: pruebas de memoria y redacción tradicional
  pierden fuerza, mientras ganan tareas con proceso (borradores, bitácoras), defensas orales y
  rúbricas centradas en razonamiento.
- Cambia el trabajo docente: menos tiempo en explicaciones repetitivas y más en diseño de
  actividades, verificación de fuentes, alfabetización en IA y políticas claras de uso.
- Surgen desigualdades: estudiantes con mejor acceso (dispositivos, conectividad, habilidades
  digitales) pueden beneficiarse más.
- Riesgos y mitigaciones: alucinaciones, sesgos y problemas de privacidad impulsan prácticas como
  exigir citación, usar herramientas para chequear y limitar datos sensibles.

[2/3] outline ──►
1. Tutor inmediato y limitaciones
- Los LLM pueden actuar como “tutor inmediato” que explica conceptos, propone ejercicios y da
  retroalimentación rápida, pero su calidad suele variar y puede introducir errores plausibles.

2. Personalización, verificación y evaluación
- La principal tensión pedagógica es entre personalización y veracidad...
- Se están reconfigurando las prácticas de evaluación...
- El “uso como atajo” (copiar/pegar) choca con objetivos de aprendizaje profundo...

3. Docencia, equidad y mitigaciones
- Cambia el trabajo docente...
- Surgen desigualdades: estudiantes con mejor acceso pueden beneficiarse más...
- Riesgos y mitigaciones: alucinaciones, sesgos y problemas de privacidad...

[3/3] draft ──►
Tutor inmediato y limitaciones
Los LLM funcionan a menudo como un “tutor inmediato” que aclara conceptos, sugiere ejercicios y
devuelve retroalimentación con rapidez. Sin embargo, su desempeño es inconsistente: puede sonar
convincente aunque falle, y generar errores plausibles que el estudiante incorpore si no se
contrastan con materiales fiables.

Personalización, verificación y evaluación
La tensión central es personalizar sin sacrificar veracidad: adaptar la respuesta al alumno
mejora la utilidad, pero sin verificación favorece el aprendizaje de errores. Por eso ganan
fuerza evaluaciones basadas en proceso—borradores, bitácoras, defensas orales y rúbricas—que
premian razonamiento, no solo resultados finales.

Docencia, equidad y mitigaciones
La docencia se desplaza: menos tiempo en explicaciones repetitivas y más en diseñar actividades,
exigir verificación de fuentes, enseñar alfabetización en IA y fijar políticas claras sobre su
uso. A la vez, aparecen desigualdades por acceso y apoyo familiar. Para mitigarlas, se aborda la
alucinación y el sesgo con citación, verificación y límites a datos sensibles.

Topic > exit
```

**Dónde está la prueba de que el relevo ocurrió.** Los tres encabezados del borrador —*Tutor
inmediato y limitaciones*, *Personalización, verificación y evaluación*, *Docencia, equidad y
mitigaciones*— son, palabra por palabra, los tres títulos del esquema. Y ninguno de los tres
aparecía en las viñetas de la etapa 1: los inventó la etapa 2. La etapa 3 solo pudo conocerlos
porque los recibió por el encadenado.

Eso es lo que aquí sustituye al `62.1371 mi` de `01` y al `8642` de `02`: sin herramientas no hay
un dato inadivinable que exhibir, así que la prueba tiene que venir de la **trazabilidad** de la
forma de los datos, no de su contenido.

En la misma sesión se escribió un segundo tema (`el precio del cacao`) y el borrador resultante
no menciona ni la educación ni los LLM. Eso lo garantiza el `messages.clear()`, no la buena
voluntad del modelo.

**Este ejemplo no está fundamentado.** La etapa 1 trabaja de memoria: no tiene herramientas ni
acceso a la web, y su prompt se lo dice explícitamente, además de pedirle que describa las cifras
de forma cualitativa en vez de inventar números precisos. `01` y `02` enseñaban a fundamentar una
respuesta en algo externo; `03` enseña a **componer** agentes. No trates sus salidas como hechos
verificados.

### Las tres diferencias con `01` y `02`, y por qué

| Diferencia | Por qué |
|---|---|
| `callback_handler=None` en las tres etapas | Con el handler por defecto cada etapa imprime su respuesta en streaming **y** `run_pipeline` la vuelve a imprimir: seis bloques de texto para tres salidas. Además aquí no hay líneas `Tool #N:` que mostrar, porque no hay herramientas. El coste es el silencio de la consola durante cada etapa |
| `Topic >` en vez de `You >` | Lo que se escribe no es un turno de conversación, sino la entrada de un proceso que se ejecuta entero y termina. La estructura del bucle (`while True` / `input()` / `exit`) es idéntica a la de `01` y `02` |
| Los agentes se resetean en cada corrida | Son constantes de módulo (importables, como en `01`), así que acumulan historial entre corridas. Sin el `clear()`, el segundo tema arrastraría el primero. `OpenAIResponsesModel` tiene `stateful = False`, así que vaciar la lista local basta de verdad |

## Estructura del proyecto

```
03-sequential-pipeline/
├── agent.py            # tres agentes + run_pipeline + CLI (79 líneas, cero herramientas)
├── requirements.txt    # 3 líneas — las mismas de 01
├── .env.example        # 2 variables
├── README.md           # este archivo
└── .env                # tu clave; ignorado por git, no se commitea
```

## Limpieza

No hay nada que limpiar: el ejemplo no crea recursos, no lanza subprocesos y no escribe ningún
archivo. El historial de las tres etapas se vacía al principio de cada corrida, y el proceso no
deja estado al salir. Para borrar el entorno: `rm -rf .venv`.

## Recursos adicionales

- [Strands Agents — documentación](https://strandsagents.com/)
- [Multi-agent en Strands](https://strandsagents.com/latest/documentation/docs/user-guide/concepts/multi-agent/multi-agent-patterns/)
  — el catálogo de primitivas (grafos, swarms, agentes como herramientas) que este ejemplo
  **deliberadamente no usa**: conviene leerlo después, para saber a partir de qué punto sí compensan
- [Modelos de OpenAI en Strands](https://strandsagents.com/latest/documentation/docs/user-guide/concepts/model-providers/openai/)
- [Prompt engineering — Anthropic](https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/overview)
