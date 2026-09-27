"""
PR Guardian Agent (pr_agent.py).

The Compliance Officer. Reads 'drafted' rows from leads table, audits copy against
a spam-lexicon, verifies word count < 75 words, and checks peer-to-peer tone.
Updates status to 'approved_for_dispatch' OR kicks back to 'scouted' with compliance_notes.
"""

import re
import json
from typing import Dict, Any, List

from src.agents.base_agent import BaseAgent

# Comprehensive B2B Email Spam Lexicon
SPAM_LEXICON = [
    "free", "revolutionary", "synergy", "guaranteed", "no risk", "100%",
    "act now", "limited time", "click here", "buy direct", "special offer",
    "miracle", "unbelievable", "risk free", "best price", "extra income",
    "earn $", "double your", "fast cash", "bargain", "satisfaction guaranteed"
]


class PRAgent(BaseAgent):
    """PR Guardian Compliance Agent enforcing strict spam & word count constraints."""

    def __init__(self, db_path: str = None):
        super().__init__(name="PRAgent", db_path=db_path or "pipeline.db")

    def audit_copy(self, email_body: str, subject: str) -> Dict[str, Any]:
        """
        Audits an email draft against length and spam lexicon rules.
        """
        text = f"{subject} {email_body}".lower()
        words = email_body.split()
        word_count = len(words)

        spam_found = []
        for term in SPAM_LEXICON:
            # Match whole words / phrases
            pattern = r'\b' + re.escape(term) + r'\b'
            if re.search(pattern, text):
                spam_found.append(term)

        is_valid = True
        reasons = []

        if word_count >= 75:
            is_valid = False
            reasons.append(f"Word count {word_count} exceeds 75 word limit.")

        if spam_found:
            is_valid = False
            reasons.append(f"Contains prohibited spam lexicon: {', '.join(spam_found)}.")

        if word_count < 15:
            is_valid = False
            reasons.append(f"Word count {word_count} is too short (< 15 words).")

        notes = "PASSED: Complies with word count (<75 words) and spam policy." if is_valid else "FAILED: " + "; ".join(reasons)

        return {
            "is_approved": is_valid,
            "word_count": word_count,
            "spam_words": spam_found,
            "notes": notes
        }

    def run(self) -> Dict[str, Any]:
        self.log("Fetching 'drafted' leads from pipeline.db for compliance audit...")
        conn = self.get_db()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM leads WHERE status = 'drafted';")
        drafted_leads = cursor.fetchall()

        if not drafted_leads:
            self.log("No 'drafted' leads to audit.")
            conn.close()
            return {"approved_count": 0, "rejected_count": 0, "audits": []}

        approved_count = 0
        rejected_count = 0
        audit_results = []

        for lead in drafted_leads:
            lead_id = lead["id"]
            company_name = lead["company_name"]
            body = lead["email_body"] or ""
            subject = lead["subject"] or ""

            # Standard Audit
            audit = self.audit_copy(body, subject)

            # LLM Secondary Verification for Tone & Compliance (Groq Llama 3.1)
            if audit["is_approved"]:
                system_prompt = "You are a Compliance Officer. Verify if this email pitch is professional, peer-to-peer engineering tone, and free of sales hype. Output ONLY valid JSON: {\"approved\": true/false, \"reason\": \"...\"}"
                prompt = f"Subject: {subject}\nBody:\n{body}"
                
                res_raw = self.llm_client.complete(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    preferred_provider="groq",
                    temperature=0.1
                )
                try:
                    clean_res = res_raw.strip()
                    if "```json" in clean_res:
                        clean_res = clean_res.split("```json")[1].split("```")[0].strip()
                    elif "```" in clean_res:
                        clean_res = clean_res.split("```")[1].split("```")[0].strip()
                    
                    llm_eval = json.loads(clean_res)
                    if not llm_eval.get("approved", True):
                        audit["is_approved"] = False
                        audit["notes"] = f"FAILED LLM Tone Check: {llm_eval.get('reason', 'Sales hype detected.')}"
                except Exception:
                    pass

            # Update Database Status based on Audit Result
            if audit["is_approved"]:
                new_status = "approved_for_dispatch"
                approved_count += 1
                self.log(f"Lead [ID: {lead_id}] {company_name} APPROVED for dispatch ({audit['word_count']} words).")
            else:
                new_status = "scouted"  # Kick back to scouted for re-drafting
                rejected_count += 1
                self.log(f"Lead [ID: {lead_id}] {company_name} REJECTED: {audit['notes']}", level="warning")

            cursor.execute("""
                UPDATE leads
                SET status = ?,
                    compliance_notes = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?;
            """, (new_status, audit["notes"], lead_id))

            audit_results.append({
                "id": lead_id,
                "company_name": company_name,
                "status": new_status,
                "word_count": audit["word_count"],
                "notes": audit["notes"]
            })

        conn.commit()
        conn.close()

        self.log(f"PR Guardian completed audit: {approved_count} approved for dispatch, {rejected_count} kicked back.")
        return {
            "approved_count": approved_count,
            "rejected_count": rejected_count,
            "audits": audit_results
        }


if __name__ == "__main__":
    agent = PRAgent()
    res = agent.run()
    print(json.dumps(res, indent=2))
