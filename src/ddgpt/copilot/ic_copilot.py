import os
import json
import cohere

from ddgpt.report.ic_memo import generate_ic_summary


class ICCopilot:
    def __init__(self, model="command-a-03-2025"):
        self.model = model

        api_key = os.getenv("CO_API_KEY")

        # No hard failure when a key isn't configured: fall back to the
        # deterministic, template-based memo (report.ic_memo) rather than
        # taking down the whole pipeline over a missing LLM credential.
        self.client = cohere.Client(api_key) if api_key else None

    def generate(self, extracted, flags, recommendation=None):
        if self.client is None:
            return generate_ic_summary(extracted, flags, recommendation=recommendation)

        recommendation_instruction = ""
        if recommendation:
            recommendation_instruction = f"""
The recommendation has ALREADY been decided by a deterministic rules engine:
**{recommendation["decision"]}** (confidence {recommendation["confidence"]:.2f}).
State this recommendation verbatim in section 3 -- do not substitute your own judgment.
"""

        prompt = f"""
You are an Investment Committee member.

You MUST ONLY use facts explicitly present
in the extracted data and flags.

Do NOT hallucinate missing metrics.
{recommendation_instruction}
INPUT:

Extracted Data:
{json.dumps(extracted, indent=2)}

Flags:
{json.dumps(flags, indent=2)}

TASK:
1. Identify top 3 risks. Use ONLY the flags listed above as the basis for
   risk judgments -- do not introduce a risk (e.g. "fee X is high") that was
   not raised as a flag; extracted data may be cited as supporting evidence
   but is not itself a source of new risk claims.
2. Identify inconsistencies
3. Provide recommendation:
   APPROVE / INVESTIGATE / PASS
4. Justify using evidence

Return professional markdown suitable
for an institutional IC memo.
"""

        resp = self.client.chat(
            model=self.model,
            message=prompt,
            temperature=0.2
        )

        return resp.text
