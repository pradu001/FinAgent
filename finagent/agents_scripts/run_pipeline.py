import os
import sys
import uuid
import time
from datetime import datetime, timezone
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Ensure console can render UTF-8 payloads emitted by upstream LLMs (e.g. \u202f).
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

load_dotenv()

from app.graph.state import create_initial_state
from app.graph.pipeline import run_financial_pipeline

def main():
    print('='*70)
    print("INITIALIZING MULTI-AGENT ANALYSIS PIPELINE: FINAGENT ENGINE")
    print('='*70)

    if not os.getenv("NVIDIA_API_KEY") or not os.getenv("TAVILY_API_KEY"):
        print("Environment keys missing")
        sys.exit(1)

    run_id = f"run-{uuid.uuid4().hex[:8]}"
    note_id = f"note-{uuid.uuid4().hex[:8]}"

    print(f"[*] Correlation Tracking: run_id={run_id} | note_id={note_id}")
    print("[*] Target Analysis Ticker: PETR4")

    state = create_initial_state(
        pipeline_run_id=run_id,
        morning_note_id=note_id,
        manager_id=1,
        company_ticker="PETR4"
    )

    state["data_freshness"]["company"] = datetime.now(timezone.utc).isoformat()

    try:
        print("[*] Launching execution loops across LangGraph topology...")
        
        start_time = time.perf_counter()
        
        final_output = run_financial_pipeline(state)
        
        end_time = time.perf_counter()
        execution_duration = end_time - start_time
        
        print("\n" + "="*50)
        print("DELIVERABLE NARRATIVE REPORT (EDITOR_AGENT CONSOLIDATION)")
        print("="*50)

        if final_output.get("morning_note"):
            print(final_output["morning_note"])
        else:
            print("WARNING: Empty narrative block output emitted.")

        rec = final_output.get("recommendation")
        if rec:
            print("\n" + "-" * 50)
            print("STRUCTURAL METRIC RECOMMENDATION:")
            print(f"   Target Action:       {rec.action}")
            print(f"   Recommended Weight:  {rec.target_weight}%")
            print(f"   Investment Horizon:  {rec.horizon_months} Months")
            print(f"   Thesis Overview:     {rec.thesis_summary}")
            print("-" * 50)

        # Print execution duration regardless of recommendation presence
        print(f"\n⏱️ Pipeline execution completed in: {execution_duration:.2f} seconds")

        # --- DEDUPLICATED FLAG DISPLAY LOGIC ---
        flags = final_output.get("flags", [])
        if flags:
            unique_flags = {}
            for flag in flags:
                flag_msg = getattr(flag, "message", None)
                if not flag_msg and hasattr(flag, "metadata") and isinstance(flag.metadata, dict):
                    flag_msg = flag.metadata.get("error", "Unknown execution error context")
                elif not flag_msg:
                    flag_msg = "Unknown execution error context"
                
                dedup_key = (flag.source, flag.flag_type, flag_msg)
                if dedup_key not in unique_flags:
                    unique_flags[dedup_key] = (flag, flag_msg)

            print(f"\nIncident Data Flags Detected ({len(unique_flags)} unique):")
            for _, (flag, flag_msg) in unique_flags.items():
                print(f"   - Source: {flag.source} | Grade: {flag.flag_type} | Reason: {flag_msg}")
        else:
            print("\nExecution Track Clean: No upstream data anomalies recorded.")

    except Exception as e:
        print(f"\nPipeline integration failure encountered: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
    sys.exit(0)
