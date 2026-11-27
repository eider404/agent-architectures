import asyncio
import os
import sys
from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.apps import App
from google.adk.models.lite_llm import LiteLlm
from google.adk.runners import InMemoryRunner
from google.genai import types
from observability import TracePlugin
# Lee el .env local: la clave (que toma LiteLLM) y el modelo.
load_dotenv()
MODEL_ID = os.getenv("MODEL_ID", "gpt-6-luna")
# El rastro vive junto a este archivo, no en el cwd de quien lanza.
HERE = os.path.dirname(os.path.abspath(__file__))
TRACE_PATH = os.path.join(HERE, "trace.jsonl")

SYSTEM_PROMPT = """You are Concierge, the booking assistant of Hotel Kraken.

Always use the tools to check availability, book a room or cancel a booking.
Never state availability or invent a booking code from your own knowledge.

If a tool reports an error, tell the user plainly what went wrong."""
# El hotel entero cabe en dos diccionarios: lo que persiste aqui es el rastro, no el negocio.
AVAILABILITY = {"2026-10-02": 3, "2026-10-03": 0, "2026-10-04": 7}
BOOKINGS = {"KRAKEN-7743": {"date": "2026-10-04", "guest": "Ada"}}
# Codigos deterministas, no aleatorios: el transcript del README sigue siendo cierto manana.
_NEXT_CODE = iter(["KRAKEN-8801", "KRAKEN-8802", "KRAKEN-8803"])

def check_availability(date: str) -> str:
    """Check how many rooms are free on a date. Returns an error message if the
    date is unknown.

    Args:
        date: The date to check, in YYYY-MM-DD format.
    """
    # Los errores se devuelven como texto: el modelo los lee y se corrige en el mismo turno.
    if date not in AVAILABILITY:
        return f"Unknown date: '{date}'. Try {', '.join(AVAILABILITY)}."
    free = AVAILABILITY[date]
    return f"{free} rooms free on {date}." if free else f"No rooms free on {date}."

def book_room(date: str, guest: str) -> str:
    """Book one room for a guest. Returns the booking code, or an error message
    if the date is unknown or full.

    Args:
        date: The date to book, in YYYY-MM-DD format.
        guest: The name of the guest the room is booked for.
    """
    if date not in AVAILABILITY:
        return f"Unknown date: '{date}'. Try {', '.join(AVAILABILITY)}."
    if AVAILABILITY[date] == 0:
        return f"No rooms free on {date}."
    AVAILABILITY[date] -= 1
    code = next(_NEXT_CODE, "KRAKEN-9999")
    BOOKINGS[code] = {"date": date, "guest": guest}
    return f"Booked for {guest} on {date}. Your code is {code}."

def cancel_booking(code: str) -> str:
    """Cancel an existing booking. Returns an error message if the code does
    not exist.

    Args:
        code: The booking code, e.g. "KRAKEN-7743".
    """
    if code not in BOOKINGS:
        return f"Unknown booking code: '{code}'."
    AVAILABILITY[BOOKINGS.pop(code)["date"]] += 1
    return f"Booking {code} cancelled."

# El segundo eje, bajo flag: ADK ya emite estos spans; esto solo les pone un exportador.
if "--otel" in sys.argv:
    from google.adk.telemetry.setup import OTelHooks, maybe_set_otel_providers
    from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor
    maybe_set_otel_providers([OTelHooks(span_processors=[SimpleSpanProcessor(ConsoleSpanExporter())])])

# El agente: no sabe que lo observan.
agent = LlmAgent(
    name="Concierge",
    model=LiteLlm(model=f"openai/responses/{MODEL_ID}"),
    instruction=SYSTEM_PROMPT,
    tools=[check_availability, book_room, cancel_booking],
)
# El observador se registra en la App, no en el agente: ese es el cambio de este ejemplo.
app = App(name="concierge", root_agent=agent, plugins=[TracePlugin(jsonl_path=TRACE_PATH)])

async def main():
    print("\nConcierge: Hotel Kraken bookings. Type 'exit' to quit.\n")
    print(f"Using LLM model: {MODEL_ID}")
    print(f"Trace: {TRACE_PATH}")
    runner = InMemoryRunner(app=app)
    session = await runner.session_service.create_session(app_name="concierge", user_id="user")

    while True:
        user_input = input("\nYou > ")
        if user_input.lower() == "exit":
            break
        message = types.Content(role="user", parts=[types.Part(text=user_input)])
        async for event in runner.run_async(user_id="user", session_id=session.id, new_message=message):
            if event.is_final_response() and event.content and event.content.parts:
                text = "".join(part.text for part in event.content.parts if part.text and not part.thought)
                print(f"\nConcierge > {text}")

if __name__ == "__main__":
    asyncio.run(main())
