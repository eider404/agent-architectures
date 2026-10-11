# Agent Architecture Examples

12 minimal, self-contained examples of **AI agent architectures**. Each folder shows *one* architecture in a single file (`agent.py`, ~70 lines) and each example changes exactly one thing relative to the previous one, so that the difference is the lesson.

They don't solve real problems: they are meant to be read top to bottom to understand how each pattern is put together.

## The 12 examples

| # | Example | Architecture |
|---|---------|--------------|
| 01 | [`basic-tool-agent`](strands-agents/01-basic-tool-agent) | Agent with its own tools (`@tool`) |
| 02 | [`mcp-agent`](strands-agents/02-mcp-agent) | Tools obtained from an MCP server |
| 03 | [`sequential-pipeline`](strands-agents/03-sequential-pipeline) | Agents chained in a row |
| 04 | [`parallel-fanout`](strands-agents/04-parallel-fanout) | Agents in parallel (fan-out / fan-in) |
| 05 | [`router-agent`](strands-agents/05-router-agent) | Classify and dispatch to a specialist |
| 06 | [`agents-as-tools`](strands-agents/06-agents-as-tools) | Agents used as another agent's tools |
| 07 | [`agent-graph`](strands-agents/07-agent-graph) | Agent graph with conditional branches |
| 08 | [`agent-swarm`](strands-agents/08-agent-swarm) | Autonomous swarm with no orchestrator |
| 09 | [`persistent-session-agent`](strands-agents/09-persistent-session-agent) | Conversation that survives a restart |
| 10 | [`observable-agent`](strands-agents/10-observable-agent) | Tool traces, timings and tokens |
| 11 | [`human-in-the-loop`](strands-agents/11-human-in-the-loop) | Human approval before acting |
| 12 | [`structured-output`](strands-agents/12-structured-output) | Typed output validated with Pydantic |

## How to try it

You need **Python 3.10+** and an [OpenAI API key](https://platform.openai.com/api-keys). AWS is not needed. Example `02` also requires **Node.js ≥ 18**.

```bash
git clone <repo-url>
cd <repo>/strands-agents/01-basic-tool-agent

python -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env              # put your OPENAI_API_KEY in it
.venv/bin/python agent.py         # type 'exit' to quit
```

To try another example, change folder and repeat the same steps: each one has its own `requirements.txt`, `.env.example` and `README.md` with the diagram, a sample conversation and what to try. To use another model for a single run:

```bash
MODEL_ID=gpt-5.4 .venv/bin/python agent.py
```

## Structure

```
strands-agents/
└── NN-name/
    ├── agent.py            # the whole example
    ├── requirements.txt    # direct dependencies
    ├── .env.example        # required variables (no real values)
    └── README.md           # architecture, running and transcript
```

There is no build, no tests and no shared dependencies at the repo level: each folder is installed and run separately.

## Where to start

Read the examples in order. `01` is the base; from `03` to `08` an agent is composed more and more (line, fan, router, hierarchy, graph, swarm); from `09` to `12` persistence, observability, human control and structured output are added.
