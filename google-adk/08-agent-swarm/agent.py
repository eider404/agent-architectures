import asyncio
import logging
import os
from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.agents.invocation_context import LlmCallsLimitExceededError
from google.adk.agents.run_config import RunConfig
from google.adk.models.lite_llm import LiteLlm
from google.adk.runners import InMemoryRunner
from google.genai import types
# Lee el .env local: la clave (que toma LiteLLM) y el modelo.
load_dotenv()
MODEL_ID = os.getenv("MODEL_ID", "gpt-6-luna")
# Silencia avisos y trazas internas de ADK (p. ej. al cortar por el tope de llamadas).
logging.getLogger("google_adk").setLevel(logging.CRITICAL)

RESEARCHER_PROMPT = """You are researcher, one of three peers on a small software team. Turn a vague
request into at most five numbered requirements: inputs, outputs, and the edge cases that matter.
Write no code. When your list is ready, publish it with `post` so the whole team keeps it, then
transfer to the peer who writes the code. At most 70 words."""

CODER_PROMPT = """You are coder, one of three peers on a small software team. Write one short Python
function, and nothing else around it. Never ask for requirements: decide the edge cases yourself and
write the code. Nothing you write travels on its own, so publish the WHOLE function with `post`, then
transfer to the peer who reviews it. If a review names a defect, fix it, post the whole corrected
function again and transfer back. At most 15 lines."""

REVIEWER_PROMPT = """You are reviewer, one of three peers on a small software team. Judge the posted
code against the requirements; never ask for it again. If you find a concrete defect, name it with
`post` and transfer in the same turn to the peer who wrote the code; do not fix it yourself. If the
code works on the stated cases, do NOT post or transfer: answer with the final function and one line
saying why it is right. Hand back only for a defect that makes it wrong on a case the requirements
name, never for style or extra validation you would merely prefer; when in doubt, approve. Approving
is the only way this task ever ends. At most 90 words."""

# Sin orquestador, esto es lo que acota la corrida: unos 6 turnos de dos llamadas cada uno.
MAX_LLM_CALLS = 12

# transfer_to_agent solo lleva el nombre del destino: el trabajo viaja en el historial compartido.
def post(message: str) -> str:
    """Publish your work so your teammates can read it. Call it before transfer_to_agent.

    Args:
        message: Everything the next peer needs: requirements, the whole code or a defect.
    """
    return "Posted. Now call transfer_to_agent."

# Un par del enjambre. La 'description' no es adorno: ADK la inyecta en la lista de destinos que
# cada agente recibe, y es lo UNICO por lo que un par decide a quien pasarle el control.
def peer(name: str, description: str, instruction: str, **kwargs) -> LlmAgent:
    return LlmAgent(name=name, model=LiteLlm(model=f"openai/responses/{MODEL_ID}"),
                    description=description, instruction=instruction, tools=[post], **kwargs)

# La arquitectura entera: tres pares. Ni aristas, ni condiciones, ni orden. ADK exige un arbol:
# researcher recibe la tarea y tiene a los otros dos como sub_agents, pero los tres se alcanzan.
team = peer("researcher", "Turns a vague request into numbered requirements. Writes no code.",
            RESEARCHER_PROMPT,
            sub_agents=[peer("coder", "Writes and fixes the Python code.", CODER_PROMPT),
                        peer("reviewer", "Reviews code against the requirements and gives the final answer.",
                             REVIEWER_PROMPT)])
runner = InMemoryRunner(agent=team, app_name="devswarm")

async def run_task(task: str) -> str:
    """Un solo turno. La ruta no esta en este archivo: la deciden los pares mientras corren."""
    session = await runner.session_service.create_session(app_name="devswarm", user_id="user")
    message = types.Content(role="user", parts=[types.Part(text=task)])
    history, note, answer, status = [team.name], "", "", "completed"
    print(f"\n[{team.name}] pensando...")
    try:
        async for event in runner.run_async(user_id="user", session_id=session.id, new_message=message,
                                            run_config=RunConfig(max_llm_calls=MAX_LLM_CALLS)):
            for call in event.get_function_calls():
                if call.name == "post":
                    note = call.args.get("message", "")
            if target := event.actions.transfer_to_agent:
                print(f"  {event.author} ──► {target}: {note}\n\n[{target}] pensando...")
                history.append(target)
                note = ""
            if event.is_final_response() and event.content and event.content.parts:
                answer = "".join(p.text for p in event.content.parts if p.text and not p.thought)
    except LlmCallsLimitExceededError:
        status = "failed"   # el tope corto la corrida: es un trabajo a medias, no una conclusion

    print(f"\n[swarm] {' ──► '.join(history)}  ({status})")
    # No hay nodo 'responder' como en 07: la respuesta es la del ultimo par que hablo.
    print(answer.strip())
    return answer

async def main():
    print("\nDevSwarm: Ask the team for a small function. Type 'exit' to quit.\n")
    print(f"Using LLM model: {MODEL_ID}")

    while True:
        user_input = input("\nTask > ")
        if user_input.lower() == "exit":
            break
        await run_task(user_input)

if __name__ == "__main__":
    asyncio.run(main())
