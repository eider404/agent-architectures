import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from google.adk.runners import InMemoryRunner
from google.adk.tools.mcp_tool import McpToolset, StdioConnectionParams
from google.genai import types
from mcp import StdioServerParameters
# Lee el .env local: la clave (que toma LiteLLM) y el modelo.
load_dotenv()
MODEL_ID = os.getenv("MODEL_ID", "gpt-6-luna")

# Ruta absoluta: npx resuelve las relativas contra su propio cwd, no contra el del script.
SANDBOX = str(Path(__file__).parent / "sandbox")
FS_SERVER = "@modelcontextprotocol/server-filesystem@2026.8.31"
# El servidor expone 14 tools; solo dejamos pasar estas 5. Las de escritura
# (write_file, edit_file, move_file, create_directory) nunca llegan al agente.
READ_ONLY = ["read_text_file", "list_directory", "directory_tree", "search_files", "get_file_info"]

SYSTEM_PROMPT = f"""You are FileBot, an assistant that explores a local directory.

The directory you may explore is: {SANDBOX}
Always pass absolute paths to the tools, starting from that directory.

Every fact you state about a file must come from a tool call. Never guess a file's
name, path or contents, and never answer from memory.

When you don't know the layout, call list_directory or directory_tree first, then
read what you need with read_text_file.

search_files matches file and directory NAMES with glob patterns such as "**/*.json".
It does not search inside file contents.

You have read-only access. If the user asks you to create, edit, move or delete
anything, say that you only have read tools."""

# El toolset MCP: lanza el servidor oficial de filesystem como subproceso stdio.
# El timeout por defecto (5 s) no alcanza para la primera descarga de npx.
fs_toolset = McpToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(command="npx", args=["-y", FS_SERVER, SANDBOX]),
        timeout=60,
    ),
    tool_filter=READ_ONLY,
)

# El agente recibe el toolset entero: ADK le pide las tools al servidor cuando las necesita.
agent = LlmAgent(
    name="FileBot",
    model=LiteLlm(model=f"openai/responses/{MODEL_ID}"),
    instruction=SYSTEM_PROMPT,
    tools=[fs_toolset],
)

async def main():
    print("\nFileBot: Ask me about the files in the sandbox! Type 'exit' to quit.\n")
    print(f"Using LLM model: {MODEL_ID}")
    runner = InMemoryRunner(agent=agent, app_name="filebot")
    session = await runner.session_service.create_session(app_name="filebot", user_id="user")

    try:
        # Pedirlas aqui arranca el servidor ya y muestra lo que paso el filtro.
        print(f"MCP tools: {[t.name for t in await fs_toolset.get_tools()]}")
        while True:
            user_input = input("\nYou > ")
            if user_input.lower() == "exit":
                break
            message = types.Content(role="user", parts=[types.Part(text=user_input)])
            async for event in runner.run_async(user_id="user", session_id=session.id, new_message=message):
                for call in event.get_function_calls():
                    print(f"Tool: {call.name}")
                if event.is_final_response() and event.content and event.content.parts:
                    text = "".join(part.text for part in event.content.parts if part.text and not part.thought)
                    print(f"\nFileBot > {text}")
    finally:
        # Cierra la sesion MCP y el subproceso del servidor.
        await fs_toolset.close()

if __name__ == "__main__":
    asyncio.run(main())
