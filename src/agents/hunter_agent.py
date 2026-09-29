"""
Hunter Agent (hunter_agent.py).

Advanced lead sourcing agent equipped with tools to discover company leads:
1. search_github_repos(query)  — GitHub REST API (company website & repo info only, NO personal emails)
2. search_huggingface(query)   — HuggingFace Hub API (company website & model info only, NO personal emails)
3. search_google_b2b(query)    — DuckDuckGo web search for B2B company websites (NO personal emails)
4. find_business_contact(website_url) — Official site contact page scraper (extracts role/published business emails)

All discovered leads without confirmed emails are stored with status='needs_contact_lookup'.
Leads with confirmed company site emails are tagged email_source='company_site' and status='scouted'.
"""

import json
import re
import time
import random
import logging
import urllib.parse
import urllib.robotparser
import requests
from bs4 import BeautifulSoup
from typing import Dict, Any, List, Optional

from src.agents.base_agent import BaseAgent

logger = logging.getLogger("HunterAgent")

ROLE_EMAIL_PREFIXES = [
    "info@", "contact@", "hello@", "sales@", "support@", "enquiries@",
    "inquiries@", "office@", "admin@", "help@", "team@", "biz@", "general@"
]

JUNK_DOMAINS = {
    "example.com", "domain.com", "email.com", "sentry.io", "wix.com",
    "wordpress.org", "schema.org", "github.com", "google.com", "facebook.com",
    "twitter.com", "linkedin.com", "instagram.com", "youtube.com"
}

INVALID_EXTENSIONS = (
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".css", ".js", ".webp", ".pdf"
)

BLOCKED_DOMAINS = [
    "github.com", "huggingface.co", "youtube.com", "wikipedia.org",
    "linkedin.com", "twitter.com", "x.com", "reddit.com", "medium.com",
    "stackoverflow.com", "facebook.com", "instagram.com"
]


def is_allowed_by_robots(target_url: str, user_agent: str = "*") -> bool:
    """Checks if target_url is permitted by robots.txt."""
    try:
        parsed = urllib.parse.urlparse(target_url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        rp = urllib.robotparser.RobotFileParser()
        resp = requests.get(robots_url, headers={"User-Agent": user_agent}, timeout=3)
        if resp.status_code == 200:
            rp.parse(resp.text.splitlines())
            return rp.can_fetch(user_agent, target_url)
        return True
    except Exception:
        return True


def find_business_contact(website_url: str) -> Optional[str]:
    """
    Fetches the website's /contact, /about, and homepage pages only.
    Extracts a business email strictly from mailto: links or plainly published text.
    Prefers role addresses (info@, contact@, hello@, sales@) over personal names.
    Returns None if nothing is found (never guesses or pattern-generates).
    """
    if not website_url or not isinstance(website_url, str):
        return None

    if not website_url.startswith("http://") and not website_url.startswith("https://"):
        website_url = "https://" + website_url

    try:
        parsed_base = urllib.parse.urlparse(website_url)
        base_domain_url = f"{parsed_base.scheme}://{parsed_base.netloc}".rstrip("/")
    except Exception:
        return None

    target_paths = ["", "/contact", "/about"]
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) B2BBusinessContactFinder/1.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    discovered_emails = []

    for idx, path in enumerate(target_paths):
        full_page_url = base_domain_url + path

        if not is_allowed_by_robots(full_page_url):
            logger.info(f"[find_business_contact] Disallowed by robots.txt: {full_page_url}")
            continue

        if idx > 0:
            time.sleep(random.uniform(2.0, 3.0))

        try:
            resp = requests.get(full_page_url, headers=headers, timeout=10, allow_redirects=True)
            if resp.status_code != 200:
                continue

            html = resp.text
            soup = BeautifulSoup(html, "html.parser")

            # Extract mailto links
            for a_tag in soup.find_all("a", href=True):
                href = a_tag["href"].strip()
                if href.lower().startswith("mailto:"):
                    raw_email = href.split("mailto:")[1].split("?")[0].strip()
                    discovered_emails.append(raw_email)

            # Extract published text emails
            text_content = soup.get_text(separator=" ")
            matches = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text_content)
            discovered_emails.extend(matches)

        except Exception as e:
            logger.debug(f"[find_business_contact] Error fetching {full_page_url}: {e}")
            continue

    # Clean & validate found emails
    valid_emails = []
    for email in set(discovered_emails):
        email_clean = email.lower().strip().rstrip(".")
        if any(email_clean.endswith(ext) for ext in INVALID_EXTENSIONS):
            continue
        parts = email_clean.split("@")
        if len(parts) != 2:
            continue
        domain_part = parts[1]
        if domain_part in JUNK_DOMAINS or "." not in domain_part:
            continue
        valid_emails.append(email_clean)

    if not valid_emails:
        return None

    # Prefer role addresses (info@, contact@, hello@, sales@, etc.)
    for email in valid_emails:
        for prefix in ROLE_EMAIL_PREFIXES:
            if email.startswith(prefix):
                return email

    return valid_emails[0]


def search_github_repos(query: str, max_results: int = 5) -> List[Dict[str, str]]:
    """
    Searches GitHub REST API for repos/orgs matching query.
    NEVER extracts personal/commit emails.
    Only captures candidate if a public company WEBSITE URL is listed.
    """
    results = []
    url = "https://api.github.com/search/repositories"
    params = {"q": query, "sort": "stars", "order": "desc", "per_page": max_results}
    headers = {"Accept": "application/vnd.github+json"}

    try:
        resp = requests.get(url, params=params, headers=headers, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            for item in data.get("items", []):
                owner = item.get("owner", {})
                owner_login = owner.get("login", "")

                # Check homepage field for website URL
                homepage = (item.get("homepage") or "").strip()
                website_url = None
                if homepage and homepage.startswith("http") and "github.com" not in homepage.lower():
                    website_url = homepage

                # If homepage not found, check owner profile
                if not website_url and owner_login:
                    try:
                        user_resp = requests.get(f"https://api.github.com/users/{owner_login}", headers=headers, timeout=5)
                        if user_resp.status_code == 200:
                            blog = (user_resp.json().get("blog") or "").strip()
                            if blog:
                                if not blog.startswith("http"):
                                    blog = "https://" + blog
                                if "github.com" not in blog.lower():
                                    website_url = blog
                    except Exception:
                        pass

                # Skip if no external public company website URL was found
                if not website_url:
                    continue

                desc = (item.get("description") or f"Open source repository by {owner_login}")[:200]
                lang = item.get("language")
                note = f"GitHub project ({lang or 'Tech'}): {desc}" if lang else f"GitHub project: {desc}"

                results.append({
                    "company_name": owner_login or item.get("name", "Tech Company"),
                    "url": website_url,
                    "description": note,
                    "source_platform": "github",
                })
                if len(results) >= max_results:
                    break
        else:
            logger.warning(f"[GitHub API] Status {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        logger.warning(f"[GitHub API] Request failed: {e}")

    return results


def search_huggingface(query: str, max_results: int = 5) -> List[Dict[str, str]]:
    """
    Searches HuggingFace Hub API for models/orgs matching query.
    NEVER extracts personal emails.
    Only captures candidate if a public company WEBSITE URL is listed.
    """
    results = []
    url = "https://huggingface.co/api/models"
    params = {"search": query, "sort": "downloads", "direction": -1, "limit": max_results * 2}

    try:
        resp = requests.get(url, params=params, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            for item in data:
                model_id = item.get("modelId", "")
                org_name = model_id.split("/")[0] if "/" in model_id else model_id

                website_url = None
                # Check organization profile for website
                try:
                    org_resp = requests.get(f"https://huggingface.co/api/organizations/{org_name}", timeout=5)
                    if org_resp.status_code == 200:
                        site = (org_resp.json().get("website") or "").strip()
                        if site and site.startswith("http") and "huggingface.co" not in site.lower():
                            website_url = site
                except Exception:
                    pass

                # If user profile fallback
                if not website_url:
                    try:
                        user_resp = requests.get(f"https://huggingface.co/api/users/{org_name}", timeout=5)
                        if user_resp.status_code == 200:
                            site = (user_resp.json().get("website") or "").strip()
                            if site and site.startswith("http") and "huggingface.co" not in site.lower():
                                website_url = site
                    except Exception:
                        pass

                # Skip if no external public company website URL was found
                if not website_url:
                    continue

                tag = item.get("pipeline_tag", "AI/hardware model")
                note = f"HuggingFace org {org_name} deploying {tag} models"

                results.append({
                    "company_name": org_name,
                    "url": website_url,
                    "description": note,
                    "source_platform": "huggingface",
                })
                if len(results) >= max_results:
                    break
        else:
            logger.warning(f"[HuggingFace API] Status {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        logger.warning(f"[HuggingFace API] Request failed: {e}")

    return results


def search_google_b2b(query: str, max_results: int = 5) -> List[Dict[str, str]]:
    """
    Standard web search using DuckDuckGo for B2B company sites.
    Only captures candidate if a valid public company WEBSITE URL is present.
    """
    from src.utils.search_engine import search_web

    raw_results = search_web(query=query, max_results=max_results * 2)
    results = []
    for item in raw_results:
        href = item.get("href", "").strip()
        if not href or any(b in href.lower() for b in BLOCKED_DOMAINS):
            continue

        title = item.get("title", "")
        comp_name = title.split("-")[0].split("|")[0].strip() or "Tech Company"
        body = item.get("body", "")[:200]

        results.append({
            "company_name": comp_name,
            "url": href,
            "description": f"B2B site: {body}",
            "source_platform": "web_search",
        })
        if len(results) >= max_results:
            break

    return results


def search_yc_directory(query: str, max_results: int = 5) -> List[Dict[str, str]]:
    """
    Searches Y Combinator public company directory pages (ycombinator.com/companies
    or workatastartup.com/companies) for startups matching query.
    Extracts company name, website URL, and relevance note (NO personal emails).
    """
    from src.utils.search_engine import search_web

    search_query = f"site:ycombinator.com/companies {query}"
    raw_results = search_web(query=search_query, max_results=max_results * 2)
    results = []

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) B2BYCSearch/1.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    for item in raw_results:
        href = item.get("href", "").strip()
        title = item.get("title", "")
        body = item.get("body", "")[:200]

        comp_name = title.split("-")[0].split("|")[0].strip()
        comp_name = re.sub(r'(?i)\s*site:ycombinator\.com.*', '', comp_name).strip() or "YC Startup"

        website_url = None

        if href and not any(b in href.lower() for b in BLOCKED_DOMAINS):
            website_url = href
        elif href and "ycombinator.com/companies/" in href.lower():
            try:
                resp = requests.get(href, headers=headers, timeout=8)
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    for a_tag in soup.find_all("a", href=True):
                        link = a_tag["href"].strip()
                        if link.startswith("http") and not any(b in link.lower() for b in BLOCKED_DOMAINS):
                            website_url = link
                            break
            except Exception as e:
                logger.debug(f"[search_yc_directory] Profile fetch failed for {href}: {e}")

        if not website_url:
            continue

        note = f"YC funded startup ({query}): {body}" if body else f"YC funded startup ({query})"

        results.append({
            "company_name": comp_name,
            "url": website_url,
            "description": note,
            "source_platform": "ycombinator",
        })
        if len(results) >= max_results:
            break

    return results


TOOL_REGISTRY = {
    "search_github_repos": {
        "fn": search_github_repos,
        "triggers": ["github", "open source", "ros2", "ros 2", "embedded", "firmware", "cad", "solidworks", "edge ai"],
        "description": "Search GitHub for repositories with public company websites.",
    },
    "search_huggingface": {
        "fn": search_huggingface,
        "triggers": ["huggingface", "tinyml", "machine learning", "edge ai", "int8", "quantization", "model", "neural"],
        "description": "Search HuggingFace for organizations with public company websites.",
    },
    "search_google_b2b": {
        "fn": search_google_b2b,
        "triggers": [],
        "description": "Standard web search for traditional manufacturing and B2B sites.",
    },
    "search_yc_directory": {
        "fn": search_yc_directory,
        "triggers": ["startup", "yc", "funded", "y combinator", "accelerator"],
        "description": "Search Y Combinator directory for funded hardware/robotics startups.",
    },
    "find_business_contact": {
        "fn": find_business_contact,
        "triggers": [],
        "description": "Extracts business contact email from official company website pages.",
    },
}


class HunterAgent(BaseAgent):
    """
    Advanced lead sourcing agent with multi-tool calling and ethical business contact lookup.
    Reads active CEO Directive to select tools, discovers company sites, and checks contact pages.
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
            for trigger in tool_info.get("triggers", []):
                if trigger in context:
                    selected.add(tool_name)
                    break

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

        selected_tools = self.select_tools(directive)
        self.log(f"Selected sourcing tools: {selected_tools} for lane '{focus_lane}'")

        conn = self.get_db()
        cursor = conn.cursor()

        cursor.execute("SELECT url FROM leads;")
        existing_urls = {row["url"].lower().rstrip("/") for row in cursor.fetchall()}

        cursor.execute("SELECT email FROM leads WHERE email IS NOT NULL;")
        existing_emails = {row["email"].lower() for row in cursor.fetchall() if row["email"]}

        scouted_leads = []

        for tool_name in selected_tools:
            if tool_name == "find_business_contact":
                continue

            tool_fn = TOOL_REGISTRY[tool_name]["fn"]
            self.log(f"Calling tool: {tool_name}...")

            for kw in keywords[:3]:
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

                    self.log(f"Checking business contact for {company_name} ({url})...")
                    business_email = find_business_contact(url)

                    if business_email and business_email.lower() in existing_emails:
                        self.log(f"Skipping lead {company_name}: email {business_email} already exists.", level="info")
                        continue

                    if business_email:
                        status = "scouted"
                        email_source = "company_site"
                    else:
                        status = "needs_contact_lookup"
                        email_source = None

                    decision_maker = "Engineering Lead"

                    try:
                        cursor.execute("""
                            INSERT INTO leads (
                                company_name, url, email, email_source, decision_maker,
                                target_keyword, service_lane, source_platform, status, compliance_notes
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                        """, (
                            company_name, url, business_email, email_source, decision_maker,
                            kw, focus_lane, source, status, description[:200]
                        ))

                        lead_id = cursor.lastrowid
                        existing_urls.add(url.lower().rstrip("/"))
                        if business_email:
                            existing_emails.add(business_email.lower())

                        scouted_leads.append({
                            "id": lead_id,
                            "company_name": company_name,
                            "url": url,
                            "email": business_email,
                            "email_source": email_source,
                            "source": source,
                            "service_lane": focus_lane,
                            "status": status,
                        })
                        self.log(f"Inserted [{source}] lead [ID: {lead_id}]: {company_name} (status: {status}, email: {business_email})")
                    except Exception as e:
                        self.log(f"Insert failed for {url}: {e}", level="warning")

        conn.commit()
        conn.close()

        self.log(f"Hunter complete. Processed {len(scouted_leads)} leads across {len(selected_tools)} tools.")
        return {
            "scouted_count": len(scouted_leads),
            "tools_used": selected_tools,
            "leads": scouted_leads,
        }


if __name__ == "__main__":
    agent = HunterAgent()
    res = agent.run()
    print(json.dumps(res, indent=2))
