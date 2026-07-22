import os
from datetime import datetime, timezone
from typing import Any, Dict

from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.graph import END, START, StateGraph
from psycopg_pool import ConnectionPool

from app.agents.company import company_agent_node
from app.agents.editor import editor_agent_node
from app.agents.macro import macro_agent_node
from app.agents.quant import quant_agent_node
from app.agents.risk import risk_agent_node
from app.graph.state import AgentState

# 1. Fetch environment connection target
raw_conn_string = os.getenv(
    "DATABASE_URL",
    "postgresql://finagent:finagent_secure_pass@localhost:5432/finagent",
)

# 2. Format connection string for compatibility
clean_uri = raw_conn_string.replace("postgresql+asyncpg://", "postgresql://")

try:
    prefix_and_creds, remaining = clean_uri.split("@")
    host_and_port = remaining.split("/")[0]
    host_address = host_and_port.split(":")[0]
    DB_CONN_STRING = f"{prefix_and_creds}@{host_address}:5433/finagent_graph"
except Exception:
    DB_CONN_STRING = "postgresql://finagent:finagent_secure_pass@localhost:5433/finagent_graph"

# 3. Configure ConnectionPool with autocommit enabled
# This allows DDL schemas and concurrent index structures to deploy safely
import atexit as _atexit

pool = ConnectionPool(
    conninfo=DB_CONN_STRING,
    max_size=10,
    min_size=2,
    timeout=5.0,
    kwargs={"autocommit": True},  # <-- Add this right here!
    open=False,
)
pool.open(wait=True, timeout=5.0)


def _shutdown_pool():
    try:
        pool.close()
    except Exception:
        pass


_atexit.register(_shutdown_pool)


def create_financial_agent_graph():
    """Builds the 5-node StateGraph: macro/company/quant fan-into risk, then editor."""
    graph = StateGraph(AgentState)
    graph.add_node("macro", macro_agent_node)
    graph.add_node("company", company_agent_node)
    graph.add_node("quant", quant_agent_node)
    graph.add_node("risk", risk_agent_node)
    graph.add_node("editor", editor_agent_node)

    graph.add_edge(START, "macro")
    graph.add_edge(START, "company")
    graph.add_edge(START, "quant")
    graph.add_edge("macro", "risk")
    graph.add_edge("company", "risk")
    graph.add_edge("quant", "risk")
    graph.add_edge("risk", "editor")
    graph.add_edge("editor", END)

    return graph.compile()


def run_financial_pipeline(initial_state: AgentState) -> Dict[str, Any]:
    """
    Executes the multi-agent StateGraph with structural Postgres checkpointing
    and passes operational business metadata tags directly down to LangSmith.
    """
    print("[*] Connecting to Postgres Graph Database on Port 5433...")
    checkpointer = PostgresSaver(pool)
    checkpointer.setup()
    print("[OK] Database Checkpointer ready.")

    print("[*] Initializing Agent Graph Topology...")
    graph = create_financial_agent_graph()

    manager_id = initial_state.get("manager_id")
    company = initial_state.get("company_ticker")
    pipeline_run_id = initial_state.get("pipeline_run_id")
    morning_note_id = initial_state.get("morning_note_id")
    date_stamp = datetime.now(timezone.utc).date().isoformat()

    config = {
        "configurable": {
            "thread_id": f"{pipeline_run_id}_{company}",
            "recursion_limit": 15,
        },
        "metadata": {
            "manager_id": manager_id,
            "company": company,
            "date": date_stamp,
            "pipeline_run_id": pipeline_run_id,
            "morning_note_id": morning_note_id,
        },
        "tags": [f"manager:{manager_id}", f"ticker:{company}", f"run:{pipeline_run_id}"],
    }

    print(f"[START] Invoking LangGraph runtime thread: {pipeline_run_id}_{company}...")
    graph.checkpointer = checkpointer
    final_state = graph.invoke(initial_state, config=config)

    _shutdown_pool()
    return final_state
