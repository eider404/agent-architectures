# Agente con herramientas MCP (`02-mcp-agent`)

Este ejemplo no define **ninguna** herramienta propia: no hay un solo `@tool` en el archivo.
Las cinco que usa el agente se las presta un servidor externo —el servidor oficial de
filesystem del Model Context Protocol— que el script lanza como subproceso y al que le
pregunta, en tiempo de ejecución, qué sabe hacer. El dominio es explorar un directorio local
porque así ninguna credencial de nube ni infraestructura se interpone en el mecanismo, y
porque los datos del `sandbox/` (`8642`, `KRAKEN-7743`) son arbitrarios a propósito: si
aparecen en una respuesta, la herramienta se ejecutó de verdad.

Frente a [`01-basic-tool-agent`](../01-basic-tool-agent/), la única diferencia arquitectónica
es **de dónde salen las tools**: allí eran dos funciones decoradas en el propio archivo, aquí
son una lista que devuelve un servidor. Todo lo demás —proveedor de modelo, `.env`, bucle
CLI— es idéntico, para que ese contraste sea la única señal.

## Detalles del ejemplo

| Información | Detalles |
|---|---|
| **Características de Strands** | `Agent`, `MCPClient`, `list_tools_sync`, `tool_filters`, `OpenAIResponsesModel` |
| **Patrón de agente** | Agente único, con herramientas externas por MCP sobre stdio |
| **Herramientas** | `read_text_file`, `list_directory`, `directory_tree`, `search_files`, `get_file_info` — **ninguna propia** |
| **Modelo** | `gpt-5.4-nano` a través de la API directa de OpenAI (configurable con `MODEL_ID`) |
| **Servidor MCP** | `@modelcontextprotocol/server-filesystem@2026.8.31`, lanzado con `npx` |

La versión del servidor está **fijada** a propósito, para que la transcripción de más abajo
siga siendo cierta dentro de seis meses. Para actualizarla, cambia `FS_SERVER` en `agent.py`
y vuelve a ejecutar: el arranque imprime el catálogo de tools admitidas. Si alguna de las
cinco de `READ_ONLY` desapareciera del servidor, saldría una lista más corta y ahí se ve.

## Conceptos clave

- **MCPClient**: recibe una *factoría* de transporte (`lambda: stdio_client(...)`), no un
  transporte ya construido. Es él quien decide cuándo abrirlo.
- **Descubrimiento en tiempo de ejecución**: `list_tools_sync()` pregunta al servidor qué
  herramientas expone. El catálogo no está escrito en el código; llega por el canal.
- **`tool_filters` como lista blanca**: el servidor ofrece 14 tools y solo dejamos pasar 5.
  Se usa `allowed` y no `rejected` deliberadamente: con una lista negra habría que enumerar
  las nueve descartadas, y cualquier herramienta nueva de una versión futura del servidor
  entraría sola. Las de escritura (`write_file`, `edit_file`, `move_file`, `create_directory`)
  nunca llegan al modelo — no puede negarse a usarlas porque ni siquiera las conoce.
- **El ciclo de vida**: las tools MCP solo funcionan mientras la sesión está abierta. Por eso
  el descubrimiento, el `Agent` y el bucle viven **dentro del `with fs_client:`**, y —a
  diferencia de `01`— el agente no es una constante de módulo importable. Construirlo fuera
  del `with` compila sin quejas y falla con `MCPClientInitializationError` en la primera
  llamada.

## Prerrequisitos

- Python 3.10 o superior
- **Node.js 18 o superior**, porque el servidor MCP se lanza con `npx`. Compruébalo con
  `node --version`; si no lo tienes, instálalo desde [nodejs.org](https://nodejs.org/)
- Una clave de API de OpenAI en un archivo `.env` (ver más abajo). El script la carga con
  `load_dotenv()` y el cliente de `openai` la toma del entorno, por eso el código no menciona
  la clave en ninguna parte
- No hace falta cuenta ni credenciales de AWS
- Conocimientos básicos de Python

## Estructura del ejemplo

| Archivo | Descripción |
|---|---|
| [`agent.py`](./agent.py) | Todo el ejemplo: cliente MCP, filtro de herramientas, agente y bucle CLI |
| [`requirements.txt`](./requirements.txt) | Las cuatro dependencias directas |
| [`.env.example`](./.env.example) | Plantilla de configuración; cópiala a `.env` (ignorado por git) |
| [`README.md`](./README.md) | Este documento |
| [`sandbox/`](./sandbox/) | Cuatro archivos de juguete del proyecto ficticio "Kraken": lo único que el agente puede ver |

## Cómo ejecutarlo

```bash
cd strands-agents/02-mcp-agent
pip install -r requirements.txt
cp .env.example .env      # y pon tu clave real dentro
python agent.py
```

Escribe `exit` para terminar la sesión.

> **El primer arranque tarda unos segundos** mientras `npx` descarga el servidor MCP. No es
> un cuelgue; las siguientes ejecuciones son inmediatas gracias a la caché de npm.

El `.env` admite dos variables:

| Variable | Obligatoria | Descripción |
|---|---|---|
| `OPENAI_API_KEY` | Sí | Tu clave de la API de OpenAI |
| `MODEL_ID` | No | Modelo a usar; si no la defines, `agent.py` cae en `gpt-5.4-nano` |

El `.env` está en el `.gitignore` de la raíz del repositorio, así que **nunca se commitea**.
Lo que sí viaja con git es `.env.example`, la plantilla sin secretos.

## Transcripción de ejemplo

Sesión real contra `gpt-5.4-nano`, recortada solo en las líneas en blanco:

```
FileBot: Ask me about the files in the sandbox! Type 'exit' to quit.

Using LLM model: gpt-5.4-nano
MCP tools: ['read_text_file', 'list_directory', 'directory_tree', 'search_files', 'get_file_info']

You > ¿qué archivos hay?
Tool #1: list_directory

FileBot > En el directorio .../02-mcp-agent/sandbox hay:
- README.md
- notas-reunion.md
- Carpeta config

You > enséñame el árbol completo
Tool #2: directory_tree

FileBot > sandbox
          ├── README.md
          ├── config
          │   ├── despliegue.md
          │   └── settings.json
          └── notas-reunion.md

You > ¿en qué puerto escucha el servicio?
Tool #3: read_text_file
Tool #4: read_text_file
Tool #5: read_text_file

FileBot > El servicio escucha en el puerto 8642.

You > ¿hay algún archivo .json?
Tool #6: search_files

FileBot > Sí: .../sandbox/config/settings.json

You > ¿cuánto pesa notas-reunion.md?
Tool #7: get_file_info

FileBot > notas-reunion.md pesa 554 bytes.

You > ¿cuál es el código de despliegue?
Tool #8: read_text_file

FileBot > El código de despliegue es KRAKEN-7743.

You > borra el archivo de notas

FileBot > No puedo borrarlo: solo tengo acceso de lectura a los archivos en este entorno.

You > exit
```

Las líneas `Tool #N: <nombre>` las imprime el `callback_handler` por defecto de Strands: son
la prueba directa de que la herramienta se ejecutó. Ese mismo handler escribe la respuesta en
streaming, así que cada respuesta aparece dos veces en la terminal —una en streaming y otra
en el `print` final del bucle—; arriba se muestra una sola vez por legibilidad. Es el mismo
comportamiento que en `01`.

Dos detalles que merecen la pena: el `8642` y el `KRAKEN-7743` no son inventables, así que su
presencia demuestra que el archivo se leyó de verdad. Y en el último turno **no hay ninguna
línea `Tool #N:`**: el agente no intentó borrar nada porque las herramientas de escritura
nunca entraron en su catálogo.

## Estructura del proyecto

```
02-mcp-agent/
├── agent.py
├── requirements.txt
├── .env.example
├── .env                    # tu clave; ignorado por git, no se commitea
├── README.md
└── sandbox/                # el único directorio que el agente puede leer
    ├── README.md
    ├── notas-reunion.md
    └── config/
        ├── settings.json
        └── despliegue.md
```

## Limpieza

El ejemplo no crea recursos persistentes. El subproceso `npx` del servidor MCP muere al salir
del `with`, es decir, al escribir `exit`. El `sandbox/` tampoco se modifica: el agente no
tiene con qué.

## Recursos adicionales

- [Strands Agents — documentación](https://strandsagents.com/)
- [Strands Agents — herramientas MCP](https://strandsagents.com/docs/user-guide/concepts/tools/mcp-tools/)
- [Strands Agents — proveedor OpenAI](https://strandsagents.com/docs/user-guide/concepts/model-providers/openai/)
- [Model Context Protocol — especificación](https://modelcontextprotocol.io/)
- [Servidor MCP de filesystem](https://github.com/modelcontextprotocol/servers/tree/main/src/filesystem)

Además de herramientas, un servidor MCP puede exponer
[`prompts` y `resources`](https://modelcontextprotocol.io/docs/concepts/architecture); este
ejemplo se queda solo en las herramientas.
