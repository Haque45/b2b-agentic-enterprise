"""
Autonomous Background Scheduler (scheduler.py).

Uses python schedule library to run continuous autonomous cycles:
- Runs Triage Agent every 2 hours (inspecting IMAP B2B_Pipeline folder for replies/bounces)
- Runs Resend Email Dispatcher every 1 hour (sending approved pitches with 60-120s jitter)
- Runs CEO / Scout / Copywriter / PR Guardian Intelligence Cycle every 4 hours

Includes graceful shutdown on KeyboardInterrupt.
"""

import sys
import os
import time
import logging
import schedule
from datetime import datetime

# Load environment variables at startup
from dotenv import load_dotenv
load_dotenv()

from database import init_db, DEFAULT_DB_PATH
from main import run_pipeline_cycle
from src.dispatcher import ResendEmailDispatcher
from src.agents import TriageAgent

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("AutonomousScheduler")


def job_triage():
    """Scheduled job to check IMAP B2B_Pipeline for replies and bounces."""
    logger.info("⏰ [SCHEDULED JOB] Running Triage Agent...")
    try:
        triage = TriageAgent()
        res = triage.run()
        logger.info(f"⏰ [SCHEDULED JOB] Triage complete: {res.get('triaged_count', 0)} replies processed.")
    except Exception as e:
        logger.error(f"❌ [SCHEDULED JOB] Triage Agent error: {e}")


def job_dispatch():
    """Scheduled job to dispatch approved leads via Resend API."""
    logger.info("⏰ [SCHEDULED JOB] Running Resend Email Dispatcher...")
    try:
        dispatcher = ResendEmailDispatcher()
        res = dispatcher.dispatch_pending_leads()
        logger.info(f"⏰ [SCHEDULED JOB] Dispatch complete: {res.get('dispatched_count', 0)} emails sent.")
    except Exception as e:
        logger.error(f"❌ [SCHEDULED JOB] Dispatcher error: {e}")


def job_intelligence_cycle():
    """Scheduled job to run full 6-agent intelligence pipeline cycle."""
    logger.info("⏰ [SCHEDULED JOB] Running 6-Agent Intelligence Pipeline Cycle...")
    try:
        run_pipeline_cycle()
        logger.info("⏰ [SCHEDULED JOB] Intelligence cycle complete.")
    except Exception as e:
        logger.error(f"❌ [SCHEDULED JOB] Intelligence cycle error: {e}")


def start_scheduler(run_on_start: bool = True):
    """Initializes jobs and enters continuous schedule loop."""
    print("""
====================================================================
           B2B AGENTIC ENTERPRISE - AUTONOMOUS SCHEDULER           
====================================================================
    Scheduled Jobs Configured:
      - Triage Agent           : Every 2 Hours
      - Email Dispatcher       : Every 1 Hour
      - 6-Agent Intelligence   : Every 4 Hours
====================================================================
    """)
    init_db()

    # Schedule tasks
    schedule.every(2).hours.do(job_triage)
    schedule.every(1).hours.do(job_dispatch)
    schedule.every(4).hours.do(job_intelligence_cycle)

    if run_on_start:
        logger.info("🚀 Executing initial startup sequence across all jobs...")
        job_triage()
        job_dispatch()
        job_intelligence_cycle()

    logger.info("⏳ Scheduler actively running. Press Ctrl+C to stop.")

    try:
        while True:
            schedule.run_pending()
            time.sleep(10)
    except KeyboardInterrupt:
        logger.info("\n🛑 Graceful shutdown initiated by user. Stopping scheduler.")
        sys.exit(0)


if __name__ == "__main__":
    start_scheduler(run_on_start=False)
