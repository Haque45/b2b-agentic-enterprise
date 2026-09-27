"""
Outbound Email Dispatcher Module (src/dispatcher.py).

Bypasses traditional SMTP by utilizing Resend API to dispatch approved email leads.
Reads leads from pipeline.db with status 'approved_for_dispatch', sends via Resend API,
enforces a 60-120 second sleep jitter between dispatches, and updates SQLite status to 'dispatched'.
"""

import os
import time
import random
import logging
import sqlite3
from typing import Dict, Any, List, Optional
import resend

from database import get_db_connection, DEFAULT_DB_PATH
from src.config import RESEND_API_KEY, RESEND_FROM_EMAIL

logger = logging.getLogger("EmailDispatcher")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")


class ResendEmailDispatcher:
    """Dispatches approved emails via Resend HTTP API."""

    def __init__(self, db_path: str = DEFAULT_DB_PATH, api_key: Optional[str] = None):
        self.db_path = db_path
        self.api_key = api_key or os.environ.get("RESEND_API_KEY") or RESEND_API_KEY
        self.from_email = RESEND_FROM_EMAIL or "Riyan <eng@muhammadriyan.tech>"

        if self.api_key:
            resend.api_key = self.api_key
        else:
            logger.warning("[Dispatcher] RESEND_API_KEY is not set. Operating in dry-run/mock mode.")

    def get_approved_leads(self) -> List[Dict[str, Any]]:
        """Queries pipeline.db for leads ready for dispatch."""
        conn = get_db_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM leads WHERE status = 'approved_for_dispatch';")
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def update_lead_status(self, lead_id: int, status: str, notes: Optional[str] = None) -> None:
        """Updates SQLite status for a lead."""
        conn = get_db_connection(self.db_path)
        cursor = conn.cursor()
        if notes:
            cursor.execute("""
                UPDATE leads
                SET status = ?, compliance_notes = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?;
            """, (status, notes, lead_id))
        else:
            cursor.execute("""
                UPDATE leads
                SET status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?;
            """, (status, lead_id))
        conn.commit()
        conn.close()

    def send_email_via_resend(self, to_email: str, subject: str, body_text: str) -> bool:
        """Calls Resend API to transmit the email."""
        if not self.api_key:
            logger.info(f"[Mock Dispatch] Sending email to {to_email} via Resend mock: '{subject}'")
            return True

        resend.api_key = self.api_key
        html_body = body_text.replace("\n", "<br>")
        params = {
            "from": self.from_email,
            "to": [to_email],
            "subject": subject,
            "text": body_text,
            "html": f"<div style='font-family: sans-serif; font-size: 14px; line-height: 1.6; color: #333;'>{html_body}</div>"
        }

        try:
            email_response = resend.Emails.send(params)
            logger.info(f"[Resend Success] Email sent to {to_email}. Response ID: {email_response.get('id', 'N/A')}")
            return True
        except Exception as e:
            logger.error(f"[Resend Error] Failed to send email to {to_email}: {e}")
            return False

    def dispatch_pending_leads(self, max_dispatches: Optional[int] = None) -> Dict[str, Any]:
        """
        Fetches all 'approved_for_dispatch' leads and sends them with 60-120s sleep jitter.
        """
        approved_leads = self.get_approved_leads()

        if not approved_leads:
            logger.info("[Dispatcher] No leads currently approved for dispatch.")
            return {"dispatched_count": 0, "dispatched_leads": []}

        if max_dispatches:
            approved_leads = approved_leads[:max_dispatches]

        logger.info(f"[Dispatcher] Starting dispatch for {len(approved_leads)} approved leads via Resend API...")
        dispatched_list = []

        for idx, lead in enumerate(approved_leads):
            lead_id = lead["id"]
            company_name = lead["company_name"]
            subject = lead["subject"] or f"Mechatronics Engineering for {company_name}"
            email_body = lead["email_body"] or ""

            # Recipient Email Determination
            # If lead URL/decision_maker domain gives an email, or fallback to target email format
            recipient_email = lead.get("recipient_email") or f"contact@{company_name.lower().replace(' ', '').replace('.', '')}-sample.com"

            logger.info(f"[{idx+1}/{len(approved_leads)}] Dispatching lead [ID: {lead_id}] '{company_name}' to {recipient_email}...")

            success = self.send_email_via_resend(
                to_email=recipient_email,
                subject=subject,
                body_text=email_body
            )

            if success:
                self.update_lead_status(lead_id, status="dispatched")
                dispatched_list.append({
                    "id": lead_id,
                    "company_name": company_name,
                    "recipient_email": recipient_email,
                    "status": "dispatched"
                })

                # Sleep jitter between 60 and 120 seconds if more leads remain
                if idx < len(approved_leads) - 1:
                    jitter = random.randint(60, 120)
                    logger.info(f"[Jitter] Sleeping for {jitter} seconds before next email dispatch...")
                    time.sleep(jitter)
            else:
                self.update_lead_status(lead_id, status="approved_for_dispatch", notes="Dispatch failed via Resend API")

        logger.info(f"[Dispatcher Complete] Successfully dispatched {len(dispatched_list)} leads.")
        return {
            "dispatched_count": len(dispatched_list),
            "dispatched_leads": dispatched_list
        }


def run_dispatcher():
    dispatcher = ResendEmailDispatcher()
    return dispatcher.dispatch_pending_leads()


if __name__ == "__main__":
    run_dispatcher()
