# 04 · Abanico paralelo de agentes (fan-out / fan-in)

Tres agentes analizan **la misma** propuesta a la vez (pros, contras y riesgos). Un cuarto espera
a los tres y da un veredicto. Sirve para ver cómo ejecutar agentes en paralelo cuando no dependen
entre sí: el tiempo total se acerca al de la rama más lenta en vez de a la suma.

> **Diferencia con `03`:** la topología. Donde había una fila, ahora hay un abanico con
> `asyncio.gather`.

## Cómo funciona

```mermaid
flowchart LR
    P(["Propuesta"]) --> PR["pros"]
    P --> CO["cons"]
    P --> RI["risks"]
    PR --> S["synthesis"]
    CO --> S
    RI --> S
    S --> V(["VERDICT"])
```

| | |
|---|---|
| Patrón | Fan-out / fan-in: 3 ramas en paralelo y 1 agregador |
| Piezas de Strands | `Agent`, `Agent.invoke_async`, `OpenAIResponsesModel`, `callback_handler=None` |
| Herramientas | Ninguna |
| Modelo | `gpt-5.4-nano` (cambiable con `MODEL_ID`) |

**Ideas clave**

- **El paralelismo lo pone `asyncio`, no Strands.** Todo el abanico es un `asyncio.gather` sobre
  `invoke_async`, en un solo hilo.
- **Se paraleliza lo que no se necesita entre sí.** En `03` cada etapa esperaba a la anterior. Aquí
  ninguna rama necesita a otra.
- **Un agente por rama.** Reusar la misma instancia de `Agent` en dos ramas a la vez lanza un
  error. Por eso `branch()` crea una instancia por rama.
- **Sin streaming por obligación.** Con tres respuestas a la vez, la consola quedaría mezclada.

## Configuración y ejecución

Requisitos: Python 3.10+ y una `OPENAI_API_KEY`. No añade dependencias: `asyncio` es de la
biblioteca estándar.

```bash
cd strands-agents/04-parallel-fanout
python -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env          # pon tu OPENAI_API_KEY
.venv/bin/python agent.py     # 'exit' para salir
```

| Variable | Obligatoria | Uso |
|---|---|---|
| `OPENAI_API_KEY` | Sí | Tu clave de OpenAI |
| `MODEL_ID` | No | Modelo a usar; por defecto `gpt-5.4-nano` |

> **Las líneas de tiempo salen en el orden en que termina cada rama**, no en el orden en que están
> declaradas. Ese desorden muestra que corrieron a la vez.

## Ejemplos

Escribe una propuesta (`Proposal >`). Fragmento real:

```text
Proposal > adoptar la semana laboral de 4 dias

[fan-out] lanzando 3 analistas en paralelo...
  risks  ──►   1.4s
  cons   ──►   1.7s
  pros   ──►   1.7s
  total:   1.7s  (en secuencia habrian sido 4.9s)

[fan-in] synthesis ──►
VERDICT: conditional
- Beneficios potenciales: mayor productividad/concentración y posible reducción de ausentismo... (P1, P2)
- La viabilidad operativa depende del contexto... (C1, R2)
```

**La prueba:** el reloj. En otra propuesta de la misma sesión, el total fue **4.4 s** cuando las
ramas sumaban **9.9 s**. Además, el veredicto cita etiquetas (`P1`, `C1`, `R2`) que solo existen
en las salidas de las ramas.

## Referencias

- [`asyncio.gather` en la documentación de Python](https://docs.python.org/3/library/asyncio-task.html#asyncio.gather)
- [Patrones multi-agente en Strands](https://strandsagents.com/latest/documentation/docs/user-guide/concepts/multi-agent/multi-agent-patterns/) (`07-agent-graph` repite este abanico con `GraphBuilder`)
- [Proveedor OpenAI en Strands](https://strandsagents.com/latest/documentation/docs/user-guide/concepts/model-providers/openai/)
- Archivos: [`agent.py`](./agent.py) · [`requirements.txt`](./requirements.txt) · [`.env.example`](./.env.example)
