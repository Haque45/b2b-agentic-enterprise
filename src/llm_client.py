"""
LLM Client Wrapper supporting Groq SDK (Llama 3.1 70B/8B) and OpenRouter API (Hermes 3 free tier).

Provides robust error handling, key checking, and fallback mock capabilities.
"""

import os
import json
import logging
import requests
from typing import Optional, Dict, Any

from src.config import GROQ_API_KEY, OPENROUTER_API_KEY

logger = logging.getLogger("LLMClient")


class LLMClient:
    """Unified LLM client interface for Groq and OpenRouter APIs."""

    def __init__(self, groq_api_key: Optional[str] = None, openrouter_api_key: Optional[str] = None):
        self.groq_api_key = groq_api_key or GROQ_API_KEY
        self.openrouter_api_key = openrouter_api_key or OPENROUTER_API_KEY

        # Initialize Groq client if key exists
        self.groq_client = None
        if self.groq_api_key:
            try:
                from groq import Groq
                self.groq_client = Groq(api_key=self.groq_api_key)
            except Exception as e:
                logger.warning(f"Failed to initialize Groq SDK: {e}")

    def call_groq(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: str = "llama-3.1-70b-versatile",
        temperature: float = 0.7,
        max_tokens: int = 500
    ) -> Optional[str]:
        """Calls Groq API using the groq SDK."""
        if not self.groq_client:
            return None

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        # Fallback model list if 70B is unavailable or deprecated
        models_to_try = [model, "llama-3.1-8b-instant", "llama3-70b-8192", "llama3-8b-8192"]

        for m in models_to_try:
            try:
                response = self.groq_client.chat.completions.create(
                    model=m,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
                return response.choices[0].message.content.strip()
            except Exception as e:
                logger.warning(f"Groq API error on model {m}: {e}")
                continue
        return None

    def call_openrouter_hermes(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: str = "nousresearch/hermes-3-llama-3.1-405b:free",
        temperature: float = 0.7,
        max_tokens: int = 500
    ) -> Optional[str]:
        """Calls OpenRouter API using python requests for Hermes 3 free tier."""
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Content-Type": "application/json"
        }
        if self.openrouter_api_key:
            headers["Authorization"] = f"Bearer {self.openrouter_api_key}"

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }

        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                return data["choices"][0]["message"]["content"].strip()
            else:
                logger.warning(f"OpenRouter status {resp.status_code}: {resp.text}")
        except Exception as e:
            logger.warning(f"OpenRouter API request failed: {e}")
        return None

    def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        preferred_provider: str = "groq",
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 500
    ) -> str:
        """
        Unified completion method trying preferred provider first,
        falling back to alternative provider, and finally using deterministic mock generation.
        """
        res = None

        if preferred_provider == "groq" or not self.openrouter_api_key:
            m = model or "llama-3.1-70b-versatile"
            res = self.call_groq(prompt, system_prompt, model=m, temperature=temperature, max_tokens=max_tokens)
            if not res:
                res = self.call_openrouter_hermes(prompt, system_prompt, temperature=temperature, max_tokens=max_tokens)
        else:
            m = model or "nousresearch/hermes-3-llama-3.1-405b:free"
            res = self.call_openrouter_hermes(prompt, system_prompt, model=m, temperature=temperature, max_tokens=max_tokens)
            if not res:
                res = self.call_groq(prompt, system_prompt, temperature=temperature, max_tokens=max_tokens)

        if res:
            return res

        # Fallback Mock logic if no API keys configured or network unreachable
        logger.info("[LLMClient] Operating in deterministic fallback mode (No API keys or cloud offline).")
        return self._mock_completion(prompt, system_prompt)

    def _mock_completion(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Deterministic mock outputs for local development & demonstration when cloud keys are unset."""
        sp = (system_prompt or "").lower()
        p = prompt.lower()

        # Strategy Agent Mock
        if "ceo" in sp or "strategy" in sp or "campaign directive" in p:
            return json.dumps({
                "focus_service_lane": "SolidWorks DFM",
                "allocation_percentage": 80.0,
                "target_sectors": "Robotics Startups, Hardware & CNC Manufacturers",
                "search_keywords": ["SolidWorks DFM hardware startup", "robotics mechanical engineer DFM", "TinyML ESP32 firmware"],
                "directive_text": "Shift 80% of today's search focus to SolidWorks DFM due to a 4% higher positive reply rate in recent metrics.",
                "reasoning": "SolidWorks DFM demonstrates superior positive response conversions (12.5% vs 3.3% for ROS 2)."
            })

        # Sales / Copywriter Agent Mock
        if "copywriter" in sp or "sales agent" in sp or "uet faisalabad" in sp:
            return json.dumps({
                "subject": "SolidWorks DFM Optimization for your Hardware Assembly",
                "email_body": "Hi there,\n\nI saw your team is building custom mechanical enclosures. As a final-year Mechatronics engineer at UET Faisalabad, I specialize in SolidWorks DFM—optimizing complex assemblies for CNC machining and sheet metal to slash production unit cost by 20%.\n\nWould you be open to a 5-minute technical chat this Thursday?\n\nBest,\nHaque",
                "service_lane": "SolidWorks DFM"
            })

        # PR Guardian Agent Mock
        if "compliance" in sp or "pr guardian" in sp:
            return json.dumps({
                "status": "APPROVED",
                "word_count": 58,
                "spam_words_found": [],
                "compliance_notes": "Complies with word count limit (< 75 words) and contains zero spam lexicon terms."
            })

        # Triage Agent Mock
        if "sentiment" in sp or "triage" in sp or "classify" in p:
            if "not interested" in p or "unsubscribe" in p:
                return "Negative"
            elif "cost" in p or "rate" in p or "price" in p:
                return "Pricing"
            else:
                return "Positive"

        return "Default intelligent response generated in fallback mode."
