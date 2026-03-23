# backend/engines/llm_explainer.py
"""
LLM Explainer — uses Mistral AI (free) to generate 
human-readable risk explanations.
"""
import httpx
from typing import Dict, List
from config.settings import settings
from models.schemas import RiskFactor


class LLMExplainer:
    """Generate natural language explanations using Mistral AI"""

    MISTRAL_API_URL = "https://api.mistral.ai/v1/chat/completions"

    @staticmethod
    async def explain(
        score: float,
        decision: str,
        risk_factors: List[RiskFactor],
        metadata: Dict,
        dna_match: float
    ) -> str:
        """
        Generate a concise human-readable explanation of the risk assessment.
        Falls back to template if Mistral is unavailable.
        """
        # Build context for LLM
        factors_text = "\n".join([
            f"- {f.factor}: {f.description} (contribution: {f.contribution:+.1f})"
            for f in risk_factors
        ])

        prompt = f"""You are a cybersecurity risk analyst. Explain this login risk assessment in ONE concise sentence (max 30 words).

Risk Score: {score}/100
Decision: {decision}
DNA Match: {dna_match}%
Country: {metadata.get('country', 'Unknown')}
City: {metadata.get('city', 'Unknown')}
Hour: {metadata.get('hour', 'Unknown')}:00
New User: {metadata.get('is_new_user', False)}

Risk Factors:
{factors_text}

Write a clear, non-technical explanation. Example: "Normal login from known device at usual time from India" or "Suspicious: new device from unusual country with failed attempts"."""

        try:
            if not settings.MISTRAL_API_KEY:
                return LLMExplainer._template_explain(
                    score, decision, risk_factors, metadata, dna_match
                )

            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.post(
                    LLMExplainer.MISTRAL_API_URL,
                    headers={
                        "Authorization": f"Bearer {settings.MISTRAL_API_KEY}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "mistral-tiny",
                        "messages": [
                            {"role": "user", "content": prompt}
                        ],
                        "max_tokens": 60,
                        "temperature": 0.3
                    }
                )

                if response.status_code == 200:
                    data = response.json()
                    explanation = data["choices"][0]["message"]["content"].strip()
                    # Clean up — remove quotes if present
                    explanation = explanation.strip('"\'')
                    return explanation

        except Exception as e:
            print(f"Mistral API error: {e}")

        # Fallback to template
        return LLMExplainer._template_explain(
            score, decision, risk_factors, metadata, dna_match
        )

    @staticmethod
    def _template_explain(
        score: float,
        decision: str,
        risk_factors: List[RiskFactor],
        metadata: Dict,
        dna_match: float
    ) -> str:
        """Template-based fallback explanation"""
        country = metadata.get("country", "Unknown")
        city = metadata.get("city", "")
        is_new = metadata.get("is_new_user", False)

        if score <= 30:
            if is_new:
                return f"First-time login from {country}. Low risk signals detected."
            return f"Normal login from known location ({country}). Behavior matches profile."

        elif score <= 60:
            top_risk = risk_factors[0].description if risk_factors else "moderate risk signals"
            return f"Moderate risk: {top_risk}. Verification recommended."

        elif score <= 80:
            top_risks = ", ".join([f.factor for f in risk_factors[:2]])
            return f"High risk detected: {top_risks}. Additional verification required."

        else:
            top_risks = ", ".join([f.factor for f in risk_factors[:3]])
            return f"Critical risk: {top_risks}. Login blocked for security."