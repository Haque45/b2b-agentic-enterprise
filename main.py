"""
Main Orchestration Engine for B2B Agentic Enterprise.

Coordinates the 6-agent intelligence layer loop communicating statefully via pipeline.db:
1. Triage Agent (Sentiment classification from inbox replies)
2. Analytics Agent (Reply rates & sentiment ratios per service lane)
3. Strategy Agent (CEO decision making & campaign directives)
4. Scout Agent (Web search & lead discovery)
5. Sales Agent (Copywriting & mechatronics founder grounding)
6. PR Guardian Agent (Spam & word count compliance audit)

Usage:
    python main.py --seed           # Seeds pipeline.db with initial historic data
    python main.py --run-once       # Executes 1 complete pipeline pass
    python main.py --loop           # Continuously runs pipeline cycle
    python main.py --status         # Displays current database summary
"""

import os
import sys
import argparse
import time
import json
import sqlite3
from typing import Dict, Any
from dotenv import load_dotenv

# Initialize environment variables at script startup
load_dotenv()

from database import init_db, seed_database, get_db_connection, DEFAULT_DB_PATH
from src.agents import (
    TriageAgent,
    AnalyticsAgent,
    StrategyAgent,
    ScoutAgent,
    SalesAgent,
    PRAgent
)
from src.dispatcher import ResendEmailDispatcher


def print_banner():
    banner = """
====================================================================
           B2B AGENTIC ENTERPRISE - INTELLIGENCE LAYER             
          6-Agent Autonomous DB-Driven Orchestration System         
====================================================================
    """
    print(banner)


def display_db_status(db_path: str = DEFAULT_DB_PATH):
    """Prints a clean summary of current pipeline.db state."""
    init_db(db_path)
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    print("\n[DB STATUS SUMMARY]")

    # Leads by status
    cursor.execute("SELECT status, COUNT(*) as cnt FROM leads GROUP BY status;")
    lead_stats = {row["status"]: row["cnt"] for row in cursor.fetchall()}
    
    # Active Directive
    cursor.execute("SELECT focus_service_lane, allocation_percentage, directive_text FROM campaign_directives WHERE status = 'active' ORDER BY id DESC LIMIT 1;")
    active_dir = cursor.fetchone()

    # Replies Count
    cursor.execute("SELECT sentiment, COUNT(*) as cnt FROM replies GROUP BY sentiment;")
    reply_stats = {row["sentiment"]: row["cnt"] for row in cursor.fetchall()}

    conn.close()

    print(f"Database Path: {db_path}")
    print("Leads Breakdown:")
    for st, count in lead_stats.items():
        print(f"  - {st:<22}: {count} leads")
    if not lead_stats:
        print("  - (No leads in database)")

    print("\nReplies Breakdown:")
    for sent, count in reply_stats.items():
        print(f"  - Sentiment '{sent}': {count} replies")
    if not reply_stats:
        print("  - (No replies recorded)")

    if active_dir:
        print(f"\nActive CEO Directive:")
        print(f"  Focus Lane : {active_dir['focus_service_lane']} ({active_dir['allocation_percentage']}% allocation)")
        print(f"  Directive  : {active_dir['directive_text']}")
    print("====================================================================\n")


def run_pipeline_cycle(db_path: str = DEFAULT_DB_PATH) -> Dict[str, Any]:
    """Executes 1 full pass across all 6 agents in sequence."""
    print_banner()
    init_db(db_path)

    cycle_start = time.time()
    results = {}

    print(">>> STEP 1: Running Triage Agent (Classifying inbox replies)...")
    triage_agent = TriageAgent(db_path=db_path)
    results["triage"] = triage_agent.run()

    print("\n>>> STEP 2: Running Analytics Agent (Computing reply rates & metrics)...")
    analytics_agent = AnalyticsAgent(db_path=db_path)
    results["analytics"] = analytics_agent.run()

    print("\n>>> STEP 3: Running CEO Strategy Agent (Formulating daily focus & directive)...")
    strategy_agent = StrategyAgent(db_path=db_path)
    results["strategy"] = strategy_agent.run(analytics_summary=results["analytics"])

    print("\n>>> STEP 4: Running Scout Agent (Web search for target hardware startups)...")
    scout_agent = ScoutAgent(db_path=db_path)
    results["scout"] = scout_agent.run()

    print("\n>>> STEP 5: Running Sales / Copywriter Agent (Scraping web & drafting grounded pitches)...")
    sales_agent = SalesAgent(db_path=db_path)
    results["sales"] = sales_agent.run()

    print("\n>>> STEP 6: Running PR Guardian Agent (Auditing copy against spam lexicon & word limit)...")
    pr_agent = PRAgent(db_path=db_path)
    results["pr"] = pr_agent.run()

    duration = round(time.time() - cycle_start, 2)
    print(f"\n[PIPELINE CYCLE COMPLETE in {duration}s]")
    display_db_status(db_path)

    return results


def main():
    parser = argparse.ArgumentParser(description="B2B Agentic Enterprise Orchestration Engine")
    parser.add_argument("--seed", action="store_true", help="Seeds database with initial historic leads and replies")
    parser.add_argument("--run-once", action="store_true", help="Executes a single 6-agent pipeline pass")
    parser.add_argument("--dispatch", action="store_true", help="Dispatches approved_for_dispatch leads via Resend API")
    parser.add_argument("--loop", action="store_true", help="Runs pipeline continuously in a loop")
    parser.add_argument("--delay", type=int, default=60, help="Delay in seconds between loop cycles (default: 60s)")
    parser.add_argument("--status", action="store_true", help="Prints database summary status")
    parser.add_argument("--db", type=str, default=DEFAULT_DB_PATH, help="Path to SQLite pipeline.db")

    args = parser.parse_args()

    if args.seed:
        print(f"Seeding database at {args.db}...")
        seed_database(args.db)
        display_db_status(args.db)
        return

    if args.dispatch:
        print(f"Dispatching approved leads via Resend API (db: {args.db})...")
        dispatcher = ResendEmailDispatcher(db_path=args.db)
        res = dispatcher.dispatch_pending_leads()
        display_db_status(args.db)
        return

    if args.status:
        display_db_status(args.db)
        return

    if args.loop:
        print(f"Starting continuous pipeline execution loop (delay: {args.delay}s)... Press Ctrl+C to stop.")
        cycle_num = 1
        try:
            while True:
                print(f"\n--- Starting Pipeline Cycle #{cycle_num} ---")
                run_pipeline_cycle(args.db)
                cycle_num += 1
                time.sleep(args.delay)
        except KeyboardInterrupt:
            print("\nPipeline loop stopped by user.")
            return

    # Default action if no flag passed or --run-once
    run_pipeline_cycle(args.db)


if __name__ == "__main__":
    main()
