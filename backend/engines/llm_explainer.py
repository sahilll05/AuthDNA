import logging
import asyncio
from config.settings import settings

logger = logging.getLogger(__name__)


class LLMExplainer:
    def __init__(self):
        self._client = None

    def _get_client(self):
        if self._client is None and settings.mistral_api_key:
            try:
                from mistralai import Mistral
                self._client = Mistral(api_key=settings.mistral_api_key)
            except Exception:
                pass
        return self._client

    async def explain(self, score, decision, risk_factors, country, city, hour, dna_match, is_new_user):
        c = self._get_client()
        if c:
            try:
                ft = "; ".join(f"{f['factor']}(+{f['contribution']})" for f in risk_factors[:5])
                prompt = (f"Security analyst: Provide a concise, professional risk summary using Markdown (bolding, lists). "
                          f"START IMMEDIATELY with the facts. NO preamble. NO conversational filler. "
                          f"DO NOT wrap the output in code blocks or triple backticks. Just raw markdown text. "
                          f"Score:{score}/100 Decision:{decision} Country:{country} Hour:{hour} DNA:{dna_match}% New:{is_new_user} Factors:{ft}")
                def call():
                    return c.chat.complete(model="mistral-tiny", messages=[{"role": "system", "content": "You are a professional security analyst. provide raw markdown analysis only. NEVER use code blocks or backticks in your response."}, {"role": "user", "content": prompt}],
                                           max_tokens=150, temperature=0.1).choices[0].message.content.strip()
                content = await asyncio.wait_for(asyncio.to_thread(call), timeout=8.0)
                # Safety: strip code blocks if the LLM ignores instructions
                return content.replace("```markdown", "").replace("```", "").strip()
            except Exception as e:
                logger.warning(f"LLM failed: {e}")
        level = "Low" if score < 30 else "Medium" if score < 60 else "High"
        parts = [f"{level}-risk login"]
        names = [f["factor"] for f in risk_factors]
        if is_new_user: parts.append("first-time user")
        if "is_new_device" in names: parts.append("unknown device")
        if "country_change" in names: parts.append(f"from {country}")
        if "impossible_travel" in names: parts.append("impossible travel")
        if "hour_zscore" in names: parts.append(f"unusual hour {hour}:00")
        if "privilege_gap_score" in names: parts.append(f"high privilege gap")
        if dna_match > 80: parts.append(f"DNA mismatched ({dna_match}% match)")
        return ": ".join([parts[0], ", ".join(parts[1:]) or "no anomalies"]) + "."