import os
from dotenv import load_dotenv
from strands import Agent
from strands.models.openai_responses import OpenAIResponsesModel
from strands.multiagent import GraphBuilder
# Lee el .env local: la clave (que toma el cliente de openai) y el modelo.
load_dotenv()
MODEL_ID = os.getenv("MODEL_ID", "gpt-5.4-nano")

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

RESPONDER_PROMPT = """You are Support, and you write the only message the customer will read. You get
the original ticket and the notes of whoever looked at it. Merge those notes into one answer: never
contradict them, never add a fact they did not give you, and never mention that specialists exist.
At most 80 words, in the ticket's language."""

# Un agente sin herramientas y sin salida en streaming: solo texto a texto, igual que en 05.
def desk(system_prompt: str) -> Agent:
    return Agent(model=OpenAIResponsesModel(model_id=MODEL_ID),
                 system_prompt=system_prompt, callback_handler=None)

# Los cinco nodos. El dict solo sirve para construirlos y resetearlos: no despacha nada.
AGENTS = {"triage": desk(TRIAGE_PROMPT), "logs": desk(LOGS_PROMPT), "impact": desk(IMPACT_PROMPT),
          "business": desk(BUSINESS_PROMPT), "responder": desk(RESPONDER_PROMPT)}

# Una condicion es una funcion Python que lee el resultado de otro nodo. Aqui vive el criterio
# de enrutado: no es un esquema validado como el Route de 05, es este 'in'.
def is_technical(state) -> bool:
    return "TECHNICAL" in str(state.results["triage"].result).upper()

# La rama complementaria. Nadie cierra el conjunto de destinos por ti: si las dos condiciones
# pudieran fallar a la vez, el grafo terminaria sin ejecutar 'responder'.
def is_business(state) -> bool:
    return not is_technical(state)

# La arquitectura entera: cinco nodos y seis aristas, declarados antes de que corra nada.
builder = GraphBuilder()
for node_id, agent in AGENTS.items():
    builder.add_node(agent, node_id)
builder.add_edge("triage", "logs", condition=is_technical)      # rama tecnica: dos nodos
builder.add_edge("triage", "impact", condition=is_technical)    # que corren EN PARALELO
builder.add_edge("triage", "business", condition=is_business)   # rama de negocio: uno solo
builder.add_edge("logs", "responder")
builder.add_edge("impact", "responder")
builder.add_edge("business", "responder")
builder.set_entry_point("triage")
# GraphBuilder no comprueba que el grafo sea aciclico: si lo fuera, correria hasta este tope.
# Sin esta linea, build() avisa por consola en cada arranque.
builder.set_max_node_executions(len(AGENTS))
graph = builder.build()

def run_ticket(ticket: str) -> str:
    """Un solo turno. Quien recorre el grafo es el Graph, no una linea de este archivo."""
    # Igual que en 03-06: cada corrida es independiente. El Graph resetea su propio estado,
    # pero los historiales de los agentes son suyos y sobreviven a la invocacion.
    for agent in AGENTS.values():
        agent.messages.clear()

    result = graph(ticket)
    # La prueba de que rama corrio la da el propio primitivo, no un print nuestro.
    print(f"\n[graph] {' ──► '.join(n.node_id for n in result.execution_order)}")

    # str(result) concatenaria los CINCO nodos con su id delante: la respuesta al cliente
    # es la de un nodo concreto.
    answer = str(result.results["responder"])
    print(answer.strip())
    return answer

if __name__ == "__main__":
    print("\nSupportGraph: Describe your issue. Type 'exit' to quit.\n")
    print(f"Using LLM model: {MODEL_ID}")

    while True:
        user_input = input("\nTicket > ")
        if user_input.lower() == "exit":
            break
        run_ticket(user_input)
