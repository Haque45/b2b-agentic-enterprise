"""
Scout Agent (scout_agent.py).

Reads active strategy directive from SQLite, searches web via DuckDuckGo for targeted
hardware startups, robotics companies, or engineering postings, and inserts leads
into leads table with status='scouted'.
"""

import json
from typing import Dict, Any, List

from src.agents.base_agent import BaseAgent
from src.utils.search_engine import search_web


class ScoutAgent(BaseAgent):
    """Scout Agent discovering relevant target companies and decision-makers on the web."""

    def __init__(self, db_path: str = None):
        super().__init__(name="ScoutAgent", db_path=db_path or "pipeline.db")

    def get_active_directive(self) -> Dict[str, Any]:
        """Fetches active directive from campaign_directives table."""
        conn = self.get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM campaign_directives WHERE status = 'active' ORDER BY id DESC LIMIT 1;")
        row = cursor.fetchone()
        conn.close()

        if row:
            keywords = json.loads(row["search_keywords"]) if row["search_keywords"] else []
            return {
                "id": row["id"],
                "directive_text": row["directive_text"],
                "focus_service_lane": row["focus_service_lane"],
                "search_keywords": keywords,
                "target_sectors": row["target_sectors"]
            }
        
        # Fallback default active directive
        return {
            "id": 0,
            "directive_text": "Target robotics and hardware companies for SolidWorks DFM optimization.",
            "focus_service_lane": "SolidWorks DFM",
            "search_keywords": ["robotics startup mechanical engineer", "SolidWorks DFM hardware startup"],
            "target_sectors": "Robotics, Hardware"
        }

    def is_valid_b2b_lead(self, url: str, title: str, body: str) -> bool:
        """Filters out non-B2B sites, adult domains, font downloads, and social media sites."""
        combined = f"{url} {title} {body}".lower()
        
        # Blocked keywords & domain fragments
        blocked_terms = [
            "porn", "xxx", "jizz", "adult", "dafont", "zhihu", "hqporn",
            "font", "wallpaper", "torrent", "bilibili", "weibo", "mp3", "video stream"
        ]
        
        for term in blocked_terms:
            if term in combined:
                return False
        return True

    def run(self) -> Dict[str, Any]:
        self.log("Reading active strategy directive from pipeline.db...")
        directive = self.get_active_directive()
        focus_lane = directive.get("focus_service_lane", "SolidWorks DFM")
        keywords = directive.get("search_keywords", ["hardware startup mechanical engineer"])

        self.log(f"Executing web scouting for service lane: '{focus_lane}' across keywords: {keywords}")

        scouted_leads = []
        conn = self.get_db()
        cursor = conn.cursor()

        # Existing URLs for deduplication
        cursor.execute("SELECT url FROM leads;")
        existing_urls = {row["url"].lower().rstrip("/") for row in cursor.fetchall()}

        for kw in keywords:
            search_results = search_web(query=kw, max_results=3)

            for item in search_results:
                url = item.get("href", "").strip()
                title = item.get("title", "").strip()
                body = item.get("body", "").strip()

                if not url or url.lower().rstrip("/") in existing_urls:
                    continue

                if not self.is_valid_b2b_lead(url, title, body):
                    self.log(f"Skipping non-B2B or unsafe domain: {url}", level="warning")
                    continue

                # Parse Company Name & Decision Maker using fast LLM reasoning (Groq Llama 3.1)
                system_prompt = "Extract company name and target engineering decision-maker title from the search snippet. Output ONLY valid JSON: {\"company_name\": \"...\", \"decision_maker\": \"...\"}"
                prompt = f"Search Keyword: {kw}\nTitle: {title}\nURL: {url}\nSnippet: {body}"

                res_raw = self.llm_client.complete(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    preferred_provider="groq",  # Fast scouting reasoning
                    temperature=0.2
                )

                company_name = title.split("-")[0].split("|")[0].strip() or "Tech Company"
                decision_maker = "Engineering Lead"

                try:
                    clean_res = res_raw.strip()
                    if "```json" in clean_res:
                        clean_res = clean_res.split("```json")[1].split("```")[0].strip()
                    elif "```" in clean_res:
                        clean_res = clean_res.split("```")[1].split("```")[0].strip()
                    parsed = json.loads(clean_res)
                    company_name = parsed.get("company_name", company_name)
                    decision_maker = parsed.get("decision_maker", decision_maker)
                except Exception:
                    pass

                # Insert into leads table (status: 'scouted')
                try:
                    cursor.execute("""
                        INSERT INTO leads (
                            company_name,
                            url,
                            decision_maker,
                            target_keyword,
                            service_lane,
                            status
                        ) VALUES (?, ?, ?, ?, ?, 'scouted');
                    """, (company_name, url, decision_maker, kw, focus_lane))
                    
                    lead_id = cursor.lastrowid
                    existing_urls.add(url.lower().rstrip("/"))
                    scouted_leads.append({
                        "id": lead_id,
                        "company_name": company_name,
                        "url": url,
                        "decision_maker": decision_maker,
                        "service_lane": focus_lane
                    })
                    self.log(f"Scouted new lead [ID: {lead_id}]: {company_name} ({url})")
                except Exception as e:
                    self.log(f"Failed to insert lead {url}: {e}", level="warning")

        conn.commit()
        conn.close()

        self.log(f"Scouting complete. Discovered {len(scouted_leads)} new leads.")
        return {"scouted_count": len(scouted_leads), "leads": scouted_leads}


if __name__ == "__main__":
    agent = ScoutAgent()
    res = agent.run()
    print(json.dumps(res, indent=2))
