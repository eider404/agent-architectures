# Vision

Un repositorio para aprender cómo se construyen agentes de IA. Muestra arquitecturas de agentes con ejemplos mínimos y autocontenidos, y repite las mismas arquitecturas en varios frameworks para poder compararlos. Hoy los 12 ejemplos están hechos con Strands Agents. El siguiente framework será Google ADK, y más adelante se sumarán otros aún por definir.

## Goals
- Implementar las 12 arquitecturas con Google ADK en una carpeta `google-adk/` con la misma numeración, el mismo escenario y el mismo comportamiento que `strands-agents/`.
- Que cada arquitectura se pueda comparar directamente entre frameworks: mismo propósito, misma conversación de ejemplo y diferencias explicadas en el README.
- Preparar la estructura para añadir más frameworks sin reorganizar el repo, siguiendo el patrón `<framework>/NN-nombre/`.
- Mantener el README raíz como índice de arquitecturas y frameworks.

## Target users
- Desarrolladores que quieren entender patrones de agentes (pipeline, fan-out, router, grafo, swarm, human-in-the-loop…) leyendo código corto de principio a fin.
- Quienes están eligiendo framework y necesitan ver cómo se expresa el mismo patrón en cada uno.

## Principles
- Una arquitectura por carpeta, en un solo `agent.py` de unas 70 líneas.
- Cada ejemplo cambia una sola cosa respecto al anterior: esa diferencia es la lección.
- Ejemplos autocontenidos: cada uno tiene su propio `requirements.txt`, `.env.example` y `README.md`, sin dependencias compartidas.
- Paridad entre frameworks: la misma arquitectura resuelve el mismo escenario en todos.
- Claridad antes que completitud: el código es didáctico y no está pensado para producción.

## Out of scope
- Convertir los ejemplos en aplicaciones reales o listas para producción (despliegue, escalado, autenticación).
- Librerías, utilidades o build compartidos entre ejemplos o entre frameworks.
- Abstracciones que oculten el framework (wrappers genéricos, capas de compatibilidad).
- Ejemplos que dependan de infraestructura cloud específica (por ejemplo, AWS) cuando no es imprescindible.

## Quality bar
- Cada ejemplo arranca siguiendo solo los pasos de su README.
- Su README incluye el diagrama de la arquitectura, una conversación de ejemplo y qué probar.
- `.env.example` sin valores reales y sin secretos en el repo.
- Al añadir o cambiar un ejemplo, se actualiza su equivalente en los demás frameworks, o queda registrado como pendiente.

## Protected areas
- `**/.env`
- `README.md` (índice raíz)
- `CLAUDE.md`, `AGENTS.md`
- La elección de nuevos frameworks que se vayan a incorporar
