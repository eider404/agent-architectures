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

# Una etapa es un agente sin herramientas: solo texto a texto.
def stage(name: str, instruction: str) -> LlmAgent:
    return LlmAgent(name=name, model=LiteLlm(model=f"openai/responses/{MODEL_ID}"),
                    instruction=instruction)

# Los tres agentes del pipeline. Cada uno tiene su propio prompt.
research_agent = stage("Researcher", RESEARCH_PROMPT)
outline_agent = stage("Outliner", OUTLINE_PROMPT)
draft_agent = stage("Writer", DRAFT_PROMPT)

async def ask(agent: LlmAgent, text: str) -> str:
    """Un turno en una sesion nueva y devuelve el texto final del agente."""
    # El historial vive en la sesion. Al estrenar una en cada llamada, la segunda corrida
    # no arrastra el tema de la primera: cada etapa es de un solo turno.
    runner = InMemoryRunner(agent=agent, app_name="pipeline")
    session = await runner.session_service.create_session(app_name="pipeline", user_id="user")
    message = types.Content(role="user", parts=[types.Part(text=text)])
    reply = ""
    async for event in runner.run_async(user_id="user", session_id=session.id, new_message=message):
        if event.is_final_response() and event.content and event.content.parts:
            reply = "".join(part.text for part in event.content.parts if part.text and not part.thought)
    return reply

async def run_pipeline(topic: str) -> str:
    """Encadena las tres etapas: la salida de cada agente es la entrada del siguiente."""
    print("\n[1/3] research ──►")
    notes = await ask(research_agent, topic)
    print(notes.strip())

    print("\n[2/3] outline ──►")
    outline = await ask(outline_agent, notes)
    print(outline.strip())

    print("\n[3/3] draft ──►")
    draft = await ask(draft_agent, outline)
    print(draft.strip())
    return draft

async def main():
    print("\nWritingPipeline: Give me a topic. Type 'exit' to quit.\n")
    print(f"Using LLM model: {MODEL_ID}")

    while True:
        user_input = input("\nTopic > ")
        if user_input.lower() == "exit":
            break
        await run_pipeline(user_input)

if __name__ == "__main__":
    asyncio.run(main())
