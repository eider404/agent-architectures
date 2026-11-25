import asyncio
import os
from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from google.adk.runners import InMemoryRunner
from google.genai import types
# Lee el .env local: la clave (que toma LiteLLM) y el modelo.
load_dotenv()
MODEL_ID = os.getenv("MODEL_ID", "gpt-6-luna")

SYSTEM_PROMPT = """You are UnitBot, a unit conversion assistant.

Always use the convert_units tool to perform a conversion. Never compute a
conversion yourself, even when you know the answer.

If convert_units reports an unknown unit, call list_units and tell the user
what you can convert instead.

Answer general questions about units directly, without calling any tool."""
# Factores hacia la unidad base de cada categoria (metro y kilogramo).
LENGTH = {"m": 1.0, "km": 1000.0, "cm": 0.01, "mm": 0.001,
          "mi": 1609.344, "ft": 0.3048, "in": 0.0254, "yd": 0.9144}
MASS = {"kg": 1.0, "g": 0.001, "mg": 1e-6, "lb": 0.45359237, "oz": 0.028349523125}
# La temperatura es un caso aparte: tiene desplazamiento de origen, no solo factor.
TO_CELSIUS = {"c": lambda v: v, "f": lambda v: (v - 32) / 1.8, "k": lambda v: v - 273.15}
FROM_CELSIUS = {"c": lambda v: v, "f": lambda v: v * 1.8 + 32, "k": lambda v: v + 273.15}
CATEGORIES = {"length": LENGTH, "mass": MASS, "temperature": TO_CELSIUS}
# Resuelve a que categoria pertenece una unidad (o None si no esta en el catalogo).
def _category(unit: str):
    return next((name for name, units in CATEGORIES.items() if unit in units), None)

# En ADK una herramienta es una funcion normal: no hace falta decorador.
def convert_units(value: float, from_unit: str, to_unit: str) -> str:
    """Convert a value between two units of the same category.

    Args:
        value: The numeric quantity to convert.
        from_unit: Source unit symbol, e.g. "km", "lb", "c".
        to_unit: Target unit symbol, e.g. "mi", "kg", "f".

    Returns:
        The converted value with its unit, or an error message if a unit
        is unknown or the two units belong to different categories.
    """
    src, dst = from_unit.lower(), to_unit.lower()
    src_cat, dst_cat = _category(src), _category(dst)
    # Los errores se devuelven como texto: el modelo los lee y se corrige en el mismo turno.
    if src_cat is None:
        return f"Unknown unit: '{src}'. Call list_units to see supported units."
    if dst_cat is None:
        return f"Unknown unit: '{dst}'. Call list_units to see supported units."
    if src_cat != dst_cat:
        return f"Cannot convert {src} ({src_cat}) to {dst} ({dst_cat})."
    if src_cat == "temperature":
        result = FROM_CELSIUS[dst](TO_CELSIUS[src](value))
    else:
        factors = CATEGORIES[src_cat]
        result = value * factors[src] / factors[dst]
    return f"{round(result, 4)} {dst}"

def list_units() -> str:
    """List every unit this agent can convert, grouped by category."""
    return "\n".join(f"{name}: {', '.join(units)}" for name, units in CATEGORIES.items())

# El agente: modelo + prompt + las dos funciones. LiteLlm conecta ADK con la Responses API de OpenAI.
agent = LlmAgent(
    name="UnitBot",
    model=LiteLlm(model=f"openai/responses/{MODEL_ID}"),
    instruction=SYSTEM_PROMPT,
    tools=[convert_units, list_units],
)

async def main():
    print("\nUnitBot: Ask me to convert units! Type 'exit' to quit.\n")
    print(f"Using LLM model: {MODEL_ID}")
    # El Runner ejecuta el agente; la sesion en memoria guarda el historial de la conversacion.
    runner = InMemoryRunner(agent=agent, app_name="unitbot")
    session = await runner.session_service.create_session(app_name="unitbot", user_id="user")

    # Bucle interactivo: el SDK decide solo cuando llamar a cada herramienta.
    while True:
        user_input = input("\nYou > ")
        if user_input.lower() == "exit":
            break
        message = types.Content(role="user", parts=[types.Part(text=user_input)])
        # Cada turno es un flujo de eventos: llamadas a herramientas, sus resultados y la respuesta.
        async for event in runner.run_async(user_id="user", session_id=session.id, new_message=message):
            for call in event.get_function_calls():
                print(f"Tool: {call.name}")
            if event.is_final_response() and event.content and event.content.parts:
                text = "".join(part.text for part in event.content.parts if part.text and not part.thought)
                print(f"\nUnitBot > {text}")

if __name__ == "__main__":
    asyncio.run(main())
