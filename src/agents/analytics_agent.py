"""
Analytics Agent (analytics_agent.py).

Reads pipeline.db to calculate reply rates, sentiment ratios, and performance metrics
per service lane. Outputs a JSON summary and logs it to analytics_logs table.
"""

import json
from datetime import datetime
from typing import Dict, Any, List

from src.agents.base_agent import BaseAgent


class AnalyticsAgent(BaseAgent):
    """Calculates campaign performance and sentiment analytics from pipeline.db."""

    def __init__(self, db_path: str = None):
        super().__init__(name="AnalyticsAgent", db_path=db_path or "pipeline.db")

    def run(self) -> Dict[str, Any]:
        self.log("Starting analytics computation across service lanes in pipeline.db...")
        conn = self.get_db()
        cursor = conn.cursor()

        # 1. Total Sent Leads
        cursor.execute("SELECT COUNT(*) as sent_count FROM leads WHERE status IN ('sent', 'replied');")
        total_sent = cursor.fetchone()["sent_count"]

        # 2. Total Replies
        cursor.execute("SELECT COUNT(*) as reply_count FROM replies;")
        total_replies = cursor.fetchone()["reply_count"]

        overall_reply_rate = round((total_replies / total_sent * 100), 2) if total_sent > 0 else 0.0

        # 3. Metrics per Service Lane
        cursor.execute("""
            SELECT 
                service_lane,
                COUNT(*) as sent_count
            FROM leads 
            WHERE status IN ('sent', 'replied') AND service_lane IS NOT NULL
            GROUP BY service_lane;
        """)
        sent_by_lane = {row["service_lane"]: row["sent_count"] for row in cursor.fetchall()}

        cursor.execute("""
            SELECT 
                service_lane,
                sentiment,
                COUNT(*) as sentiment_count
            FROM replies
            WHERE service_lane IS NOT NULL
            GROUP BY service_lane, sentiment;
        """)
        replies_by_lane_sentiment = cursor.fetchall()

        service_lane_metrics = {}
        for lane, sent_cnt in sent_by_lane.items():
            service_lane_metrics[lane] = {
                "sent_leads": sent_cnt,
                "total_replies": 0,
                "positive": 0,
                "negative": 0,
                "pricing": 0,
                "unsubscribed": 0,
                "reply_rate": 0.0,
                "positive_reply_rate": 0.0
            }

        for row in replies_by_lane_sentiment:
            lane = row["service_lane"]
            sent_type = row["sentiment"]
            cnt = row["sentiment_count"]

            if lane not in service_lane_metrics:
                service_lane_metrics[lane] = {
                    "sent_leads": 0,
                    "total_replies": 0,
                    "positive": 0,
                    "negative": 0,
                    "pricing": 0,
                    "unsubscribed": 0,
                    "reply_rate": 0.0,
                    "positive_reply_rate": 0.0
                }

            metrics = service_lane_metrics[lane]
            metrics["total_replies"] += cnt
            if sent_type == "Positive":
                metrics["positive"] += cnt
            elif sent_type == "Negative":
                metrics["negative"] += cnt
            elif sent_type == "Pricing":
                metrics["pricing"] += cnt
            elif sent_type == "Unsubscribed":
                metrics["unsubscribed"] += cnt

        # Calculate Rates per Service Lane
        top_lane = None
        max_positive_rate = -1.0

        for lane, metrics in service_lane_metrics.items():
            s_cnt = metrics["sent_leads"]
            t_rep = metrics["total_replies"]
            pos_cnt = metrics["positive"]

            metrics["reply_rate"] = round((t_rep / s_cnt * 100), 2) if s_cnt > 0 else 0.0
            metrics["positive_reply_rate"] = round((pos_cnt / s_cnt * 100), 2) if s_cnt > 0 else 0.0

            if metrics["positive_reply_rate"] > max_positive_rate:
                max_positive_rate = metrics["positive_reply_rate"]
                top_lane = lane

        summary_payload = {
            "timestamp": datetime.now().isoformat(),
            "total_sent_leads": total_sent,
            "total_replies": total_replies,
            "overall_reply_rate": overall_reply_rate,
            "top_performing_lane": top_lane or "SolidWorks DFM",
            "service_lane_metrics": service_lane_metrics
        }

        # Save JSON to analytics_logs
        summary_json = json.dumps(summary_payload, indent=2)
        cursor.execute("INSERT INTO analytics_logs (summary_json) VALUES (?);", (summary_json,))
        conn.commit()
        conn.close()

        self.log(f"Analytics completed. Overall reply rate: {overall_reply_rate}%. Top performing lane: {top_lane}.")
        return summary_payload


if __name__ == "__main__":
    agent = AnalyticsAgent()
    res = agent.run()
    print(json.dumps(res, indent=2))
