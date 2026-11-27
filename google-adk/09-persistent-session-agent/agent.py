import asyncio
import os
import sys
from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.sessions.sqlite_session_service import SqliteSessionService
from google.genai import types
from json_session import JsonSessionService
# Lee el .env local: la clave (que toma LiteLLM) y el modelo.
load_dotenv()
MODEL_ID = os.getenv("MODEL_ID", "gpt-6-luna")
# Los dos almacenes viven junto a este archivo, no en el cwd de quien lanza.
HERE = os.path.dirname(os.path.abspath(__file__))

SYSTEM_PROMPT = """You are Mnemo, a personal assistant whose memory survives a restart.

What the user tells you about themselves stays true in later conversations: recall it when asked,
and never invent a detail you were not given.

If you were never told something, say plainly that you do not know it."""

# El id de sesion es el primer argumento que no sea un flag: es la CLAVE con la que se guarda
# y se recupera la conversacion. Dos ids distintos son dos memorias distintas.
SESSION_ID = next((arg for arg in sys.argv[1:] if not arg.startswith("--")), "default")

# Lo UNICO que cambia entre las tres corridas. El agente de abajo no sabe cual le toco.
if "--no-session" in sys.argv:
    session_service = InMemorySessionService()   # linea base: se pierde al cerrar el proceso
elif "--sqlite" in sys.argv:
    session_service = SqliteSessionService(os.path.join(HERE, "sessions.db"))   # viene con ADK
else:
    session_service = JsonSessionService(os.path.join(HERE, "sessions"))        # propio

# El agente: identico al de 01 salvo por no tener tools. La memoria no es cosa suya.
agent = LlmAgent(
    name="Mnemo",
    model=LiteLlm(model=f"openai/responses/{MODEL_ID}"),
    instruction=SYSTEM_PROMPT,
)

async def main():
    print("\nMnemo: I remember what you told me in an earlier run. Type 'exit' to quit.\n")
    print(f"Using LLM model: {MODEL_ID}")
    # Recuperar o crear: con el mismo id y el mismo almacen vuelve el historial anterior.
    key = {"app_name": "mnemo", "user_id": "user", "session_id": SESSION_ID}
    session = (await session_service.get_session(**key)
               or await session_service.create_session(**key))
    store = "none" if "--no-session" in sys.argv else type(session_service).__name__
    # Los eventos ya restaurados ANTES del primer turno: la prueba de que la memoria se cargo.
    print(f"Session '{SESSION_ID}' | store: {store} | restored messages: {len(session.events)}")
    # El Runner guarda cada evento en el servicio que le pasen.
    runner = Runner(agent=agent, app_name="mnemo", session_service=session_service)

    while True:
        user_input = input("\nYou > ")
        if user_input.lower() == "exit":
            break
        message = types.Content(role="user", parts=[types.Part(text=user_input)])
        async for event in runner.run_async(user_id="user", session_id=SESSION_ID, new_message=message):
            if event.is_final_response() and event.content and event.content.parts:
                text = "".join(part.text for part in event.content.parts if part.text and not part.thought)
                print(f"\nMnemo > {text}")

if __name__ == "__main__":
    asyncio.run(main())
