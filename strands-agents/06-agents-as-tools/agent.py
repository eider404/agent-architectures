import os
from dotenv import load_dotenv
from strands import Agent, tool
from strands.models.openai_responses import OpenAIResponsesModel
# Lee el .env local: la clave (que toma el cliente de openai) y el modelo.
load_dotenv()
MODEL_ID = os.getenv("MODEL_ID", "gpt-6-luna")

# Datos de demo arbitrarios: ningun modelo puede adivinar estos codigos ni estos precios.
# Si aparecen en la respuesta final, la herramienta del especialista corrio de verdad.
FLIGHTS = {"lisbon": "IB-4417 - 08:05-09:25 - 412 EUR",
           "porto": "TP-8642 - 11:40-13:05 - 191 EUR",
           "oslo": "SK-7743 - 07:15-11:00 - 358 EUR"}
HOTELS = {"lisbon": "Casa Kraken, Alfama - 94 EUR/night",
          "porto": "Pensao Vela Roja, Ribeira - 77 EUR/night",
          "oslo": "Hotell Nordlys, Grunerlokka - 132 EUR/night"}

@tool
def search_flights(city: str) -> str:
    """Look up the flight this agency sells to a destination city.

    Args:
        city: Destination city, in English: translate it first, e.g. "Oporto" is "Porto".
    """
    return FLIGHTS.get(city.strip().lower(), f"Unknown city: '{city}'. On sale: {', '.join(FLIGHTS)}.")

@tool
def search_hotels(city: str) -> str:
    """Look up the hotel this agency sells in a destination city.

    Args:
        city: Destination city, in English: translate it first, e.g. "Oporto" is "Porto".
    """
    return HOTELS.get(city.strip().lower(), f"Unknown city: '{city}'. On sale: {', '.join(HOTELS)}.")

ORCHESTRATOR_PROMPT = """You are TripDesk, a travel planner. You look nothing up yourself: you have
two specialists and you reach them through your tools. Call flights_agent for getting there and
hotels_agent for staying there - both when the request needs both, neither when the question is
about travelling in general, which you answer yourself in one sentence.

Then write the plan: one short paragraph per specialist you called, keeping every flight code,
hotel name and price exactly as it came back. Answer in the user's language."""

FLIGHTS_PROMPT = """You are FlightDesk, a flight specialist. Always call search_flights: never name
a flight, a time or a price from your own knowledge. Report what it returned in at most 40 words,
in the language of the request."""

HOTELS_PROMPT = """You are HotelDesk, a hotel specialist. Always call search_hotels: never name
a hotel, an area or a price from your own knowledge. Report what it returned in at most 40 words,
in the language of the request."""

# Un especialista es un agente con su prompt y sus herramientas, sin salida en streaming.
def specialist(system_prompt: str, tools: list) -> Agent:
    return Agent(model=OpenAIResponsesModel(model_id=MODEL_ID), system_prompt=system_prompt,
                 tools=tools, callback_handler=None)

flights = specialist(FLIGHTS_PROMPT, [search_flights])
hotels = specialist(HOTELS_PROMPT, [search_hotels])

# Envolver un agente en @tool es esto: una funcion que lo llama y devuelve su texto. El docstring
# y los type hints son lo que el orquestador lee para decidir si la llama, igual que en 01.
@tool
def flights_agent(request: str) -> str:
    """Ask the flight specialist how to get to a destination.

    Args:
        request: The trip in one sentence, in the user's language.

    Returns:
        The specialist's answer, with the flight code, times and price.
    """
    print("  [tool] flights_agent ──►")
    return str(flights(request))

@tool
def hotels_agent(request: str) -> str:
    """Ask the hotel specialist where to stay at a destination.

    Args:
        request: The trip in one sentence, in the user's language.

    Returns:
        The specialist's answer, with the hotel name, area and nightly price.
    """
    print("  [tool] hotels_agent ──►")
    return str(hotels(request))

# El orquestador: sus dos herramientas son los dos agentes de arriba, no dos funciones.
orchestrator = Agent(model=OpenAIResponsesModel(model_id=MODEL_ID), system_prompt=ORCHESTRATOR_PROMPT,
                     tools=[flights_agent, hotels_agent], callback_handler=None)

def run_trip(request: str) -> str:
    """Un solo turno. Quien despacha aqui es el modelo, no una linea de Python."""
    # Igual que en 03-05: cada corrida es independiente. Y un especialista que acabe la corrida
    # con el historial vacio es un especialista al que el orquestador no llamo.
    for a in (orchestrator, flights, hotels):
        a.messages.clear()
    plan = str(orchestrator(request))
    print(f"\n{plan.strip()}")
    return plan

if __name__ == "__main__":
    print("\nTripDesk: Tell me about your trip. Type 'exit' to quit.\n")
    print(f"Using LLM model: {MODEL_ID}")

    while True:
        user_input = input("\nTrip > ")
        if user_input.lower() == "exit":
            break
        run_trip(user_input)
