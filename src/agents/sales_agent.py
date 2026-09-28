"""
Sales Agent / Copywriter (sales_agent.py).

Reads 'scouted' rows from leads table, scrapes target URL for context using BeautifulSoup4,
and generates zero-fluff peer-to-peer cold emails strictly grounded in founder background:
- UET Faisalabad final year Mechatronics engineering
- SolidWorks DFM (CNC, injection molding, sheet metal)
- ROS 2 / Gazebo simulation & Nav2 autonomous navigation
- TinyML / INT8 quantization on ESP32 & STM32
- Cascade pneumatics & electropneumatic sequence control

Also handles 'needs_follow_up' leads by generating follow-up copy that references
the original outreach and provides a new angle.

Updates row with email_body, subject, service_lane, and status='drafted'.
"""

import json
from datetime import datetime
from typing import Dict, Any, List, Optional

from src.agents.base_agent import BaseAgent
from src.utils.web_scraper import scrape_company_website
from src.config import FOUNDER_PROFILE


class SalesAgent(BaseAgent):
    """Copywriter / Sales Agent crafting personalized, grounded technical pitches."""

    def __init__(self, db_path: str = None):
        super().__init__(name="SalesAgent", db_path=db_path or "pipeline.db")

    def run(self, current_date: Optional[str] = None) -> Dict[str, Any]:
        today = current_date or datetime.now().strftime("%Y-%m-%d")
        self.log(f"Starting copywriting cycle (date context: {today})...")

        conn = self.get_db()
        cursor = conn.cursor()

        # Fetch scouted leads for initial outreach
        cursor.execute("SELECT * FROM leads WHERE status = 'scouted';")
        scouted_leads = cursor.fetchall()

        # Fetch follow-up eligible leads
        cursor.execute("SELECT * FROM leads WHERE status = 'needs_follow_up';")
        followup_leads = cursor.fetchall()

        total = len(scouted_leads) + len(followup_leads)
        if total == 0:
            self.log("No leads to draft (scouted or follow-up).")
            conn.close()
            return {"drafted_count": 0, "drafts": []}

        self.log(f"Processing {len(scouted_leads)} scouted + {len(followup_leads)} follow-up leads...")
        drafted_records = []

        # ── INITIAL OUTREACH ──
        initial_system_prompt = f"""You are an elite Engineering Technical Copywriter. You write short, peer-to-peer cold email pitches.
Today's date: {today}

CRITICAL FOUNDER GROUNDING:
You are representing a final-year Mechatronics Engineering student at UET Faisalabad with hands-on expertise in:
1. SolidWorks DFM: Optimizing complex mechanical assemblies for CNC machining, injection molding, and sheet metal to slash unit production cost and lead time.
2. ROS 2 / Gazebo Simulation: Building high-fidelity URDF models, Gazebo physics environments, and Nav2 autonomous navigation pipelines.
3. TinyML / INT8 Quantization: Deploying INT8 quantized neural network models (TFLite Micro) on resource-constrained microcontrollers (ESP32, STM32).
4. Cascade Pneumatics: Multi-cylinder electropneumatic sequence control and PLC valve manifold automation.

STRICT WRITING RULES:
1. WORD COUNT: Maximum 65 words total. Zero fluff, zero sales jargon.
2. TONE: Engineering peer-to-peer, technical, direct, authentic.
3. GROUNDING: Naturally highlight relevant expertise based on the target company context and service lane.
4. STRUCTURE: Direct opening greeting -> Contextual observation -> Technical grounding proof point -> Low-friction call to action (5-min chat).

OUTPUT FORMAT:
Return ONLY valid JSON:
{{
  "subject": "<Concise subject line under 8 words>",
  "email_body": "<The exact email pitch body under 65 words>",
  "service_lane": "<SolidWorks DFM | ROS 2 / Gazebo | TinyML / INT8 Quantization | Cascade Pneumatics>"
}}"""

        for lead in scouted_leads:
            draft = self._draft_initial(lead, initial_system_prompt, cursor)
            if draft:
                drafted_records.append(draft)

        # ── FOLLOW-UP OUTREACH ──
        followup_system_prompt = f"""You are an elite Engineering Technical Copywriter writing a FOLLOW-UP email.
Today's date: {today}

This is NOT a first-touch email. The lead was already contacted previously and did not respond.
Your job is to write a SHORT, friendly follow-up that:
1. References the previous outreach naturally ("I reached out last week about..." or "Following up on my note about...").
2. Provides a NEW angle, insight, or value proposition — do NOT repeat the exact same pitch.
3. Keeps it under 50 words. Even shorter is better.
4. Ends with a simple low-friction CTA.

FOUNDER: Final-year Mechatronics Engineering student at UET Faisalabad.

OUTPUT FORMAT:
Return ONLY valid JSON:
{{
  "subject": "Re: <original subject or short follow-up subject>",
  "email_body": "<Follow-up body under 50 words>",
  "service_lane": "<Same service lane as original>"
}}"""

        for lead in followup_leads:
            draft = self._draft_follow_up(lead, followup_system_prompt, cursor)
            if draft:
                drafted_records.append(draft)

        conn.commit()
        conn.close()

        self.log(f"Sales Agent completed drafting {len(drafted_records)} pitches.")
        return {"drafted_count": len(drafted_records), "drafts": drafted_records}

    def _draft_initial(self, lead, system_prompt: str, cursor) -> Optional[Dict]:
        """Generates an initial cold outreach draft for a scouted lead."""
        lead_id = lead["id"]
        company_name = lead["company_name"]
        url = lead["url"]
        dm = lead["decision_maker"] or "Engineering Manager"
        lane = lead["service_lane"] or "SolidWorks DFM"

        web_context = scrape_company_website(url)

        prompt = f"""Target Company: {company_name}
Target Decision Maker: {dm}
Service Lane Focus: {lane}
Website Title: {web_context['title']}
Meta Description: {web_context['meta_description']}
Page Snippet: {web_context['main_text']}

Draft a personalized, high-converting 60-word peer-to-peer email pitch grounded in UET Faisalabad mechatronics expertise."""

        response_raw = self.llm_client.complete(
            prompt=prompt,
            system_prompt=system_prompt,
            preferred_provider="openrouter",
            temperature=0.5
        )

        subject, email_body = self._parse_llm_output(response_raw, lane, company_name, dm)

        cursor.execute("""
            UPDATE leads
            SET email_body = ?, subject = ?, service_lane = ?,
                status = 'drafted', updated_at = CURRENT_TIMESTAMP
            WHERE id = ?;
        """, (email_body, subject, lane, lead_id))

        self.log(f"Drafted pitch for lead [ID: {lead_id}] {company_name} ({len(email_body.split())} words)")
        return {
            "id": lead_id,
            "company_name": company_name,
            "subject": subject,
            "word_count": len(email_body.split()),
            "type": "initial",
            "status": "drafted",
        }

    def _draft_follow_up(self, lead, system_prompt: str, cursor) -> Optional[Dict]:
        """Generates follow-up copy for a stale dispatched lead."""
        lead_id = lead["id"]
        company_name = lead["company_name"]
        url = lead["url"]
        dm = lead["decision_maker"] or "Engineering Manager"
        lane = lead["service_lane"] or "SolidWorks DFM"
        original_subject = lead["subject"] or f"{lane} for {company_name}"
        original_body = lead["email_body"] or ""
        follow_up_num = (lead["follow_up_count"] or 0) + 1

        prompt = f"""Target Company: {company_name}
Target Decision Maker: {dm}
Service Lane Focus: {lane}
Original Email Subject: {original_subject}
Original Email Body (truncated): {original_body[:200]}
This is follow-up #{follow_up_num}.

Write a short, friendly follow-up email that provides a new angle."""

        response_raw = self.llm_client.complete(
            prompt=prompt,
            system_prompt=system_prompt,
            preferred_provider="openrouter",
            temperature=0.5
        )

        subject = f"Re: {original_subject}"
        email_body = ""

        try:
            clean_json = response_raw.strip()
            if "```json" in clean_json:
                clean_json = clean_json.split("```json")[1].split("```")[0].strip()
            elif "```" in clean_json:
                clean_json = clean_json.split("```")[1].split("```")[0].strip()
            parsed = json.loads(clean_json)
            subject = parsed.get("subject", subject)
            email_body = parsed.get("email_body", "")
            lane = parsed.get("service_lane", lane)
        except Exception as e:
            self.log(f"Follow-up LLM parse error for lead {lead_id}: {e}", level="warning")

        if not email_body:
            email_body = (
                f"Hi {dm.split()[0] if dm else 'there'},\n\n"
                f"Just following up on my note about {lane} for {company_name}. "
                f"Happy to share a quick case study if helpful.\n\nBest,\nHaque"
            )

        # Update: set back to 'drafted' so PR Guardian re-audits before dispatch
        cursor.execute("""
            UPDATE leads
            SET email_body = ?, subject = ?, service_lane = ?,
                status = 'drafted', updated_at = CURRENT_TIMESTAMP
            WHERE id = ?;
        """, (email_body, subject, lane, lead_id))

        self.log(f"Drafted follow-up #{follow_up_num} for lead [ID: {lead_id}] {company_name} ({len(email_body.split())} words)")
        return {
            "id": lead_id,
            "company_name": company_name,
            "subject": subject,
            "word_count": len(email_body.split()),
            "type": f"follow_up_{follow_up_num}",
            "status": "drafted",
        }

    def _parse_llm_output(self, response_raw: str, lane: str, company_name: str, dm: str):
        """Parses LLM JSON output, with deterministic fallback."""
        subject = f"{lane} for {company_name}"
        email_body = ""

        try:
            clean_json = response_raw.strip()
            if "```json" in clean_json:
                clean_json = clean_json.split("```json")[1].split("```")[0].strip()
            elif "```" in clean_json:
                clean_json = clean_json.split("```")[1].split("```")[0].strip()
            parsed = json.loads(clean_json)
            subject = parsed.get("subject", subject)
            email_body = parsed.get("email_body", "")
            lane = parsed.get("service_lane", lane)
        except Exception as e:
            self.log(f"Copywriter LLM output parse error: {e}", level="warning")

        if not email_body:
            first_name = dm.split()[0] if dm else "there"
            if "ROS 2" in lane:
                email_body = f"Hi {first_name},\n\nNoticed {company_name}'s robotics development. As a final-year Mechatronics engineer at UET Faisalabad, I build ROS 2 / Gazebo simulation environments with custom URDFs and Nav2 navigation pipelines to test hardware virtually before fabrication.\n\nOpen to a quick 5-minute technical chat this week?"
            elif "TinyML" in lane:
                email_body = f"Hi {first_name},\n\nSaw {company_name}'s embedded sensor work. As a final-year Mechatronics engineer at UET Faisalabad, I specialize in TinyML INT8 quantization for ESP32 and STM32 MCUs—cutting memory footprint by 75%.\n\nWould you be open to reviewing benchmarks?"
            else:
                email_body = f"Hi {first_name},\n\nSaw {company_name}'s hardware product line. As a final-year Mechatronics engineer at UET Faisalabad, I specialize in SolidWorks DFM—optimizing assemblies for CNC machining and sheet metal to slash unit costs by 20%.\n\nWorth a 5-minute technical chat Thursday?"

        return subject, email_body


if __name__ == "__main__":
    agent = SalesAgent()
    res = agent.run()
    print(json.dumps(res, indent=2))
