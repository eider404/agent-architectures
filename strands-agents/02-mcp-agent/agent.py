import os
from pathlib import Path
from dotenv import load_dotenv
from mcp import StdioServerParameters, stdio_client
from strands import Agent
from strands.models.openai_responses import OpenAIResponsesModel
from strands.tools.mcp import MCPClient
# Lee el .env local: la clave (que toma el cliente de openai) y el modelo.
load_dotenv()
MODEL_ID = os.getenv("MODEL_ID", "gpt-5.4-nano")

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

# El cliente MCP: lanza el servidor oficial de filesystem como subproceso stdio.
fs_client = MCPClient(lambda: stdio_client(StdioServerParameters(
    command="npx", args=["-y", FS_SERVER, SANDBOX],
)))

if __name__ == "__main__":
    print("\nFileBot: Ask me about the files in the sandbox! Type 'exit' to quit.\n")
    print(f"Using LLM model: {MODEL_ID}")

    # Todo vive dentro del with: al salir se cierra la sesion MCP y las tools
    # dejan de funcionar. Por eso el agente se construye aqui dentro, no fuera.
    with fs_client:
        tools = fs_client.list_tools_sync(tool_filters={"allowed": READ_ONLY})
        print(f"MCP tools: {[t.tool_spec['name'] for t in tools]}")
        agent = Agent(
            model=OpenAIResponsesModel(model_id=MODEL_ID),
            system_prompt=SYSTEM_PROMPT,
            tools=tools,
        )

        while True:
            user_input = input("\nYou > ")
            if user_input.lower() == "exit":
                break
            response = agent(user_input)
            print(f"\nFileBot > {response}")
