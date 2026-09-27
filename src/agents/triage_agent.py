"""
Triage Agent (triage_agent.py).

Connects via IMAP to read incoming unread email replies (or simulates unread replies
during offline runs), uses Llama 3.1 to classify sentiment (Positive, Negative, Pricing, Unsubscribed),
and updates replies table in pipeline.db.
"""

import imaplib
import email
from email.header import decode_header
import json
from typing import Dict, Any, List, Optional

from src.agents.base_agent import BaseAgent
from src.config import IMAP_SERVER, IMAP_PORT, IMAP_USER, IMAP_PASSWORD


class TriageAgent(BaseAgent):
    """Triage Agent classifying incoming email replies and updating pipeline.db."""

    def __init__(self, db_path: str = None):
        super().__init__(name="TriageAgent", db_path=db_path or "pipeline.db")

    def fetch_imap_unread_emails(self) -> List[Dict[str, str]]:
        """Attempts to fetch unread emails via IMAP protocol."""
        if not IMAP_USER or not IMAP_PASSWORD or "example.com" in IMAP_USER:
            self.log("IMAP credentials not configured. Skipping live IMAP connection.", level="warning")
            return []

        folder_name = "B2B_Pipeline"
        messages = []
        try:
            self.log(f"Connecting to IMAP server {IMAP_SERVER}:{IMAP_PORT} as {IMAP_USER} (Folder: {folder_name})...")
            mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
            mail.login(IMAP_USER, IMAP_PASSWORD)
            
            # CRITICAL: Strictly select and read from 'B2B_Pipeline' IMAP folder (NOT default 'INBOX')
            status, count = mail.select(folder_name)
            if status != 'OK':
                self.log(f"Could not select IMAP folder '{folder_name}'. Status: {status}", level="warning")
                return []

            status, data = mail.search(None, 'UNSEEN')
            if status != 'OK':
                return []

            mail_ids = data[0].split()
            for msg_id in mail_ids[:10]:  # Process up to 10 unread emails
                res, msg_data = mail.fetch(msg_id, '(RFC822)')
                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        msg = email.message_from_bytes(response_part[1])
                        subject, encoding = decode_header(msg["Subject"])[0]
                        if isinstance(subject, bytes):
                            subject = subject.decode(encoding or "utf-8")
                        
                        sender = msg.get("From")
                        body = ""
                        if msg.is_multipart():
                            for part in msg.walk():
                                if part.get_content_type() == "text/plain":
                                    body = part.get_payload(decode=True).decode()
                                    break
                        else:
                            body = msg.get_payload(decode=True).decode()

                        messages.append({
                            "sender": sender,
                            "subject": subject,
                            "body": body.strip()
                        })
            mail.logout()
        except Exception as e:
            self.log(f"IMAP fetch error: {e}", level="warning")

        return messages

    def classify_sentiment(self, subject: str, body: str) -> str:
        """Uses Llama 3.1 LLM to classify reply sentiment into standardized buckets."""
        system_prompt = """You are an Email Sentiment Classifier for a B2B sales pipeline.
Classify the email sentiment strictly into ONE of these categories:
- Positive (Interested in meeting, call, proposal, case study, or demo)
- Pricing (Asking for hourly rates, cost estimate, or pricing details)
- Negative (Not interested, wrong timing, no fit)
- Unsubscribed (Explicit request to remove or stop emailing)
- Out of Office (Automated vacation response)

Output ONLY the category name. No explanations."""

        prompt = f"Subject: {subject}\nBody:\n{body}"

        res = self.llm_client.complete(
            prompt=prompt,
            system_prompt=system_prompt,
            preferred_provider="groq",
            temperature=0.0
        )

        clean_res = res.strip().replace(".", "")
        valid_sentiments = ["Positive", "Pricing", "Negative", "Unsubscribed", "Out of Office"]
        
        for v in valid_sentiments:
            if v.lower() in clean_res.lower():
                return v

        return "Positive" if "yes" in clean_res.lower() or "call" in clean_res.lower() else "Negative"

    def match_lead_by_email_or_subject(self, sender_email: str, subject: str) -> Optional[Dict[str, Any]]:
        """Matches incoming email to a lead in pipeline.db by email address or subject line."""
        conn = self.get_db()
        cursor = conn.cursor()

        # Try matching by subject containing company name or service lane
        cursor.execute("SELECT * FROM leads WHERE status IN ('approved_for_dispatch', 'sent');")
        leads = cursor.fetchall()
        conn.close()

        sender_clean = sender_email.lower()
        subject_clean = subject.lower()

        for lead in leads:
            comp = lead["company_name"].lower()
            url = lead["url"].lower()
            domain = url.replace("https://", "").replace("http://", "").split("/")[0]

            if domain and domain in sender_clean:
                return dict(lead)
            if comp and comp in subject_clean:
                return dict(lead)

        if leads:
            return dict(leads[0])
        return None

    def run(self) -> Dict[str, Any]:
        self.log("Checking for incoming unread email replies...")
        emails_to_process = self.fetch_imap_unread_emails()

        # Fallback simulation if IMAP is offline / no live emails found
        if not emails_to_process:
            self.log("No live IMAP emails fetched. Checking database for mock incoming simulation...")
            conn = self.get_db()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM leads WHERE status = 'sent' AND id NOT IN (SELECT lead_id FROM replies WHERE lead_id IS NOT NULL);")
            unreplied_sent_leads = cursor.fetchall()
            conn.close()

            if unreplied_sent_leads:
                # Simulate 1 incoming reply for demonstration
                sample_lead = unreplied_sent_leads[0]
                company = sample_lead["company_name"]
                lane = sample_lead["service_lane"] or "SolidWorks DFM"
                emails_to_process.append({
                    "sender": f"contact@{company.lower().replace(' ', '')}-demo.com",
                    "subject": f"Re: {sample_lead['subject'] or lane}",
                    "body": f"Hi, thanks for reaching out. We have a mechanical assembly needing {lane} optimization. Let's schedule a brief call.",
                    "lead_id": sample_lead["id"],
                    "service_lane": lane
                })

        if not emails_to_process:
            self.log("No unread replies to triage.")
            return {"triaged_count": 0, "replies": []}

        triaged = []
        conn = self.get_db()
        cursor = conn.cursor()

        for item in emails_to_process:
            sender = item["sender"]
            subj = item["subject"]
            body = item["body"]

            lead_info = self.match_lead_by_email_or_subject(sender, subj)
            lead_id = item.get("lead_id") or (lead_info["id"] if lead_info else None)
            service_lane = item.get("service_lane") or (lead_info["service_lane"] if lead_info else "SolidWorks DFM")

            # Classify sentiment using Llama 3.1
            sentiment = self.classify_sentiment(subj, body)

            cursor.execute("""
                INSERT INTO replies (lead_id, sender_email, subject, body, sentiment, service_lane)
                VALUES (?, ?, ?, ?, ?, ?);
            """, (lead_id, sender, subj, body, sentiment, service_lane))

            if lead_id:
                cursor.execute("UPDATE leads SET status = 'replied' WHERE id = ?;", (lead_id,))

            triaged.append({
                "lead_id": lead_id,
                "sender": sender,
                "sentiment": sentiment,
                "service_lane": service_lane
            })
            self.log(f"Triaged reply from {sender}: Sentiment -> {sentiment} (Service Lane: {service_lane})")

        conn.commit()
        conn.close()

        self.log(f"Triage Agent completed processing {len(triaged)} replies.")
        return {"triaged_count": len(triaged), "replies": triaged}


if __name__ == "__main__":
    agent = TriageAgent()
    res = agent.run()
    print(json.dumps(res, indent=2))
