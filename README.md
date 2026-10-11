# Arquitecturas de agentes

12 ejemplos mínimos y autocontenidos de **arquitecturas de agentes de IA**. Cada carpeta muestra *una* arquitectura en un solo archivo (`agent.py`, ~70 líneas) y cada ejemplo cambia exactamente una cosa respecto al anterior, para que la diferencia sea la lección.

No resuelven problemas reales: están pensados para leerse de arriba abajo y entender cómo se arma cada patrón.

## Los 12 ejemplos

| # | Ejemplo | Arquitectura |
|---|---------|--------------|
| 01 | [`basic-tool-agent`](strands-agents/01-basic-tool-agent) | Agente con herramientas propias (`@tool`) |
| 02 | [`mcp-agent`](strands-agents/02-mcp-agent) | Herramientas obtenidas de un servidor MCP |
| 03 | [`sequential-pipeline`](strands-agents/03-sequential-pipeline) | Agentes encadenados en fila |
| 04 | [`parallel-fanout`](strands-agents/04-parallel-fanout) | Agentes en paralelo (fan-out / fan-in) |
| 05 | [`router-agent`](strands-agents/05-router-agent) | Clasificar y despachar a un especialista |
| 06 | [`agents-as-tools`](strands-agents/06-agents-as-tools) | Agentes usados como herramientas de otro agente |
| 07 | [`agent-graph`](strands-agents/07-agent-graph) | Grafo de agentes con ramas condicionales |
| 08 | [`agent-swarm`](strands-agents/08-agent-swarm) | Enjambre autónomo sin orquestador |
| 09 | [`persistent-session-agent`](strands-agents/09-persistent-session-agent) | Conversación que sobrevive al reinicio |
| 10 | [`observable-agent`](strands-agents/10-observable-agent) | Trazas de herramientas, tiempos y tokens |
| 11 | [`human-in-the-loop`](strands-agents/11-human-in-the-loop) | Aprobación humana antes de actuar |
| 12 | [`structured-output`](strands-agents/12-structured-output) | Salida tipada y validada con Pydantic |

## Cómo probarlo

Necesitas **Python 3.10+** y una [API key de OpenAI](https://platform.openai.com/api-keys). No hace falta AWS. El ejemplo `02` además requiere **Node.js ≥ 18**.

```bash
git clone <url-del-repo>
cd <repo>/strands-agents/01-basic-tool-agent

python -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env              # pon tu OPENAI_API_KEY dentro
.venv/bin/python agent.py         # escribe 'exit' para salir
```

Para probar otro ejemplo, cambia de carpeta y repite los mismos pasos: cada uno tiene su propio `requirements.txt`, `.env.example` y `README.md` con el diagrama, una conversación de ejemplo y qué probar. Para usar otro modelo en una ejecución:

```bash
MODEL_ID=gpt-5.4 .venv/bin/python agent.py
```

## Estructura

```
strands-agents/
└── NN-nombre/
    ├── agent.py            # todo el ejemplo
    ├── requirements.txt    # dependencias directas
    ├── .env.example        # variables necesarias (sin valores reales)
    └── README.md           # arquitectura, ejecución y transcripción
```

No hay build, tests ni dependencias compartidas a nivel de repo: cada carpeta se instala y se ejecuta por separado.

## Por dónde empezar

Lee los ejemplos en orden. El `01` es la base; del `03` al `08` se compone cada vez más de un agente (fila, abanico, router, jerarquía, grafo, enjambre); del `09` al `12` se añaden persistencia, observabilidad, control humano y salida estructurada.
