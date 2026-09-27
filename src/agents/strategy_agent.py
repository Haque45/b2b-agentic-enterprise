"""
Strategy Agent (strategy_agent.py).

The CEO Agent. Reads the Analytics JSON summary, determines daily campaign focus,
and updates campaign_directives table in SQLite.
"""

import json
from typing import Dict, Any

from src.agents.base_agent import BaseAgent


class StrategyAgent(BaseAgent):
    """CEO Strategy Agent formulating data-driven search & targeting directives."""

    def __init__(self, db_path: str = None):
        super().__init__(name="StrategyAgent", db_path=db_path or "pipeline.db")

    def run(self, analytics_summary: Dict[str, Any] = None) -> Dict[str, Any]:
        self.log("Reading Analytics JSON summary to determine daily strategic focus...")

        # If analytics_summary not passed directly, fetch latest from DB
        if not analytics_summary:
            conn = self.get_db()
            cursor = conn.cursor()
            cursor.execute("SELECT summary_json FROM analytics_logs ORDER BY id DESC LIMIT 1;")
            row = cursor.fetchone()
            conn.close()

            if row:
                analytics_summary = json.loads(row["summary_json"])
            else:
                analytics_summary = {
                    "overall_reply_rate": 0.0,
                    "top_performing_lane": "SolidWorks DFM",
                    "service_lane_metrics": {}
                }

        # Formulate CEO Prompt
        system_prompt = """You are the CEO Strategy Agent for an elite B2B Engineering Services firm.
Your role is to analyze campaign analytics and issue a clear, quantitative daily search directive for the Scout Agent.
You MUST output ONLY valid JSON matching this schema:
{
  "focus_service_lane": "<Service Lane Name>",
  "allocation_percentage": <Float between 50 and 90>,
  "target_sectors": "<Comma separated sectors>",
  "search_keywords": ["keyword 1", "keyword 2", "keyword 3"],
  "directive_text": "<Detailed 1-2 sentence CEO directive detailing why search is shifted>",
  "reasoning": "<Data-driven justification reference reply rates>"
}"""

        prompt = f"""Review these latest campaign metrics:
{json.dumps(analytics_summary, indent=2)}

Determine today's strategic focus. If one service lane (e.g. SolidWorks DFM) shows a higher positive reply rate, direct 80% of search allocation to it. Generate targeted search keywords for robotics, hardware startups, and mechanical engineering job postings."""

        response_raw = self.llm_client.complete(
            prompt=prompt,
            system_prompt=system_prompt,
            preferred_provider="openrouter",  # Hermes 3 system prompt adherence
            temperature=0.4
        )

        try:
            # Extract JSON from LLM output
            clean_json = response_raw.strip()
            if "```json" in clean_json:
                clean_json = clean_json.split("```json")[1].split("```")[0].strip()
            elif "```" in clean_json:
                clean_json = clean_json.split("```")[1].split("```")[0].strip()

            directive_data = json.loads(clean_json)
        except Exception as e:
            self.log(f"JSON parsing error from LLM response: {e}. Falling back to default directive.", level="warning")
            top_lane = analytics_summary.get("top_performing_lane", "SolidWorks DFM")
            directive_data = {
                "focus_service_lane": top_lane,
                "allocation_percentage": 80.0,
                "target_sectors": "Robotics Startups, Industrial Automation, Hardware Engineering",
                "search_keywords": [
                    f"{top_lane} hardware startup engineer",
                    "robotics company mechanical design",
                    "mechatronics automation engineering job"
                ],
                "directive_text": f"Shift 80% of today's search to '{top_lane}' due to higher positive response rates.",
                "reasoning": f"Data analysis indicates '{top_lane}' yields superior positive conversion metrics."
            }

        # Update SQLite campaign_directives table
        conn = self.get_db()
        cursor = conn.cursor()

        # Archive current active directives
        cursor.execute("UPDATE campaign_directives SET status = 'archived' WHERE status = 'active';")

        # Insert new active directive
        cursor.execute("""
            INSERT INTO campaign_directives (
                directive_text,
                target_sectors,
                focus_service_lane,
                search_keywords,
                allocation_percentage,
                reasoning,
                status
            ) VALUES (?, ?, ?, ?, ?, ?, 'active');
        """, (
            directive_data["directive_text"],
            directive_data.get("target_sectors", ""),
            directive_data.get("focus_service_lane", "SolidWorks DFM"),
            json.dumps(directive_data.get("search_keywords", [])),
            float(directive_data.get("allocation_percentage", 80.0)),
            directive_data.get("reasoning", "")
        ))

        new_id = cursor.lastrowid
        conn.commit()
        conn.close()

        self.log(f"CEO Strategy Directive updated [ID: {new_id}]: {directive_data['directive_text']}")
        return directive_data


if __name__ == "__main__":
    agent = StrategyAgent()
    res = agent.run()
    print(json.dumps(res, indent=2))
