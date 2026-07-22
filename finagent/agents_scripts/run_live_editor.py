import os
import asyncio
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)

from app.graph.state import create_initial_state
from app.agents.macro import macro_agent_node
from app.agents.company import company_agent_node
from app.agents.quant import quant_agent_node
from app.agents.risk import risk_agent_node
from app.agents.editor import editor_agent_node

async def run_live_editor_pipeline():
    print("[INIT] Initializing Live Multi-Agent Pipeline for PETR4...")
    state = create_initial_state(
        pipeline_run_id="live-editor-smoke-test",
        morning_note_id=f"note-{int(datetime.now().timestamp())}",
        manager_id=1,
        company_ticker="PETR4"
    )
    
    # Step 1: Ingest Live Data Feeds
    print("\n[PHASE 1] Ingesting upstream live metrics & analysis...")
    state = macro_agent_node(state)
    state = company_agent_node(state)
    state = quant_agent_node(state)
    
    # Step 2: Extract Adversarial Vulnerabilities
    print("\n[PHASE 2] Auditing risks and data integrity gaps...")
    state = risk_agent_node(state)
    
    # Step 3: Compile Editorial Layout and Typed Allocation
    print("\n[PHASE 3] Executing EditorAgent compilation layer...")
    final_state = editor_agent_node(state)
    
    print("\n[RESULTS] --- LIVE DELIVERABLE RESULTS ---")

    print("\n[SECTION CONFIDENCE SCORES]")
    for section, score in final_state.get("confidence_scores", {}).items():
        status = "[SOLID]" if score >= 0.5 else "[GAP DETECTED]"
        print(f" - {section.upper()}: {score} | {status}")

    print("\n[TYPED INVESTMENT RECOMMENDATION STRUCT]")
    rec = final_state.get("recommendation")
    if rec:
        print(f" - Action: {rec.action}")
        print(f" - Target Portfolio Weight: {rec.target_weight}%")
        print(f" - View Horizon: {rec.horizon_months} Months")
        print(f" - Thesis Summary Bullet: {rec.thesis_summary}")
    else:
        print(" [NONE] No structured recommendation generated.")

    print("\n[GENERATED MORNING NOTE NARRATIVE]")
    print("--------------------------------------------------------------------------------")
    print(final_state.get("morning_note") or "[EMPTY] Morning note is empty/failed.")
    print("--------------------------------------------------------------------------------")

if __name__ == "__main__":
    asyncio.run(run_live_editor_pipeline())