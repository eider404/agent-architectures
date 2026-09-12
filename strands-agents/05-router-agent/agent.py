import os
from enum import Enum
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from strands import Agent
from strands.models.openai_responses import OpenAIResponsesModel
# Lee el .env local: la clave (que toma el cliente de openai) y el modelo.
load_dotenv()
MODEL_ID = os.getenv("MODEL_ID", "gpt-5.4-nano")

# Las cuatro ramas. El modelo no puede inventarse una quinta: el enum cierra el conjunto.
class Category(str, Enum):
    BILLING = "billing"
    TECHNICAL = "technical"
    SALES = "sales"
    OTHER = "other"

# La decision del router. Estas descripciones SON el criterio de clasificacion:
# el SDK convierte este modelo en una tool y el LLM lee sus descripciones, no un prompt.
class Route(BaseModel):
    category: Category = Field(description=(
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

# Un agente sin herramientas y sin salida en streaming: solo texto a texto.
def desk(system_prompt: str) -> Agent:
    return Agent(model=OpenAIResponsesModel(model_id=MODEL_ID),
                 system_prompt=system_prompt, callback_handler=None)

classifier = desk(CLASSIFIER_PROMPT)
# El despacho es este dict: una entrada por valor del enum, sin if/elif y sin rama por defecto.
SPECIALISTS = {Category.BILLING: desk(BILLING_PROMPT), Category.TECHNICAL: desk(TECHNICAL_PROMPT),
               Category.SALES: desk(SALES_PROMPT), Category.OTHER: desk(OTHER_PROMPT)}

def run_router(request: str) -> str:
    """Clasifica con salida estructurada y despacha a UN especialista. Dos llamadas al modelo."""
    # Los agentes son constantes de modulo y acumulan historial. Sin este reset, la
    # segunda corrida arrastraria la peticion de la primera: cada turno es independiente.
    for agent in (classifier, *SPECIALISTS.values()):
        agent.messages.clear()

    # La unica llamada del ejemplo que no devuelve texto: devuelve un Route validado.
    route = classifier(request, structured_output_model=Route).structured_output
    print(f"\n[router] {route.category.value} ──► {route.reason}")

    # El despacho: una busqueda en un dict. Las otras tres ramas no se ejecutan.
    answer = str(SPECIALISTS[route.category](request))
    print(answer.strip())
    return answer

if __name__ == "__main__":
    print("\nSupportRouter: Describe your issue. Type 'exit' to quit.\n")
    print(f"Using LLM model: {MODEL_ID}")

    while True:
        user_input = input("\nRequest > ")
        if user_input.lower() == "exit":
            break
        run_router(user_input)
