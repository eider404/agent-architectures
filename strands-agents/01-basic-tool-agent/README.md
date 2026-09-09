# Agente básico con herramientas (`01-basic-tool-agent`)

Este es el ejemplo más simple de la colección: un único agente de Strands con dos
herramientas propias definidas con el decorador `@tool`, expuesto como un script de línea de
comandos. El dominio es un conversor de unidades porque su salida es **verificable a simple
vista**: si pides convertir 100 km a millas y recibes 62.1371, es evidente que la herramienta
se ejecutó y que el número no lo improvisó el modelo.

## Detalles del ejemplo

| Información | Detalles |
|---|---|
| **Características de Strands** | `Agent`, decorador `@tool`, `OpenAIResponsesModel` |
| **Patrón de agente** | Agente único |
| **Herramientas** | `convert_units`, `list_units` (herramienta sin argumentos) |
| **Modelo** | `gpt-5.4-mini` a través de la API directa de OpenAI (configurable con `MODEL_ID`) |

## Conceptos clave

- **Agent**: el componente central que gestiona la conversación y orquesta las herramientas.
- **Model**: el LLM que impulsa al agente; se instancia por separado y se pasa a `Agent`.
- **Tools**: funciones que el agente puede llamar. Los tipos de los argumentos y el docstring
  **son** el esquema de entrada que lee el modelo para decidir cuándo y cómo llamarlas. Tú no
  escribes el `if` que decide llamar a la herramienta: eso lo aporta el SDK.

## Prerrequisitos

- Python 3.10 o superior
- Una clave de API de OpenAI en un archivo `.env` (ver más abajo). El script la carga con
  `load_dotenv()` y el cliente de `openai` la toma del entorno, por eso el código no menciona
  la clave en ninguna parte
- No hace falta cuenta ni credenciales de AWS
- Conocimientos básicos de Python

> **Nota sobre Bedrock:** `gpt-5.4-mini` **no está disponible en Amazon Bedrock**. El catálogo
> OpenAI en Bedrock no incluye variantes `-mini`; el equivalente más cercano allí sería
> `openai.gpt-5.4` (modelo completo).

## Estructura del ejemplo

| Archivo | Descripción |
|---|---|
| [`agent.py`](./agent.py) | Todo el ejemplo: las dos herramientas, el agente y el bucle CLI |
| [`requirements.txt`](./requirements.txt) | Las tres dependencias directas |
| [`.env.example`](./.env.example) | Plantilla de configuración; cópiala a `.env` (ignorado por git) |
| [`README.md`](./README.md) | Este documento |

## Cómo ejecutarlo

```bash
cd strands-agents/01-basic-tool-agent
pip install -r requirements.txt
cp .env.example .env      # y pon tu clave real dentro
python agent.py
```

Escribe `exit` para terminar la sesión.

El `.env` admite dos variables:

| Variable | Obligatoria | Descripción |
|---|---|---|
| `OPENAI_API_KEY` | Sí | Tu clave de la API de OpenAI |
| `MODEL_ID` | No | Modelo a usar; si no la defines, `agent.py` cae en `gpt-5.4-mini` |

El `.env` está en el `.gitignore` de la raíz del repositorio, así que **nunca se commitea**.
Lo que sí viaja con git es `.env.example`, la plantilla sin secretos. Si prefieres no usar
archivo, `export OPENAI_API_KEY="..."` en la terminal funciona igual: `load_dotenv()` no
pisa una variable que ya exista en el entorno. Eso también permite probar otro modelo en una
sola ejecución: `MODEL_ID=gpt-5.4 python agent.py`.

## Transcripción de ejemplo

> ⚠️ **Transcripción ilustrativa.** La verificación de punta a punta contra el modelo real
> quedó **pendiente**: no había una `OPENAI_API_KEY` disponible al escribir el ejemplo. Sin
> ella no se comprobaron los siete requisitos funcionales del PRD (que el agente llame
> exactamente una vez a `convert_units`, que se recupere con `list_units` ante una unidad
> desconocida, ni que responda sin herramientas a una pregunta general). El comportamiento de
> las herramientas sí está verificado: se ejecutan y devuelven los valores de abajo.

```
UnitBot: Ask me to convert units! Type 'exit' to quit.

You > ¿cuántas millas son 100 km?
Tool #1: convert_units

UnitBot > 100 km son 62.1371 millas.

You > ¿qué unidades manejas?
Tool #2: list_units

UnitBot > Puedo convertir longitud (m, km, cm, mm, mi, ft, in, yd),
masa (kg, g, mg, lb, oz) y temperatura (c, f, k).

You > convierte 5 galones a litros
Tool #3: convert_units
Tool #4: list_units

UnitBot > No manejo galones ni litros. Puedo convertir longitud, masa y temperatura.

You > exit
```

Las líneas `Tool #N: <nombre>` las imprime el `callback_handler` por defecto de Strands: son
la prueba directa de que la herramienta se ejecutó de verdad.

## Estructura del proyecto

```
01-basic-tool-agent/
├── agent.py
├── requirements.txt
├── .env.example
├── .env               # tu clave; ignorado por git, no se commitea
└── README.md
```

## Limpieza

El ejemplo no crea recursos persistentes ni escribe ningún archivo. Solo llama a la API de
OpenAI para la inferencia, así que no hay nada que limpiar.

## Recursos adicionales

- [Strands Agents — documentación](https://strandsagents.com/)
- [Strands Agents — proveedor OpenAI](https://strandsagents.com/docs/user-guide/concepts/model-providers/openai/)
- [Strands Agents — API Responses de OpenAI](https://strandsagents.com/docs/user-guide/concepts/model-providers/openai-responses/)
- [Strands Agents — herramientas personalizadas](https://strandsagents.com/docs/user-guide/concepts/tools/custom-tools/)
