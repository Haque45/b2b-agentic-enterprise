"""
Hunter Agent (hunter_agent.py).

Advanced lead sourcing agent equipped with three callable tools:
1. search_github_repos(query)  — GitHub REST API (unauthenticated, 60 req/hr)
2. search_huggingface(query)   — HuggingFace Hub API (free, public)
3. search_google_b2b(query)    — DuckDuckGo + BeautifulSoup fallback

The Hunter reads the CEO Directive and intelligently selects which tools
to call based on the service lane focus and target sectors.

All discovered leads are inserted into pipeline.db with source_platform tracking.
"""

import json
import re
import logging
import requests
from typing import Dict, Any, List, Optional

from src.agents.base_agent import BaseAgent

logger = logging.getLogger("HunterAgent")

# ─────────────────────────────────────────────
# TOOL 1: GitHub Repository Search
# ─────────────────────────────────────────────
def search_github_repos(query: str, max_results: int = 5) -> List[Dict[str, str]]:
    """
    Searches GitHub REST API (unauthenticated) for repositories matching the query.
    Extracts repo name, URL, description, owner login, and language.
    Free tier: 10 requests/minute, 60 requests/hour.
    """
    results = []
    url = "https://api.github.com/search/repositories"
    params = {
        "q": query,
        "sort": "stars",
        "order": "desc",
        "per_page": max_results,
    }
    headers = {"Accept": "application/vnd.github+json"}

    try:
        resp = requests.get(url, params=params, headers=headers, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            for item in data.get("items", [])[:max_results]:
                owner = item.get("owner", {})
                results.append({
                    "company_name": owner.get("login", "Unknown"),
                    "url": item.get("html_url", ""),
                    "description": (item.get("description") or "")[:200],
                    "language": item.get("language", ""),
                    "stars": item.get("stargazers_count", 0),
                    "source_platform": "github",
                })
        else:
            logger.warning(f"[GitHub API] Status {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        logger.warning(f"[GitHub API] Request failed: {e}")

    return results


# ─────────────────────────────────────────────
# TOOL 2: HuggingFace Organization/Model Search
# ─────────────────────────────────────────────
def search_huggingface(query: str, max_results: int = 5) -> List[Dict[str, str]]:
    """
    Searches HuggingFace Hub API for models/organizations matching hardware/robotics/edge AI.
    Completely free, no auth required.
    """
    results = []
    url = "https://huggingface.co/api/models"
    params = {
        "search": query,
        "sort": "downloads",
        "direction": -1,
        "limit": max_results,
    }

    try:
        resp = requests.get(url, params=params, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            for item in data[:max_results]:
                model_id = item.get("modelId", "")
                org_name = model_id.split("/")[0] if "/" in model_id else model_id
                results.append({
                    "company_name": org_name,
                    "url": f"https://huggingface.co/{model_id}",
                    "description": (item.get("pipeline_tag", "") + " model by " + org_name)[:200],
                    "downloads": item.get("downloads", 0),
                    "source_platform": "huggingface",
                })
        else:
            logger.warning(f"[HuggingFace API] Status {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        logger.warning(f"[HuggingFace API] Request failed: {e}")

    return results


# ─────────────────────────────────────────────
# TOOL 3: Web Search (DuckDuckGo + BS4 fallback)
# ─────────────────────────────────────────────
def search_google_b2b(query: str, max_results: int = 5) -> List[Dict[str, str]]:
    """
    Standard web search using DuckDuckGo for traditional manufacturing/B2B sites.
    Falls back to synthetic results if DDG is rate-limited.
    """
    from src.utils.search_engine import search_web

    raw_results = search_web(query=query, max_results=max_results)
    results = []
    for item in raw_results:
        title = item.get("title", "")
        results.append({
            "company_name": title.split("-")[0].split("|")[0].strip() or "Tech Company",
            "url": item.get("href", ""),
            "description": item.get("body", "")[:200],
            "source_platform": "web_search",
        })
    return results


# ─────────────────────────────────────────────
# TOOL ROUTER — maps directive context to tools
# ─────────────────────────────────────────────
TOOL_REGISTRY = {
    "search_github_repos": {
        "fn": search_github_repos,
        "triggers": ["github", "open source", "ros2", "ros 2", "embedded", "firmware", "cad", "solidworks", "edge ai"],
        "description": "Search GitHub for repositories matching CAD/robotics/edge AI and extract contributor leads.",
    },
    "search_huggingface": {
        "fn": search_huggingface,
        "triggers": ["huggingface", "tinyml", "machine learning", "edge ai", "int8", "quantization", "model", "neural"],
        "description": "Search HuggingFace for organizations deploying hardware/robotics AI models.",
    },
    "search_google_b2b": {
        "fn": search_google_b2b,
        "triggers": [],  # Always available as fallback
        "description": "Standard web search for traditional manufacturing and B2B sites.",
    },
}


class HunterAgent(BaseAgent):
    """
    Advanced lead sourcing agent with multi-tool calling.
    Reads the CEO Directive and intelligently selects which sourcing tools to use.
    """

    def __init__(self, db_path: str = None):
        super().__init__(name="HunterAgent", db_path=db_path or "pipeline.db")

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
                "target_sectors": row["target_sectors"],
            }

        return {
            "id": 0,
            "directive_text": "Target robotics and hardware companies for SolidWorks DFM optimization.",
            "focus_service_lane": "SolidWorks DFM",
            "search_keywords": ["robotics startup mechanical engineer", "SolidWorks DFM hardware startup"],
            "target_sectors": "Robotics, Hardware",
        }

    def select_tools(self, directive: Dict[str, Any]) -> List[str]:
        """
        Intelligently selects which tools to call based on directive context.
        Always includes web search as a baseline.
        """
        context = (
            f"{directive.get('directive_text', '')} "
            f"{directive.get('focus_service_lane', '')} "
            f"{directive.get('target_sectors', '')} "
            f"{' '.join(directive.get('search_keywords', []))}"
        ).lower()

        selected = set()
        for tool_name, tool_info in TOOL_REGISTRY.items():
            for trigger in tool_info["triggers"]:
                if trigger in context:
                    selected.add(tool_name)
                    break

        # Always include web search as baseline
        selected.add("search_google_b2b")
        return list(selected)

    def is_valid_b2b_lead(self, url: str, description: str) -> bool:
        """Filters out non-B2B sites, adult domains, and social media."""
        combined = f"{url} {description}".lower()
        blocked = [
            "porn", "xxx", "adult", "dafont", "font", "wallpaper",
            "torrent", "bilibili", "weibo", "mp3", "video stream",
        ]
        return not any(term in combined for term in blocked)

    def run(self) -> Dict[str, Any]:
        self.log("Reading active CEO directive for tool selection...")
        directive = self.get_active_directive()
        focus_lane = directive.get("focus_service_lane", "SolidWorks DFM")
        keywords = directive.get("search_keywords", ["hardware startup mechanical engineer"])

        # Select tools based on directive
        selected_tools = self.select_tools(directive)
        self.log(f"Selected sourcing tools: {selected_tools} for lane '{focus_lane}'")

        conn = self.get_db()
        cursor = conn.cursor()

        # Existing URLs + emails for deduplication
        cursor.execute("SELECT url FROM leads;")
        existing_urls = {row["url"].lower().rstrip("/") for row in cursor.fetchall()}

        cursor.execute("SELECT email FROM leads WHERE email IS NOT NULL;")
        existing_emails = {row["email"].lower() for row in cursor.fetchall() if row["email"]}

        scouted_leads = []

        for tool_name in selected_tools:
            tool_fn = TOOL_REGISTRY[tool_name]["fn"]
            self.log(f"Calling tool: {tool_name}...")

            for kw in keywords[:3]:  # Cap at 3 keywords per tool to stay within rate limits
                try:
                    raw_results = tool_fn(kw, max_results=3)
                except Exception as e:
                    self.log(f"Tool {tool_name} failed for '{kw}': {e}", level="warning")
                    continue

                for item in raw_results:
                    url = item.get("url", "").strip()
                    if not url or url.lower().rstrip("/") in existing_urls:
                        continue

                    description = item.get("description", "")
                    if not self.is_valid_b2b_lead(url, description):
                        continue

                    company_name = item.get("company_name", "Tech Company")
                    source = item.get("source_platform", tool_name)
                    email = item.get("email")

                    # Skip duplicate emails
                    if email and email.lower() in existing_emails:
                        continue

                    # Use LLM for quick entity extraction on web results
                    decision_maker = "Engineering Lead"
                    if tool_name == "search_google_b2b":
                        sys_prompt = 'Extract company name and target engineering decision-maker title. Output ONLY valid JSON: {"company_name": "...", "decision_maker": "..."}'
                        prompt = f"Title: {company_name}\nURL: {url}\nSnippet: {description}"
                        try:
                            res_raw = self.llm_client.complete(
                                prompt=prompt,
                                system_prompt=sys_prompt,
                                preferred_provider="groq",
                                temperature=0.2,
                            )
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

                    # Insert into leads table
                    try:
                        cursor.execute("""
                            INSERT INTO leads (
                                company_name, url, email, decision_maker,
                                target_keyword, service_lane, source_platform, status
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'scouted');
                        """, (company_name, url, email, decision_maker, kw, focus_lane, source))

                        lead_id = cursor.lastrowid
                        existing_urls.add(url.lower().rstrip("/"))
                        if email:
                            existing_emails.add(email.lower())

                        scouted_leads.append({
                            "id": lead_id,
                            "company_name": company_name,
                            "url": url,
                            "source": source,
                            "service_lane": focus_lane,
                        })
                        self.log(f"Scouted [{source}] lead [ID: {lead_id}]: {company_name}")
                    except Exception as e:
                        self.log(f"Insert failed for {url}: {e}", level="warning")

        conn.commit()
        conn.close()

        self.log(f"Hunter complete. Sourced {len(scouted_leads)} new leads across {len(selected_tools)} tools.")
        return {
            "scouted_count": len(scouted_leads),
            "tools_used": selected_tools,
            "leads": scouted_leads,
        }


if __name__ == "__main__":
    agent = HunterAgent()
    res = agent.run()
    print(json.dumps(res, indent=2))
