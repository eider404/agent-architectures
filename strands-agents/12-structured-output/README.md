# 12 · Structured output

`05` ya devolvía un objeto Pydantic, pero como **medio**: `Route` era un enum cerrado que el LLM
no podía fallar, solo un despacho hacia una de cuatro ramas fijas. `12` lo convierte en el **fin**
del ejemplo: un esquema que sí puede fallar, y que falla de verdad.

```python
# 05 — el objeto como medio: un enum cerrado, el LLM no puede equivocarse de tipo
route = classifier(request, structured_output_model=Route).structured_output
answer = SPECIALISTS[route.category](request)          # el objeto solo sirve para despachar

# 12 — el objeto como fin: un esquema fallable, con una invariante que cruza sus propios campos
invoice = agent(document, structured_output_model=Invoice).structured_output
print(invoice.total, invoice.items, invoice.issued_on) # el objeto ES el resultado
```

La diferencia no está en la llamada —es literalmente la misma línea—, está en qué pasa cuando el
modelo se equivoca: `Route` no tiene forma de estar mal (el `Literal`/`Enum` se lo impide);
`Invoice` sí, porque su `@model_validator` compara `total` contra la suma de `items`, algo que
ninguna restricción de tipo puede expresar por sí sola.

## Descripción

Ledger es un extractor de facturas de un solo agente, sin herramientas: lee un documento de texto
plano de `sandbox/` y llama al agente con `structured_output_model=Invoice`. Copia la forma de `01`
sin `@tool` y la línea estructurada de `05`; lo único nuevo es el esquema y su validador.

`Invoice` tiene seis campos —`invoice_id`, `supplier`, `issued_on: date`, `currency:
Literal["EUR","USD"]`, `items: list[LineItem]`, `total`— y una regla que ningún campo por
separado puede imponer: **el total tiene que cuadrar con la suma de las líneas**.
`sandbox/shipping.txt` está pensado para poner a prueba justo esa regla: imprime un cargo de
envío fuera de la tabla de líneas pero incluido en el total, así que copiar el total impreso sin
más es el error natural.

| Documento | Qué tiene de particular | Qué demuestra |
|---|---|---|
| `clean.txt` | Todo impreso, total cuadra, fecha ISO | El camino feliz |
| `shipping.txt` | Cargo de envío fuera de la tabla, incluido en el total | La invariante `total == Σ items` |
| `messy.txt` | Fecha en prosa (`4 March 2026`), moneda como `$` | Coerción de tipos: `str` → `date`, símbolo → `Literal` |

## Cómo Funciona

### Detalles del ejemplo

| Información | Detalles |
|---|---|
| **Características de Strands** | `structured_output_model=` en la llamada al agente + `result.structured_output` |
| **Patrón de agente** | Agente único, sin herramientas — el esquema Pydantic hace el trabajo de una tool |
| **Modelo** | `gpt-5.4-mini` por defecto (configurable con `MODEL_ID`); la corrida real usó `gpt-5.4-nano` |
| **Archivos de código** | 1: `agent.py` (75 líneas) |
| **Dependencias nuevas** | **Cero**: `requirements.txt` es idéntico al de `09`/`10`/`11` — Pydantic ya viene con el SDK |

### El turno, de un vistazo

```
sandbox/shipping.txt
        │
        │  Path.read_text()                 <- Python, no el LLM
        ▼
   agent(document, structured_output_model=Invoice)
        │
        │  el SDK registra Invoice como tool dinamica, con SU nombre de clase
        ▼
   ┌─────────── un solo turno ───────────┐
   │  LLM -> toolUse Invoice(total=315)  │
   │  Pydantic -> ValidationError        │
   │  toolResult status=error  ──────────┼──> el LLM lo lee
   │  LLM -> toolUse Invoice(corregido)  │
   │  Pydantic -> ok, store + stop_loop  │
   └─────────────────────────────────────┘
        │
        ▼
   result.structured_output  ->  Invoice(...)   # objeto de Python, no texto
```

No hay ningún `try/except`, ningún contador de reintentos, ninguna función de parsing en
`agent.py`. Todo el ciclo de arriba corre dentro de la única llamada `agent(...)`.

### Qué viaja al LLM y qué no

El esquema se convierte en la especificación JSON de una tool que el modelo puede llamar. Medido
sobre el `Invoice` real de este ejemplo:

```python
>>> convert_pydantic_to_tool_spec(Invoice)
name: Invoice
minimum in schema: True       # LineItem.quantity: ge=1, unit_price: ge=0, total: ge=0
minLength/minItems in schema: True   # items: min_length=1
"add up to" in schema: False  # el cuerpo del @model_validator NO esta aqui
```

Las restricciones **declarativas** (`ge=`, `min_length=`) sí viajan dentro del JSON Schema de la
tool: el modelo las ve antes de llamar. El cuerpo del `@model_validator` **no** viaja nunca — solo
su mensaje de error, y solo si la validación falla. Por eso ese mensaje está escrito como una
instrucción para el LLM (*"Re-read the document: a charge included in the total is missing from
items."*), no como un diagnóstico para un humano.

Un matiz más: el SDK envuelve la docstring del modelo en la descripción de la tool con
`"IMPORTANT: This StructuredOutputTool should only be invoked as the last and final tool before
returning the completed result to the caller. <description>...</description>"`. El
`SYSTEM_PROMPT` no necesita decir "llama a la tool al final" — el SDK ya lo dice.

### El ciclo de autocorrección, medido sin llamar al modelo real

Con un modelo guionizado (`strands.models.model.Model` falso, sin red ni clave) que primero
propone el total sin el envío y luego se corrige, usando los números reales de `shipping.txt`:

```
toolResult #1 (status: error):
{
  "toolUseId": "tu-1",
  "status": "error",
  "content": [
    {
      "text": "Validation failed for Invoice. Please fix the following errors:\n- Field 'root': Value error, total is 315.0 but the 1 items add up to 300.0. Re-read the document: a charge included in the total is missing from items."
    }
  ]
}

toolResult #2 (status: success):
{
  "toolUseId": "tu-2",
  "status": "success",
  "content": [{ "text": "Successfully validated Invoice structured output" }]
}

final total: 315.0 items: 2
```

El mensaje que ve el modelo lleva el prefijo `Value error, ` que antepone Pydantic al `str()`
propio del `ValueError` — el README lo cita **con** ese prefijo porque es lo que el modelo lee de
verdad. Las restricciones declarativas, en cambio, producen errores por **ruta de campo**
(`items -> 0 -> quantity`), no por `root`: el modelo sabe exactamente qué línea arreglar sin tener
que releer todo el documento.

### Verificado también a mano, sin agente ni modelo

```python
>>> Invoice(invoice_id='X', supplier='Y', issued_on='2026-03-04', currency='EUR',
...         items=[{'description':'a','quantity':2,'unit_price':50}], total=999)
ValidationError: Field 'root': Value error, total is 999.0 but the 1 items add up to 100.0. ...

>>> # quantity=0            -> Field 'items -> 0 -> quantity': Input should be greater than or equal to 1
>>> # items=[]              -> Field 'items': List should have at least 1 item after validation, not 0
>>> # issued_on='4 March 2026' -> Field 'issued_on': Input should be a valid date or datetime, ...
>>> # currency='$'          -> Field 'currency': Input should be 'EUR' or 'USD'
```

## Configuración y Pruebas

### Prerrequisitos

- Python 3.10 o superior
- Una `OPENAI_API_KEY` en un `.env` local
- **Sin AWS**, **sin Node.js**, **sin dependencias nuevas**: `requirements.txt` es idéntico al de
  `09`/`10`/`11` (`diff` sin salida)

### Cómo ejecutarlo

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt   # solo la primera vez
cp .env.example .env            # y pon tu clave real en el .env

.venv/bin/python agent.py       # type 'exit' to quit
```

| Variable | Descripción |
|---|---|
| `OPENAI_API_KEY` | Tu clave de OpenAI. La lee el cliente de `openai` por su cuenta; ninguna línea de código la menciona |
| `MODEL_ID` | Modelo a usar. Por defecto `gpt-5.4-mini` |

### Los límites duros, medidos sobre los archivos finales

```
wc -l agent.py                               # 75  (tope: 75)
grep -c "@tool" agent.py                     # 0
grep -c "hooks=" agent.py                    # 0
grep -c "structured_output_model" agent.py   # 1
grep -c "model_validator" agent.py           # 2
diff requirements.txt ../11-human-in-the-loop/requirements.txt   # sin salida
grep -rn "api_key\|sk-" agent.py             # sin resultados
ls sandbox/*.txt | wc -l                     # 3
awk '{print length}' agent.py | sort -rn | head -1   # 95  (norma de la serie: <= 99)
```

### Transcripción real

Corrida real contra `gpt-5.4-nano` (vía `MODEL_ID` en `.env`), las tres facturas en orden:

```
Ledger: invoice extractor (gpt-5.4-nano). Type 'exit' to quit.
Available: clean.txt, messy.txt, shipping.txt

Invoice > shipping.txt

[ok] INV-8843 · Nordkapp Rigging AB · 2026-03-11 · EUR
     3 x Deck cleat               @   100.00
     1 x Shipping fee             @    15.00
     total: 315.00  (date)

Invoice > clean.txt

[ok] INV-8842 · Nordkapp Rigging AB · 2026-03-04 · EUR
     2 x Mooring line 24mm        @    85.00
     1 x Shackle set              @    42.50
     total: 212.50  (date)

Invoice > messy.txt

[ok] INV-8844 · Nordkapp Rigging AB · 2026-03-04 · USD
     4 x Winch handle             @    25.00
     1 x Anchor chain 10m         @    80.00
     total: 180.00  (date)

Invoice > exit
```

**Nota honesta sobre esta corrida:** `shipping.txt` **no disparó el validador**. `gpt-5.4-nano`
incluyó el envío como línea (`1 x Shipping fee @ 15.00`) desde la primera llamada, tanto con la
trampa original (una sección `Charges:` tabular) como con una versión reescrita como nota en
prosa (*"Note: a 15.00 shipping fee applies to this order and is already reflected in the total
below."*). Confirmado sin ambigüedad releyendo `agent.messages` tras la corrida:

```python
>>> agent.extract('shipping.txt')
>>> len(agent.agent.messages)       # 3: prompt, toolUse, toolResult
3
>>> [m for m in agent.agent.messages if ... status == 'error']
[]                                   # ningun retry, exito a la primera
```

Esto **no invalida el ejemplo**: la sección anterior ("El ciclo de autocorrección, medido sin
llamar al modelo real") reproduce el mismo mecanismo — el mismo `Invoice`, el mismo SDK, los
mismos números de `shipping.txt` — con un modelo guionizado que sí falla la primera vez, y captura
el `toolResult` de error **literal**. El validador funciona exactamente como se especificó (visto
también a mano, sin agente, en la sección anterior); lo que no se pudo forzar de manera confiable
fue que el modelo real cometiera el error en una corrida concreta. `messy.txt` sí demuestra
coerción real contra el modelo: `2026-03-04` como `date` y `USD` como `Literal`, ambos a partir de
texto que no estaba en ese formato en el documento (`4 March 2026`, `$`).

## Información Adicional

### Los tres bordes, medidos

- **Forzado.** Si el modelo responde con texto (`stop_reason == "end_turn"`) sin llamar a la tool,
  el SDK inyecta el mensaje de usuario `"You must format the previous response as structured
  output."` y reintenta con `tool_choice={'tool': {'name': 'Invoice'}}`. Verificado literal contra
  el modelo guionizado.
- **`StructuredOutputException`.** Si el modelo vuelve a responder con `end_turn` después de ese
  forzado, el SDK propaga `StructuredOutputException("The model failed to invoke the structured
  output tool even after it was forced.")` sin capturarla — el ejemplo no la atrapa a propósito.
- **`stop_reason == "tool_use"`, nunca `"end_turn"`, en una corrida exitosa.** Es la trampa real
  para quien copie este patrón esperando lo segundo: cuando la validación pasa, el SDK marca
  `stop_loop = True` y corta el bucle con el `stop_reason` de la tool call, no el de fin de turno.
- La tool dinámica que registra el SDK se llama **`Invoice`** — el nombre de la clase, no
  `"structured_output"` — y `agent.tool_registry.dynamic_tools` vuelve a estar vacío después de
  `agent(...)`: se registra y se borra dentro de cada llamada.

### Nota de seguridad, en una frase

Un esquema garantiza **forma**, no **verdad**: si el modelo lee mal dos importes de forma
consistente (por ejemplo, invierte precio y cantidad en las dos únicas líneas), el
`@model_validator` los deja pasar porque el total sigue cuadrando con lo que el modelo — mal —
extrajo.

### `requirements.txt` idéntico al de `09`/`10`/`11`

Pydantic no se añade como dependencia propia: el SDK la trae de forma transitiva. Igual que los
hooks o el sistema de interrupciones, la salida estructurada es parte del núcleo de
`strands-agents`, no un extra.

### Correcciones frente al plan

- **`sandbox/shipping.txt` no disparó el validador en ninguna de las dos corridas reales**, ni con
  la trampa original ni con una versión reescrita como nota en prosa. El plan preveía este caso
  explícitamente y prohibía falsificar el transcript: la corrida real se documenta tal como
  ocurrió arriba, y el mecanismo de autocorrección se demuestra con el modelo guionizado y con la
  construcción manual del objeto, ambos con los números reales de la factura.
- El resto de hallazgos del plan se confirmaron exactos en este `.venv` (`strands-agents 1.56.0`,
  `pydantic 2.13.5`): Pydantic no coerciona `"4 March 2026"` a `date` (es trabajo del LLM, no de
  un `field_validator` añadido a propósito); el mensaje del validador lleva el prefijo `Value
  error, `; el SDK envuelve la docstring del modelo en su propia descripción de tool.

### Lo que existe y no se usa

| Símbolo | Por qué no |
|---|---|
| `structured_output_model=` en el constructor de `Agent` | Existe como alternativa a pasarlo en la llamada; aquí se prefiere en la llamada porque queda en la misma línea que el documento que se está leyendo |
| `structured_output_prompt` propio | Permitiría reemplazar el prompt de forzado por defecto; el mensaje por defecto ya es correcto para este dominio |
| Combinar `tools=[...]` con `structured_output_model=` (como el notebook upstream) | Dos variables nuevas a la vez rompería la regla de la serie de cambiar una por ejemplo |

### Cierre de la serie

Doce ejemplos, cada uno la forma anterior con exactamente una diferencia controlada:

| # | Ejemplo | La variable que cambió |
|---|---|---|
| 01 | `basic-tool-agent` | `@tool` definidas en el propio archivo |
| 02 | `mcp-agent` | Tools obtenidas en tiempo de ejecución de un servidor MCP |
| 03 | `sequential-pipeline` | Varios `Agent` encadenados |
| 04 | `parallel-fanout` | `asyncio.gather` / `invoke_async` en paralelo |
| 05 | `router-agent` | Salida estructurada usada para **despachar** |
| 06 | `agents-as-tools` | Un `Agent` envuelto en `@tool` |
| 07 | `agent-graph` | `GraphBuilder`, un grafo explícito de agentes |
| 08 | `agent-swarm` | `Swarm`, coordinación autónoma entre agentes |
| 09 | `persistent-session-agent` | `FileSessionManager`, historial que sobrevive al proceso |
| 10 | `observable-agent` | Hooks de solo lectura para trazar el ciclo de vida |
| 11 | `human-in-the-loop` | Un hook que **interrumpe**, no solo observa |
| 12 | `structured-output` | Salida estructurada usada como **fin**, con un esquema que puede fallar y corregirse |

De `str` a objeto validado: los once ejemplos anteriores terminaban en texto o, cuando mucho, en
un enum que el modelo no podía fallar. `12` cierra la serie mostrando lo que un esquema realmente
garantiza — forma — y lo que no — verdad —, con el error de validación real y la segunda llamada
con la que el modelo se corrige, ambos a la vista.

### Estructura del proyecto

```
12-structured-output/
├── agent.py            # LineItem + Invoice (con @model_validator) + Agent + CLI (75 lineas)
├── requirements.txt    # 3 líneas — idéntico a 09/10/11
├── .env.example         # 2 variables
├── README.md            # este archivo
├── sandbox/             # las tres facturas a extraer
│   ├── clean.txt
│   ├── shipping.txt
│   └── messy.txt
├── .env                 # tu clave; ignorado por git, no se commitea
└── .venv/               # ignorado por git
```

### Limpieza

```bash
rm -rf .venv    # borra el entorno
```

### Recursos adicionales

- [Strands Agents — documentación](https://strandsagents.com/)
- [Structured output en Strands](https://strandsagents.com/latest/documentation/docs/user-guide/concepts/agents/structured-output/)
- [Modelos de OpenAI en Strands](https://strandsagents.com/latest/documentation/docs/user-guide/concepts/model-providers/openai/)
