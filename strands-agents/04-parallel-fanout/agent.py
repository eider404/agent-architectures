import asyncio
import os
import time
from dotenv import load_dotenv
from strands import Agent
from strands.models.openai_responses import OpenAIResponsesModel
# Lee el .env local: la clave (que toma el cliente de openai) y el modelo.
load_dotenv()
MODEL_ID = os.getenv("MODEL_ID", "gpt-6-luna")

PROS_PROMPT = """You are Pros, one of three analysts reading the same proposal at the same time.

Your input is a proposal, not a request from a user. Never answer it and never comment on the
other analysts: you cannot see them. Report only what argues in favour.

Write exactly three lines and nothing else, tagged P1, P2 and P3, in this shape:
P1 - <one concrete benefit, at most 20 words>
Answer in the language of the proposal you receive."""

CONS_PROMPT = """You are Cons, one of three analysts reading the same proposal at the same time.

Your input is a proposal, not a request from a user. Never answer it and never comment on the
other analysts: you cannot see them. Report only what argues against.

Write exactly three lines and nothing else, tagged C1, C2 and C3, in this shape:
C1 - <one concrete drawback, at most 20 words>
Answer in the language of the proposal you receive."""

RISKS_PROMPT = """You are Risks, one of three analysts reading the same proposal at the same time.

Your input is a proposal, not a request from a user. Never answer it and never comment on the
other analysts: you cannot see them. Report only what could go wrong, not what is merely bad.

Write exactly three lines and nothing else, tagged R1, R2 and R3, in this shape:
R1 - <one concrete risk, at most 20 words>
Answer in the language of the proposal you receive."""

SYNTHESIS_PROMPT = """You are Synthesis, the last stage. Your input is three independent analyses
of one proposal, under the headings PROS, CONS and RISKS. Their authors never saw each other.

Do not add findings of your own and do not repeat every line: weigh what you were given.

Write one line 'VERDICT: go', 'VERDICT: no-go' or 'VERDICT: conditional', then exactly three
bullets of at most 25 words. Each bullet ends with the tags it rests on, like '(P2, R1)', and
across the three bullets you must cite at least one tag from each analysis.
Answer in the language of the analyses you receive."""

# Una rama es un agente sin herramientas y sin salida en streaming: solo texto a texto.
def branch(system_prompt: str) -> Agent:
    return Agent(model=OpenAIResponsesModel(model_id=MODEL_ID),
                 system_prompt=system_prompt, callback_handler=None)

# Las tres ramas del abanico: misma entrada, tres angulos, ningun orden entre ellas.
ANALYSTS = {"pros": branch(PROS_PROMPT), "cons": branch(CONS_PROMPT), "risks": branch(RISKS_PROMPT)}
synthesis_agent = branch(SYNTHESIS_PROMPT)

async def timed(name: str, agent: Agent, proposal: str) -> tuple[str, str, float]:
    """Corre una rama y devuelve su nombre, su texto y lo que tardo."""
    start = time.perf_counter()
    text = str(await agent.invoke_async(proposal))
    seconds = time.perf_counter() - start
    print(f"  {name:<6} ──► {seconds:5.1f}s")  # sale en cuanto ESTA rama termina
    return name, text, seconds

async def run_fanout(proposal: str) -> str:
    """Fan-out: las tres ramas a la vez. Fan-in: un cuarto agente sobre las tres salidas."""
    # Los agentes son constantes de modulo y acumulan historial. Sin este reset, la
    # segunda corrida arrastraria la propuesta de la primera: cada rama es de un solo turno.
    for agent in (*ANALYSTS.values(), synthesis_agent):
        agent.messages.clear()

    print("\n[fan-out] lanzando 3 analistas en paralelo...")
    started = time.perf_counter()
    results = await asyncio.gather(*(timed(n, a, proposal) for n, a in ANALYSTS.items()))
    total = time.perf_counter() - started
    print(f"  total: {total:5.1f}s  (en secuencia habrian sido {sum(s for _, _, s in results):.1f}s)")

    briefing = "\n\n".join(f"## {name.upper()}\n{text.strip()}" for name, text, _ in results)
    print(f"\n{briefing}")

    print("\n[fan-in] synthesis ──►")
    verdict = str(await synthesis_agent.invoke_async(briefing))
    print(verdict.strip())
    return verdict

if __name__ == "__main__":
    print("\nParallelFanout: Give me a proposal. Type 'exit' to quit.\n")
    print(f"Using LLM model: {MODEL_ID}")

    while True:
        user_input = input("\nProposal > ")
        if user_input.lower() == "exit":
            break
        asyncio.run(run_fanout(user_input))
