import asyncio
import os
from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.events.event import Event
from google.adk.models.lite_llm import LiteLlm
from google.adk.runners import InMemoryRunner
from google.adk.workflow import START, JoinNode, Workflow
from google.genai import types
# Lee el .env local: la clave (que toma LiteLLM) y el modelo.
load_dotenv()
MODEL_ID = os.getenv("MODEL_ID", "gpt-6-luna")

TRIAGE_PROMPT = """You are Triage, the front desk of a support team. Read the ticket and answer with
exactly ONE word and nothing else: TECHNICAL if it is about errors, crashes, outages, data loss or
how the product works; BUSINESS if it is about invoices, charges, refunds, plans or contracts."""

LOGS_PROMPT = """You are LogDesk, the diagnostics half of the technical team. Say which two or three
log lines, error codes or metrics you would pull first, and what each one would tell you. You have no
access to any system: never claim to have read one. At most 50 words, in the ticket's language."""

IMPACT_PROMPT = """You are ImpactDesk, the blast-radius half of the technical team. Say who is
affected, how badly, and how urgent this is. You have no access to any system: never invent user
counts. At most 50 words, in the ticket's language."""

BUSINESS_PROMPT = """You are BizDesk, the business specialist: invoices, charges, refunds, plans and
contracts. You have no access to any account, so say what you would check and what you need from the
customer. At most 50 words, in the ticket's language."""

# {ticket} lo rellena ADK desde el estado de la sesion; las notas le llegan como entrada del nodo.
RESPONDER_PROMPT = """You are Support, and you write the only message the customer will read. You get
the original ticket and the notes of whoever looked at it. Merge those notes into one answer: never
contradict them, never add a fact they did not give you, and never mention that specialists exist.
At most 80 words, in the ticket's language.

Original ticket: {ticket}"""

# Un agente sin herramientas: como nodo de un Workflow solo ve la salida del nodo anterior.
def desk(name: str, instruction: str) -> LlmAgent:
    return LlmAgent(name=name, model=LiteLlm(model=f"openai/responses/{MODEL_ID}"), instruction=instruction)

triage, logs = desk("triage", TRIAGE_PROMPT), desk("logs", LOGS_PROMPT)
impact, business = desk("impact", IMPACT_PROMPT), desk("business", BUSINESS_PROMPT)
responder = desk("responder", RESPONDER_PROMPT)
DESKS = [triage.name, logs.name, impact.name, business.name, responder.name]

# Un nodo funcion lee el veredicto de triage, emite la ruta y reenvia el ticket a la rama elegida.
def route(ctx, node_input: str):
    verdict = "technical" if "TECHNICAL" in node_input.upper() else "business"
    return Event(output=ctx.state["ticket"], route=verdict)

# JoinNode espera a las dos mitades tecnicas y entrega sus salidas juntas, con el nombre de cada una.
join = JoinNode(name="join")

# La arquitectura entera: las aristas, declaradas antes de que corra nada.
graph = Workflow(name="support_graph", edges=[
    (START, triage, route),
    (route, {"technical": (logs, impact),      # rama tecnica: dos nodos EN PARALELO
             "business": business}),           # rama de negocio: uno solo
    ((logs, impact), join, responder),
    (business, responder),
])
runner = InMemoryRunner(node=graph, app_name="support")

async def run_ticket(ticket: str) -> str:
    """Un solo turno. Quien recorre el grafo es el Workflow, no una linea de este archivo."""
    # Una sesion nueva por ticket: cada corrida es independiente.
    session = await runner.session_service.create_session(
        app_name="support", user_id="user", state={"ticket": ticket})
    message = types.Content(role="user", parts=[types.Part(text=ticket)])
    path, answer = [], ""
    async for event in runner.run_async(user_id="user", session_id=session.id, new_message=message):
        if event.author in DESKS and event.content and event.content.parts:
            path.append(event.author)
            if event.author == responder.name:
                answer = "".join(p.text for p in event.content.parts if p.text and not p.thought)
    # La prueba de que rama corrio: el autor de cada evento que emitio el grafo.
    print(f"\n[graph] {' ──► '.join(dict.fromkeys(path))}")
    print(answer.strip())
    return answer

async def main():
    print("\nSupportGraph: Describe your issue. Type 'exit' to quit.\n")
    print(f"Using LLM model: {MODEL_ID}")

    while True:
        user_input = input("\nTicket > ")
        if user_input.lower() == "exit":
            break
        await run_ticket(user_input)

if __name__ == "__main__":
    asyncio.run(main())
