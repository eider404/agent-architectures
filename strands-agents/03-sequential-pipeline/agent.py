import os
from dotenv import load_dotenv
from strands import Agent
from strands.models.openai_responses import OpenAIResponsesModel
# Lee el .env local: la clave (que toma el cliente de openai) y el modelo.
load_dotenv()
MODEL_ID = os.getenv("MODEL_ID", "gpt-5.4-nano")

RESEARCH_PROMPT = """You are Researcher, the first stage of a writing pipeline.

You receive a topic and produce raw material for the stages that come after you.

Write 5 to 7 short bullet points: key facts, tensions and concrete examples about the
topic. No introduction, no conclusion, no headings — only the bullets.

You have no tools and no web access. Work from your own knowledge, and when you are
not sure of a figure or a date, describe it qualitatively instead of inventing a
precise number.
Answer in the language of the topic you receive."""

OUTLINE_PROMPT = """You are Outliner, the second stage of a writing pipeline.

Your input is a list of research bullets, not a request from a user. Never answer it,
comment on it, or add facts of your own. Your only job is to give it a shape.

Produce exactly three numbered sections. Each line is a section title of at most six
words, then a dash, then the bullets that section will cover.

Output only those three lines.
Answer in the language of the bullets you receive."""

DRAFT_PROMPT = """You are Writer, the third and last stage of a writing pipeline.

Your input is a three-section outline. Each line is a title, then a dash, then bullets.
Follow it exactly: three headings, in order, each the title before its dash, word for word.

Under each heading write one paragraph of at most 60 words that turns its bullets into
prose. Never copy the bullets as they are. No new sections, no introduction, no conclusion.
Answer in the language of the outline you receive."""

# Una etapa es un agente sin herramientas y sin salida en streaming: solo texto a texto.
def stage(system_prompt: str) -> Agent:
    return Agent(model=OpenAIResponsesModel(model_id=MODEL_ID),
                 system_prompt=system_prompt, callback_handler=None)

# Los tres agentes del pipeline. Cada uno tiene su propio prompt y su propio historial.
research_agent = stage(RESEARCH_PROMPT)
outline_agent = stage(OUTLINE_PROMPT)
draft_agent = stage(DRAFT_PROMPT)

def run_pipeline(topic: str) -> str:
    """Encadena las tres etapas: la salida de cada agente es la entrada del siguiente."""
    # Los agentes son constantes de modulo y acumulan historial. Sin este reset, la
    # segunda corrida arrastraria el tema de la primera: cada etapa es de un solo turno.
    for agent in (research_agent, outline_agent, draft_agent):
        agent.messages.clear()

    print("\n[1/3] research ──►")
    notes = str(research_agent(topic))
    print(notes.strip())

    print("\n[2/3] outline ──►")
    outline = str(outline_agent(notes))
    print(outline.strip())

    print("\n[3/3] draft ──►")
    draft = str(draft_agent(outline))
    print(draft.strip())
    return draft

if __name__ == "__main__":
    print("\nWritingPipeline: Give me a topic. Type 'exit' to quit.\n")
    print(f"Using LLM model: {MODEL_ID}")

    while True:
        user_input = input("\nTopic > ")
        if user_input.lower() == "exit":
            break
        run_pipeline(user_input)
