"""Probe for issue #15: does the declared mcp floor actually work?

Builds a clean venv, pins mcp to a version (by default the floor declared in
google-adk/01) and runs the unmodified agent.py against a local fake OpenAI
Responses server. LiteLlm is not replaced. Needs uv (UV=path or on PATH).

    python probe_mcp_floor.py            # declared floor
    python probe_mcp_floor.py 2.0.0      # any other version
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

EXAMPLE = Path(__file__).parent / "google-adk" / "01-basic-tool-agent"
UV = os.getenv("UV") or shutil.which("uv")
PINS = ["google-adk==2.15.1", "litellm==1.106.2"]
REQUESTS = []


class FakeResponses(BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        REQUESTS.append(self.path)
        answered = any(i.get("type") == "function_call_output" for i in body["input"])
        if answered:
            item = {"type": "message", "id": "msg_1", "role": "assistant", "status": "completed",
                    "content": [{"type": "output_text", "annotations": [],
                                 "text": "FAKE: 100 km is 62.1371 miles."}]}
        else:
            item = {"type": "function_call", "id": "fc_1", "call_id": "call_1", "status": "completed",
                    "name": "convert_units",
                    "arguments": json.dumps({"value": 100, "from_unit": "km", "to_unit": "mi"})}
        data = json.dumps({
            "id": f"resp_{len(REQUESTS)}", "object": "response", "created_at": 1, "status": "completed",
            "model": body["model"], "output": [item], "parallel_tool_calls": True,
            "tool_choice": "auto", "tools": [],
            "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
        }).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


def main():
    declared = re.search(r"^mcp>=([\d.]+)", (EXAMPLE / "requirements.txt").read_text(), re.M)[1]
    version = sys.argv[1] if len(sys.argv) > 1 else declared
    server = ThreadingHTTPServer(("127.0.0.1", 0), FakeResponses)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_port}/v1"

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        venv = Path(tmp) / "venv"
        python = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        subprocess.run([UV, "venv", "-q", "--python", "3.12", str(venv)], check=True)
        subprocess.run([UV, "pip", "install", "-q", "--python", str(python), "-r",
                        str(EXAMPLE / "requirements.txt"), *PINS, f"mcp=={version}"], check=True)
        shutil.copy(EXAMPLE / "agent.py", tmp)
        env = {**os.environ, "OPENAI_API_KEY": "sk-fake", "MODEL_ID": "gpt-6-luna",
               "OPENAI_BASE_URL": base, "OPENAI_API_BASE": base, "PYTHONIOENCODING": "utf-8"}
        run = subprocess.run([str(python), str(Path(tmp) / "agent.py")], cwd=tmp, env=env,
                             input="Convert 100 km to miles\nexit\n", capture_output=True,
                             encoding="utf-8", timeout=180)
    server.shutdown()

    print((run.stdout + run.stderr)[-3000:])
    ok = run.returncode == 0 and "FAKE: 100 km" in run.stdout and len(REQUESTS) == 2
    print(f"mcp {version} (declared floor {declared}) | exit code: {run.returncode} | requests: {REQUESTS}")
    print("PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
