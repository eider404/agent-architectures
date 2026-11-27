import asyncio
import os
from typing import Literal
from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from google.adk.runners import InMemoryRunner
from google.genai import types
from pydantic import BaseModel, Field
# Lee el .env local: la clave (que toma LiteLLM) y el modelo.
load_dotenv()
MODEL_ID = os.getenv("MODEL_ID", "gpt-6-luna")

# La decision del router. El Literal cierra el conjunto: el modelo no puede inventarse una
# quinta rama. La descripcion ES el criterio de clasificacion: viaja en el esquema JSON.
# Es un Literal y no un Enum porque con un Enum ADK descarta esa descripcion.
class Route(BaseModel):
    category: Literal["billing", "technical", "sales", "other"] = Field(description=(
        "billing: invoices, charges, refunds, payment methods. "
        "technical: errors, crashes, outages, how something works. "
        "sales: prices, plans, upgrades, trials, quotes. "
        "other: anything that fits none of the three above."))
    reason: str = Field(description="Why this branch, at most 12 words, in the language of the request.")

CLASSIFIER_PROMPT = """You are Triage, the front desk of a support team.

Read the incoming request and route it to exactly one specialist. Never answer it yourself:
the specialist you choose will. Judge what the user needs, not the words they used."""

BILLING_PROMPT = """You are Billing, a support specialist. You only handle invoices, charges,
refunds and payment methods. You have no tools and no access to any account, so explain what
you would check and what you need from the user. Answer in at most 60 words, in their language."""

TECHNICAL_PROMPT = """You are Technical, a support specialist. You only handle errors, crashes,
outages and how the product works. You have no tools and no access to any system, so explain what
you would check and what you need from the user. Answer in at most 60 words, in their language."""

SALES_PROMPT = """You are Sales, a support specialist. You only handle prices, plans, upgrades,
trials and quotes. You have no tools and no access to any price list, so never invent a figure:
say what it depends on and what you need. Answer in at most 60 words, in their language."""

OTHER_PROMPT = """You are Front Desk. This request reached you because it fits no specialist.
Say so plainly, in one sentence, and ask the single question that would let you route it.
At most 40 words, in the user's language. Never guess the answer yourself."""

# Un agente sin herramientas. Con output_schema su respuesta es JSON con esa forma.
def desk(name: str, instruction: str, output_schema: type[BaseModel] | None = None) -> LlmAgent:
    return LlmAgent(name=name, model=LiteLlm(model=f"openai/responses/{MODEL_ID}"),
                    instruction=instruction, output_schema=output_schema)

classifier = desk("Triage", CLASSIFIER_PROMPT, Route)
# El despacho es este dict: una entrada por categoria, sin if/elif y sin rama por defecto.
SPECIALISTS = {"billing": desk("Billing", BILLING_PROMPT), "technical": desk("Technical", TECHNICAL_PROMPT),
               "sales": desk("Sales", SALES_PROMPT), "other": desk("FrontDesk", OTHER_PROMPT)}

async def ask(agent: LlmAgent, text: str) -> str:
    """Un turno en una sesion nueva y devuelve el texto final del agente."""
    # Sesion nueva en cada llamada: cada turno es independiente del anterior.
    runner = InMemoryRunner(agent=agent, app_name="router")
    session = await runner.session_service.create_session(app_name="router", user_id="user")
    message = types.Content(role="user", parts=[types.Part(text=text)])
    reply = ""
    async for event in runner.run_async(user_id="user", session_id=session.id, new_message=message):
        if event.is_final_response() and event.content and event.content.parts:
            reply = "".join(part.text for part in event.content.parts if part.text and not part.thought)
    return reply

async def run_router(request: str) -> str:
    """Clasifica con salida estructurada y despacha a UN especialista. Dos llamadas al modelo."""
    # La unica llamada del ejemplo cuyo texto es JSON: Pydantic lo valida y lo convierte en Route.
    route = Route.model_validate_json(await ask(classifier, request))
    print(f"\n[router] {route.category} ──► {route.reason}")

    # El despacho: una busqueda en un dict. Las otras tres ramas no se ejecutan.
    answer = await ask(SPECIALISTS[route.category], request)
    print(answer.strip())
    return answer

async def main():
    print("\nSupportRouter: Describe your issue. Type 'exit' to quit.\n")
    print(f"Using LLM model: {MODEL_ID}")

    while True:
        user_input = input("\nRequest > ")
        if user_input.lower() == "exit":
            break
        await run_router(user_input)

if __name__ == "__main__":
    asyncio.run(main())
