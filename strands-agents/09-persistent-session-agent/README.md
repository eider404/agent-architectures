# 09 · Agente con sesión persistente

`08` cerró el arco que abrió `03`: cadena, abanico, router, jerarquía, grafo y enjambre. Seis ejemplos
respondiendo siempre a la misma pregunta — **quién habla, y en qué orden**. `09` cambia el eje: vuelve
a **un solo agente, sin herramientas**, y pregunta otra cosa — **qué queda cuando el proceso muere**.

Por eso el ejemplo con el que hay que comparar `09` no es `08`, sino **`01`**. Son el mismo archivo
salvo un parámetro:

```python
# 01-08: al terminar el proceso, la conversacion se evapora
agent = Agent(model=..., system_prompt=..., tools=[...])

# 09: la misma llamada, mas una linea
agent = Agent(model=..., system_prompt=..., session_manager=FileSessionManager("ana", ...))
```

No hay `save()`, no hay `load()`, no hay `json.dump`, no hay `atexit`. `grep` sobre `agent.py`:

```
grep -cE '\bsave\(|\bload\('   agent.py   → 0
grep -cE 'json\.dump|json\.load' agent.py   → 0
```

Y porque *"guardar la sesión"* no es una propiedad del agente sino **un colaborador enchufable**, el
ejemplo trae además un **backend propio de SQLite** en `sqlite_session.py`, que implementa la misma
interfaz `SessionRepository` con la misma doble herencia que usa `FileSessionManager` dentro del SDK.
El agente de `agent.py` no sabe cuál de los dos le tocó.

```
   SIN memoria (--no-session)              CON memoria (por defecto)

   proceso 1   "soy KRAKEN-7743"           proceso 1   "soy KRAKEN-7743"
       │                                       │              │
       ▼                                       ▼              ▼ 2 mensajes al disco
     (fin)  ─────  nada                      (fin)      sessions/session_ana/…
       │                                       │              │
   proceso 2   "¿mi codigo?"                proceso 2   "¿mi codigo?"  ◄── 2 mensajes restaurados
       │                                       │
       ▼                                       ▼
   "No lo sé."                            "Tu código de socio es KRAKEN-7743."
```

## Descripción

Mnemo es un asistente personal de un solo agente, **sin ninguna `@tool`**, cuya conversación
sobrevive al reinicio del proceso. El dominio está elegido para que la prueba sea verificable a
simple vista: se le dice un dato **inadivinable** (`KRAKEN-7743`) en una corrida, se mata el proceso,
y en la siguiente se le pregunta por él. Si lo dice, la memoria funcionó; y como el `SYSTEM_PROMPT`
le ordena admitir lo que no sabe, la corrida con otro `session_id` (`bruno`) sirve de **control
negativo**: allí tiene que fallar.

La CLI arranca de tres maneras, con el **mismo `agent.py`**, y eso es lo que convierte la lección en
algo que se *ejecuta* en vez de leerse:

| Arranque | Almacén | Para qué está |
|---|---|---|
| `python agent.py ana` | `FileSessionManager` → árbol de JSON | El primitivo del SDK |
| `python agent.py ana --sqlite` | `SqliteSessionManager` → una base SQLite | El backend propio: la interfaz cumplida por otro |
| `python agent.py ana --no-session` | ninguno | La línea base: el comportamiento de `01`–`08` |

## Cómo Funciona

### Detalles del ejemplo

| Información | Detalles |
|---|---|
| **Características de Strands** | `session_manager=`, `FileSessionManager`, `RepositorySessionManager`, la interfaz `SessionRepository` |
| **Patrón de agente** | Agente único con estado persistente entre procesos |
| **Herramientas** | **Ninguna**. `grep -c '@tool' agent.py` → `0` |
| **Modelo** | `gpt-5.4-mini` por la API directa de OpenAI (configurable con `MODEL_ID`) |
| **Almacenes** | Dos: el del SDK (JSON en disco) y uno propio (SQLite, 79 líneas, 0 dependencias nuevas) |
| **Dependencias nuevas** | **Cero**: `sqlite3` y `json` son de la biblioteca estándar |

### Conceptos clave

- **No existe `save()` ni `load()`.** El `SessionManager` es un `HookProvider`: al pasarlo a `Agent`,
  el SDK lo engancha a cuatro puntos del ciclo de vida (`AgentInitializedEvent`,
  `MessageAddedEvent`, `AfterInvocationEvent` y la redacción por guardarraíles). Restaurar y guardar
  ocurren **dentro** de esos hooks; tu código no los llama nunca.
- **El reparto de responsabilidades son tres piezas, no una**:
  - `SessionManager` — la interfaz que `Agent` conoce (los hooks).
  - `RepositorySessionManager` — la implementación de esos hooks en términos de *"leer y escribir
    entidades"*. Es quien decide **cuándo**.
  - `SessionRepository` — la interfaz de **dónde** se guardan: nueve métodos, ningún hook.
- **`FileSessionManager` es *una* implementación, no *el* mecanismo.** En el SDK se declara así:

  ```python
  class FileSessionManager(RepositorySessionManager, SessionRepository):
  ```

  Esa doble herencia —ser a la vez el gestor y el repositorio— es exactamente la que copia
  `sqlite_session.py`. Cambiar de almacén no toca ni una línea de `agent.py`.
- **El `session_id` es la clave de la memoria.** Es el primer argumento que no sea un flag. Dos ids
  distintos son dos memorias distintas, aunque compartan archivo o base de datos.
- **`restored messages` no lo dice el modelo.** Sale de `len(agent.messages)` **antes** del primer
  turno: es un dato del proceso, no una respuesta que el LLM pueda inventar.

### El orden real de llamadas

Instrumentando los nueve métodos del repositorio (proveedor de modelo falso, sin red). Esta traza es
literal:

```
== proceso 1 ==
 construir manager: ['read_session', 'create_session']
 construir Agent:   ['create_agent']   <- SIN read_agent: la sesion es nueva
 turno 1:           ['create_message(msg_id=0)', 'update_agent', 'create_message(msg_id=1)']
 turno 2:           ['create_message(msg_id=2)', 'create_message(msg_id=3)']   <- CERO update_agent

== proceso 2 ==
 construir manager: ['read_session']
 construir Agent:   ['read_agent', 'list_messages(offset=0)'] -> mensajes: 4
 window_size: 40 | model.stateful: False
```

Dos cosas sorprenden, y las dos están medidas:

1. **`read_agent` no se llama en una sesión nueva.** `RepositorySessionManager.initialize` se lo
   salta cuando acaba de crear la sesión (`if self._is_new_session: session_agent = None`).
2. **`update_agent` se llama una sola vez en todo el proceso**, no una por mensaje: en el primer
   sincronizado y nunca más, porque después nada del agente cambia. Las escrituras en la tabla de
   mensajes son una por mensaje; las de la tabla de agentes, casi ninguna.

Y una tercera, la que sostiene el ejemplo: **restaurar no llama al LLM**. Contando las invocaciones
del modelo falso durante toda la prueba —dos escrituras y cuatro restauraciones— salen `[1, 0, 0, 1,
0, 0]`: una por cada turno que de verdad habló, cero en cada arranque.

### Los dos almacenes, por dentro

| | `FileSessionManager` | `SqliteSessionManager` (este ejemplo) |
|---|---|---|
| Soporte | Un árbol de directorios con un JSON por entidad | Un archivo `.db`, tres tablas |
| Dónde | `sessions/` junto a `agent.py` | `sessions.db` junto a `agent.py` |
| Aislamiento entre sesiones | Un directorio por `session_id` | La columna `session_id` de cada tabla |
| Valida el `session_id` | **Sí** (es parte de una ruta) | **No** (ver trampa 5) |
| Multi-agente (`Swarm`/`Graph`) | Sí, `multi_agents/` | **No**: los tres `*_multi_agent` no se implementan |
| Concurrencia | Un proceso | Un proceso (`check_same_thread=False` para los hilos del agente) |

El árbol que deja `FileSessionManager` tras las corridas reales, literal:

```
sessions/session_ana/session.json
sessions/session_ana/multi_agents/           (vacio)
sessions/session_ana/agents/agent_default/agent.json
sessions/session_ana/agents/agent_default/messages/message_0.json
sessions/session_ana/agents/agent_default/messages/message_1.json
sessions/session_ana/agents/agent_default/messages/message_2.json
sessions/session_ana/agents/agent_default/messages/message_3.json
sessions/session_bruno/session.json
sessions/session_bruno/multi_agents/         (vacio)
sessions/session_bruno/agents/agent_default/agent.json
sessions/session_bruno/agents/agent_default/messages/message_0.json
sessions/session_bruno/agents/agent_default/messages/message_1.json
```

El `multi_agents/` vacío lo crea el SDK aunque nunca haya un `Swarm`. Y la base SQLite tras la
corrida `--sqlite`:

```
sqlite> SELECT session_id, agent_id, message_id, substr(data,1,60) FROM messages;
('ana', 'default', 0, '{"message": {"role": "user", "content": [{"text": "cual es m')
('ana', 'default', 1, '{"message": {"role": "assistant", "content": [{"text": "No l')

sqlite> SELECT DISTINCT session_id FROM messages;
['ana']
```

### El contrato, método a método

`SessionRepository` tiene **nueve** métodos abstractos. `sqlite_session.py` los implementa todos
(`len(SqliteSessionManager.__abstractmethods__)` → `0`) en dos o tres líneas cada uno, apoyados en dos
ayudantes (`_write` / `_read`):

| Método | Cuándo lo llama el SDK |
|---|---|
| `read_session` | Al construir el manager, antes que nada |
| `create_session` | Al construir el manager, si `read_session` devolvió `None` |
| `create_agent` | Al construir el `Agent`, si la sesión es nueva |
| `read_agent` | Al construir el `Agent`, **sólo** si la sesión ya existía |
| `update_agent` | En el primer sincronizado, y después sólo si algo cambió (en la práctica: una vez) |
| `create_message` | Una vez por mensaje añadido, en `MessageAddedEvent` |
| `list_messages` | Al restaurar, con el `offset` de lo que el gestor de ventana ya descartó |
| `read_message` | Al leer un mensaje suelto por su `message_id` |
| `update_message` | Sólo cuando un guardarraíl redacta un mensaje ya escrito |

Los tres opcionales —`create_multi_agent`, `read_multi_agent`, `update_multi_agent`— **no están**
(`grep -c multi_agent sqlite_session.py` → `0`): heredan el `NotImplementedError` de la interfaz. Es
lo correcto para un backend de agente único, y es también su límite: **este backend no sirve para
persistir un `Swarm` o un `Graph`**.

Las nueve consultas van parametrizadas con `?`, sin excepción
(`grep -cE '%s|f"SELECT|\+ session_id'` → `0`), porque el `session_id` entra por `sys.argv`.

### Qué se persiste y qué no

| Sí sobrevive al reinicio | No sobrevive |
|---|---|
| Los mensajes de la conversación | El `system_prompt` |
| `agent.state` | Las herramientas registradas |
| El estado del gestor de conversación (qué recortó la ventana) | El modelo y su configuración |
| `_model_state` | Cualquier variable del proceso |

La columna derecha no es un olvido: esas tres cosas **vienen del código**, y el código manda sobre el
disco en cada arranque. Es justo lo que dice la trampa 3.

### Las cinco trampas

**1. Importar el módulo ya escribe en disco.** No hace falta llegar al bucle: construir el manager
crea la sesión.

```
trampa 1 - tras construir SOLO el manager: ['agents', 'multi_agents', 'session.json']
```

Un `import agent` en las pruebas deja `sessions/` y `sessions.db` detrás. Es el diseño del SDK, no un
fallo — pero por eso `sessions/` y `*.db` están en el `.gitignore` de la raíz **desde antes** de que
existiera este código.

**2. Cambiar de backend es cambiar de memoria.** Es la trampa que más rabia da, y la que el flag
`--sqlite` te hará pisar. El mismo `session_id` en otro almacén es **otra conversación**: tras cuatro
corridas guardadas en JSON, `python agent.py ana --sqlite` arranca en `restored messages: 0`. El
`session_id` identifica la sesión **dentro** de un almacén, nunca entre almacenes.

**3. El `system_prompt` no se persiste.** Restaurando `ana` con un prompt distinto:

```
trampa 3 - mensajes 2 del disco, prompt 'PROMPT B' del codigo
```

Los mensajes vienen del disco; el prompt, del archivo que acabas de editar. Cambiar el
`SYSTEM_PROMPT` afecta a las conversaciones viejas desde el turno siguiente.

**4. Dos `Agent` con el mismo manager, revienta.**

```
trampa 4 - SessionException: The `agent_id` of an agent must be unique in a session.
```

Un manager, un agente. Para dos agentes en la misma sesión hacen falta dos `agent_id` distintos.

**5. El `session_id` con separadores: lo valida `FileSessionManager`, *no* el contrato.**

```
trampa 5 FileSessionManager:   ValueError: session_id=../../etc | id cannot contain path separators
trampa 5 SqliteSessionManager: ACEPTADO -> session_id='../../etc'
```

Ésta es la lección del ejemplo aplicada a sí mismo. La validación **no la pone el SDK en general**:
la pone `FileSessionManager`, porque allí el `session_id` es parte de una ruta de archivo. Implementar
`SessionRepository` te da **el contrato, no los guardarraíles del otro backend**. En SQLite es
inofensivo —es el valor de una columna, y las nueve consultas van parametrizadas—, pero si tu backend
convirtiera el `session_id` en una ruta, una URL o una clave de S3, la validación te toca a ti.

### Las diferencias con `01`

| | `01-basic-tool-agent` | `09-persistent-session-agent` |
|---|---|---|
| Llamada a `Agent(...)` | `model`, `system_prompt`, `tools` | `model`, `system_prompt`, **`session_manager`** |
| Herramientas | 2 (`@tool`) | **0** — el ejemplo no va de herramientas |
| Archivos de código | 1 (`agent.py`) | 2: `agent.py` (52 líneas) + `sqlite_session.py` (79) |
| CLI | Sin argumentos | `session_id` posicional + `--sqlite` / `--no-session` |
| Escribe en disco | No | Sí: `sessions/` o `sessions.db` |
| Dependencias | 3 | Las mismas 3 |

El segundo archivo es una excepción deliberada a *"`agent.py` es el ejemplo entero"*: el backend
propio **tiene** que vivir aparte para que se vea que el agente no lo conoce. Aun así, 52 + 79 = 131
líneas repartidas, frente a las 110 que `06` tiene en un solo archivo.

## Configuración y Pruebas

### Prerrequisitos

- Python 3.10 o superior
- Una `OPENAI_API_KEY` en un `.env` local
- **Sin AWS** y **sin Node.js**, igual que en `03`–`08`
- El `requirements.txt` es **idéntico al de `08`** (`diff` sin salida): ni el primitivo de sesión ni
  el backend propio añaden una sola dependencia — `sqlite3` y `json` son de la biblioteca estándar

### Cómo ejecutarlo

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt   # solo la primera vez
cp .env.example .env            # y pon tu clave real en el .env

.venv/bin/python agent.py ana                 # 1. dile el dato, sal con 'exit'
.venv/bin/python agent.py ana                 # 2. proceso NUEVO: preguntaselo
.venv/bin/python agent.py bruno               # 3. otra sesion: no lo sabe
.venv/bin/python agent.py ana --no-session    # 4. sin memoria: no lo sabe
.venv/bin/python agent.py ana --sqlite        # 5. otro almacen: empieza vacio (trampa 2)
```

| Variable | Descripción |
|---|---|
| `OPENAI_API_KEY` | Tu clave de OpenAI. La lee el cliente de `openai` por su cuenta; ninguna línea de código la menciona |
| `MODEL_ID` | Modelo a usar. Por defecto `gpt-5.4-mini` |

`MODEL_ID=gpt-5.4 .venv/bin/python agent.py ana` cambia el modelo para una sola corrida.

> **El `session_id` y el backend NO son configuración de entorno**, a diferencia de `MODEL_ID`. Son
> argumentos de la línea de órdenes, y a propósito: quieres cambiar de memoria entre una corrida y la
> siguiente sin editar ningún archivo.

> **La respuesta sale dos veces en las transcripciones, y es correcto.** `09` mantiene el
> `callback_handler` por defecto de `01` (no pasa `callback_handler=None` como `03`–`08`): ese handler
> hace *streaming* de la respuesta a medida que llega, y luego el `print(f"\nMnemo > {response}")` del
> bucle la imprime entera otra vez. La primera copia es del SDK; la segunda, del bucle. Es la primera
> vez que la serie enseña, medido, qué hace de verdad el handler por defecto — y no se recorta.

### Transcripción de ejemplo

Corridas **reales** contra `gpt-5.4-mini`, en este orden, cada una en su propio proceso.

**1. Escribir** — sesión `ana`, todavía vacía:

```
Mnemo: I remember what you told me in an earlier run. Type 'exit' to quit.

Using LLM model: gpt-5.4-mini
Session 'ana' | store: FileSessionManager | restored messages: 0

You > mi codigo de socio es KRAKEN-7743
Entendido. Tu código de socio es **KRAKEN-7743**.
Mnemo > Entendido. Tu código de socio es **KRAKEN-7743**.

You > exit
```

**2. Recordar** — proceso nuevo, misma sesión. **Ésta es la prueba del ejemplo:**

```
Using LLM model: gpt-5.4-mini
Session 'ana' | store: FileSessionManager | restored messages: 2

You > cual es mi codigo de socio?
Tu código de socio es **KRAKEN-7743**.
Mnemo > Tu código de socio es **KRAKEN-7743**.
```

`restored messages: 2` se imprimió **antes** de que el modelo dijese nada: los dos mensajes de la
corrida 1 ya estaban en memoria.

**3. Aislar** — otro `session_id`, mismo almacén. **Control negativo**: aquí tiene que fallar.

```
Session 'bruno' | store: FileSessionManager | restored messages: 0

You > cual es mi codigo de socio?
No lo sé; no me has dicho cuál es tu código de socio. Si quieres, puedes decírmelo y lo recordaré para más adelante.
Mnemo > No lo sé; no me has dicho cuál es tu código de socio. Si quieres, puedes decírmelo y lo recordaré para más adelante.
```

Si aquí hubiera acertado `KRAKEN-7743`, la corrida 2 no probaría nada: lo habría adivinado, no
recordado.

**4. La línea base** — `--no-session`, que es el comportamiento de `01`–`08`:

```
Session 'ana' | store: none | restored messages: 0

You > cual es mi codigo de socio?
No lo sé. No me has dicho cuál es tu código de socio.
Mnemo > No lo sé. No me has dicho cuál es tu código de socio.
```

Mismo `session_id` que la corrida 2, misma pregunta, respuesta opuesta. La única diferencia es el
flag.

**5. La trampa 2** — mismo `session_id`, otro almacén:

```
Session 'ana' | store: SqliteSessionManager | restored messages: 0

You > cual es mi codigo de socio?
No lo sé; no me has dicho tu código de socio.
Mnemo > No lo sé; no me has dicho tu código de socio.
```

`ana` tenía cuatro mensajes en `sessions/`, pero **cero** en `sessions.db`. Cambiar de backend es
cambiar de memoria.

## Información Adicional

**El almacén guarda la conversación en claro.** Ni `sessions/*.json` ni `sessions.db` están cifrados:
cualquiera con acceso al disco lee todo lo que el usuario contó. Por eso `sessions/` y `*.db` están
en el `.gitignore` de la **raíz** del repositorio — este es el primer ejemplo de la serie que escribe
en el árbol del proyecto, y una conversación real commiteada por error no se borra del historial de
git con un `rm`. Si llevas esto a producción, el cifrado y la retención son tuyos: el contrato de
`SessionRepository` no los menciona.

**Los otros backends del SDK.** Strands trae también `S3SessionManager` (mismo contrato, bucket de S3)
y `SnapshotSessionManager`. No están aquí porque `S3SessionManager` exigiría credenciales de AWS, que
la serie entera evita, y porque el objetivo era enseñar **cómo se escribe uno**, no cómo se
configura el que ya existe. Si entendiste `sqlite_session.py`, ya sabes leer los dos.

**El gestor de ventana sigue ahí.** Por defecto, `SlidingWindowConversationManager` con
`window_size=40`. Persistir no es lo mismo que recordar sin límite: cuando la conversación crece, la
ventana recorta, y el `offset` con el que se llama a `list_messages` refleja lo ya descartado. Su
estado también se persiste. Configurarlo queda fuera de este ejemplo.

**Lo que queda para los siguientes.** La persistencia de `09` entra por **hooks** que el SDK registra
por ti; en `10-observable-agent` los escribimos nosotros. Después, `11` el bucle autónomo y `12` la
evaluación.

### Estructura del proyecto

```
09-persistent-session-agent/
├── agent.py            # constantes + SYSTEM_PROMPT + 3 ramas de backend + Agent + CLI (52 líneas, 0 @tool)
├── sqlite_session.py   # el backend propio: SCHEMA + 9 métodos del contrato (79 líneas, 0 dependencias nuevas)
├── requirements.txt    # 3 líneas — idéntico al de 08
├── .env.example        # 2 variables
├── README.md           # este archivo
├── .env                # tu clave; ignorado por git, no se commitea
├── sessions/           # lo que escribe FileSessionManager; ignorado por git
└── sessions.db         # lo que escribe SqliteSessionManager; ignorado por git
```

### Limpieza

Este ejemplo **sí** deja rastro, al contrario que `01`–`08`:

```bash
rm -rf sessions sessions.db     # borra las dos memorias
rm -rf .venv                    # borra el entorno
```

Borrar `sessions/session_ana/` es la forma de que `ana` empiece de cero sin cambiar de `session_id`.

### Recursos adicionales

- [Strands Agents — documentación](https://strandsagents.com/)
- [Gestión de sesiones y estado](https://strandsagents.com/latest/documentation/docs/user-guide/concepts/agents/session-management/)
  — `session_manager`, `FileSessionManager` y `S3SessionManager`
- [Hooks en Strands](https://strandsagents.com/latest/documentation/docs/user-guide/concepts/agents/hooks/)
  — los eventos por los que entra la persistencia, y el primitivo de `10`
- [Gestión del contexto de conversación](https://strandsagents.com/latest/documentation/docs/user-guide/concepts/agents/conversation-management/)
  — el `SlidingWindowConversationManager` y su `window_size`
- [Modelos de OpenAI en Strands](https://strandsagents.com/latest/documentation/docs/user-guide/concepts/model-providers/openai/)
