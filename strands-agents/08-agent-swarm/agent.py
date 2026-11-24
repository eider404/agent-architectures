import asyncio
import os
from dotenv import load_dotenv
from strands import Agent
from strands.models.openai_responses import OpenAIResponsesModel
from strands.multiagent import Swarm
# Lee el .env local: la clave (que toma el cliente de openai) y el modelo.
load_dotenv()
MODEL_ID = os.getenv("MODEL_ID", "gpt-6-luna")

RESEARCHER_PROMPT = """You are researcher, one of three peers on a small software team. Turn a vague
request into at most five numbered requirements: inputs, outputs, and the edge cases that matter.
Write no code. When your list is ready, hand off to the peer who writes the code, and put the
requirements in the handoff context so the whole team keeps them. At most 70 words."""

CODER_PROMPT = """You are coder, one of three peers on a small software team. Write one short Python
function, and nothing else around it. Never ask for requirements: decide the edge cases yourself and
write the code. Nothing you write travels on its own, so hand off to the peer who reviews it with the
WHOLE function pasted in the handoff message. If a review names a defect, fix it and hand it back
with the whole corrected function again. At most 15 lines."""

REVIEWER_PROMPT = """You are reviewer, one of three peers on a small software team. Judge the code in
the handoff message against the requirements; never ask for it again. If you find a concrete defect,
name it and hand off in the same turn to the peer who wrote the code; do not fix it yourself. If the
code works on the stated cases, do NOT hand off: answer with the final function and one line saying
why it is right. Hand back only for a defect that makes it wrong on a case the requirements name,
never for style or extra validation you would merely prefer; when in doubt, approve. Approving is the
only way this task ever ends. At most 90 words."""

# Un par del enjambre. La 'description' no es adorno: el Swarm la inyecta en el roster que cada
# agente recibe, y es lo UNICO por lo que un par decide a quien pasarle el control.
def peer(name: str, description: str, system_prompt: str) -> Agent:
    return Agent(model=OpenAIResponsesModel(model_id=MODEL_ID), name=name, description=description,
                 system_prompt=system_prompt, callback_handler=None)

# La arquitectura entera: una lista de pares. Ni aristas, ni condiciones, ni orden.
PEERS = [peer("researcher", "Turns a vague request into numbered requirements. Writes no code.", RESEARCHER_PROMPT),
         peer("coder", "Writes and fixes the Python code.", CODER_PROMPT),
         peer("reviewer", "Reviews code against the requirements and gives the final answer.", REVIEWER_PROMPT)]
# Sin orquestador, esto es lo UNICO que acota la corrida: con los valores por defecto, un
# ping-pong entre dos pares cuesta 20 turnos y 40 llamadas al modelo antes de parar (medido).
swarm = Swarm(PEERS, max_handoffs=6, max_iterations=6, node_timeout=60.0,
              repetitive_handoff_detection_window=4, repetitive_handoff_min_unique_agents=3)

async def run_task(task: str) -> str:
    """Un solo turno. La ruta no esta en este archivo: la deciden los pares mientras corren."""
    # Los pares acumulan historial, pero el Swarm reinicia el suyo en cada invocacion (medido):
    # aqui sobra el reseteo manual que 03-07 hacian al empezar cada corrida.
    result = None
    async for event in swarm.stream_async(task):
        kind = event.get("type")   # ojo: 'multiagent_*', sin guion bajo, pese a lo que dice el docstring
        if kind == "multiagent_node_start":
            print(f"\n[{event['node_id']}] pensando...")
        elif kind == "multiagent_handoff":
            # El motivo del traspaso, escrito por el par que suelta el control. Es la
            # coordinacion entera del sistema, y solo se ve aqui.
            print(f"  {event['from_node_ids'][0]} ──► {event['to_node_ids'][0]}: {event['message']}")
        elif kind == "multiagent_result":
            result = event["result"]

    # La prueba de la ruta la da el primitivo. Y el status importa: si los topes cortaron la
    # corrida sale FAILED, y lo de abajo es un trabajo a medias, no una conclusion.
    print(f"\n[swarm] {' ──► '.join(n.node_id for n in result.node_history)}  ({result.status.value})")
    # No hay nodo 'responder' como en 07: la respuesta es la del ultimo par que hablo,
    # y cual sea eso no se sabe hasta que la corrida termina.
    answer = str(result.results[result.node_history[-1].node_id])
    print(answer.strip())
    return answer

if __name__ == "__main__":
    print("\nDevSwarm: Ask the team for a small function. Type 'exit' to quit.\n")
    print(f"Using LLM model: {MODEL_ID}")

    while True:
        user_input = input("\nTask > ")
        if user_input.lower() == "exit":
            break
        asyncio.run(run_task(user_input))
