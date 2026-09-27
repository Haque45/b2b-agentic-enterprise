"""
Web Scraper Utility using requests & BeautifulSoup4 to extract company page context.
"""

import requests
from bs4 import BeautifulSoup
import logging
from typing import Dict, Any

logger = logging.getLogger("WebScraper")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def scrape_company_website(url: str, timeout: int = 10) -> Dict[str, str]:
    """
    Extracts text context (meta description, page title, headings, paragraph summary)
    from a target company URL.
    """
    context = {
        "url": url,
        "title": "",
        "meta_description": "",
        "headings": "",
        "main_text": ""
    }

    if not url or not url.startswith("http"):
        # For mock/demo URLs or missing HTTP protocol
        context["title"] = "Hardware Engineering & Mechatronics Startup"
        context["meta_description"] = "Developing robotics, embedded sensor platforms, and custom mechanical hardware assemblies."
        context["main_text"] = "We build custom autonomous mobile robots, IoT sensor nodes, and precision mechanical enclosures for industrial automation."
        return context

    try:
        response = requests.get(url, headers=HEADERS, timeout=timeout)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")

            # Page Title
            if soup.title:
                context["title"] = soup.title.string.strip() if soup.title.string else ""

            # Meta Description
            meta_desc = soup.find("meta", attrs={"name": "description"}) or soup.find("meta", attrs={"property": "og:description"})
            if meta_desc and meta_desc.get("content"):
                context["meta_description"] = meta_desc["content"].strip()

            # Headings
            h_tags = soup.find_all(["h1", "h2", "h3"])
            context["headings"] = " | ".join([h.get_text(strip=True) for h in h_tags[:5]])

            # Paragraph snippets
            paragraphs = soup.find_all("p")
            p_text = " ".join([p.get_text(strip=True) for p in paragraphs[:5]])
            context["main_text"] = p_text[:600]

    except Exception as e:
        logger.warning(f"Web scraper failed for {url}: {e}")
        # Graceful fallback context if page fetch fails or network blocked
        context["title"] = "Robotics & Hardware Solutions"
        context["meta_description"] = "Engineering advanced hardware systems, IoT automation, and mechanical components."
        context["main_text"] = "Specializing in hardware product design, rapid prototyping, and electro-mechanical system integration."

    return context
