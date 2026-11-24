import os
import sys
from dotenv import load_dotenv
from strands import Agent
from strands.models.openai_responses import OpenAIResponsesModel
from strands.session import FileSessionManager
from sqlite_session import SqliteSessionManager
# Lee el .env local: la clave (que toma el cliente de openai) y el modelo.
load_dotenv()
MODEL_ID = os.getenv("MODEL_ID", "gpt-6-luna")
# Los dos almacenes viven junto a este archivo, no en el cwd de quien lanza ni en ~/.strands.
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
    session_manager = None                      # linea base: sin memoria entre procesos
elif "--sqlite" in sys.argv:
    session_manager = SqliteSessionManager(SESSION_ID, db_path=os.path.join(HERE, "sessions.db"))
else:
    session_manager = FileSessionManager(SESSION_ID, storage_dir=os.path.join(HERE, "sessions"))

# El agente: identico al de 01 salvo por el parametro session_manager (y por no tener tools).
agent = Agent(
    model=OpenAIResponsesModel(model_id=MODEL_ID),
    system_prompt=SYSTEM_PROMPT,
    session_manager=session_manager,
)

if __name__ == "__main__":
    print("\nMnemo: I remember what you told me in an earlier run. Type 'exit' to quit.\n")
    print(f"Using LLM model: {MODEL_ID}")
    store = "none" if session_manager is None else type(session_manager).__name__
    # Los mensajes ya restaurados ANTES del primer turno: la prueba de que la memoria se cargo.
    print(f"Session '{SESSION_ID}' | store: {store} | restored messages: {len(agent.messages)}")

    while True:
        user_input = input("\nYou > ")
        if user_input.lower() == "exit":
            break
        response = agent(user_input)
        print(f"\nMnemo > {response}")
