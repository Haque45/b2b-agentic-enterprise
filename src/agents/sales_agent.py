"""
Sales Agent / Copywriter (sales_agent.py).

Reads 'scouted' rows from leads table, scrapes target URL for context using BeautifulSoup4,
and generates zero-fluff peer-to-peer cold emails strictly grounded in founder background:
- UET Faisalabad final year Mechatronics engineering
- SolidWorks DFM (CNC, injection molding, sheet metal)
- ROS 2 / Gazebo simulation & Nav2 autonomous navigation
- TinyML / INT8 quantization on ESP32 & STM32
- Cascade pneumatics & electropneumatic sequence control

Updates row with email_body, subject, service_lane, and status='drafted'.
"""

import json
from typing import Dict, Any, List

from src.agents.base_agent import BaseAgent
from src.utils.web_scraper import scrape_company_website
from src.config import FOUNDER_PROFILE


class SalesAgent(BaseAgent):
    """Copywriter / Sales Agent crafting personalized, grounded technical pitches."""

    def __init__(self, db_path: str = None):
        super().__init__(name="SalesAgent", db_path=db_path or "pipeline.db")

    def run(self) -> Dict[str, Any]:
        self.log("Fetching 'scouted' leads from pipeline.db...")
        conn = self.get_db()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM leads WHERE status = 'scouted';")
        scouted_leads = cursor.fetchall()

        if not scouted_leads:
            self.log("No 'scouted' leads found to draft.")
            conn.close()
            return {"drafted_count": 0, "drafts": []}

        self.log(f"Processing {len(scouted_leads)} scouted leads for copywriting...")
        drafted_records = []

        system_prompt = f"""You are an elite Engineering Technical Copywriter. You write short, peer-to-peer cold email pitches.

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
            lead_id = lead["id"]
            company_name = lead["company_name"]
            url = lead["url"]
            dm = lead["decision_maker"] or "Engineering Manager"
            lane = lead["service_lane"] or "SolidWorks DFM"

            # Scrape web page for grounding context
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
                preferred_provider="openrouter",  # Hermes 3 system prompt adherence
                temperature=0.5
            )

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
                self.log(f"Copywriter LLM output parse error for lead {lead_id}: {e}", level="warning")

            if not email_body:
                # Deterministic fallback draft grounded in UET Faisalabad background
                if "ROS 2" in lane:
                    email_body = f"Hi {dm.split()[0] if dm else 'there'},\n\nNoticed {company_name}'s robotics development. As a final-year Mechatronics engineer at UET Faisalabad, I build ROS 2 / Gazebo simulation environments with custom URDFs and Nav2 navigation pipelines to test hardware virtually before fabrication.\n\nOpen to a quick 5-minute technical chat this week?"
                elif "TinyML" in lane:
                    email_body = f"Hi {dm.split()[0] if dm else 'there'},\n\nSaw {company_name}'s embedded sensor work. As a final-year Mechatronics engineer at UET Faisalabad, I specialize in TinyML INT8 quantization for ESP32 and STM32 MCUs—cutting memory footprint by 75%.\n\nWould you be open to reviewing benchmarks?"
                else:
                    email_body = f"Hi {dm.split()[0] if dm else 'there'},\n\nSaw {company_name}'s hardware product line. As a final-year Mechatronics engineer at UET Faisalabad, I specialize in SolidWorks DFM—optimizing assemblies for CNC machining and sheet metal to slash unit costs by 20%.\n\nWorth a 5-minute technical chat Thursday?"

            # Update row in leads table (status: 'drafted')
            cursor.execute("""
                UPDATE leads
                SET email_body = ?,
                    subject = ?,
                    service_lane = ?,
                    status = 'drafted',
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?;
            """, (email_body, subject, lane, lead_id))

            drafted_records.append({
                "id": lead_id,
                "company_name": company_name,
                "subject": subject,
                "word_count": len(email_body.split()),
                "status": "drafted"
            })

            self.log(f"Drafted pitch for lead [ID: {lead_id}] {company_name} ({len(email_body.split())} words)")

        conn.commit()
        conn.close()

        self.log(f"Sales Agent completed drafting {len(drafted_records)} pitches.")
        return {"drafted_count": len(drafted_records), "drafts": drafted_records}


if __name__ == "__main__":
    agent = SalesAgent()
    res = agent.run()
    print(json.dumps(res, indent=2))
