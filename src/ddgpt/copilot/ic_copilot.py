import os
import json
import cohere

class ICCopilot:
    def __init__(self, model="command-a-03-2025"):
        api_key = os.getenv("CO_API_KEY")

        if not api_key:
            raise RuntimeError(
                "CO_API_KEY not found in environment."
            )

        self.client = cohere.Client(api_key)

        self.model = model

    def generate(self, extracted, flags):
        prompt = f"""
You are an Investment Committee member.

You MUST ONLY use facts explicitly present
in the extracted data and flags.

Do NOT hallucinate missing metrics.

INPUT:

Extracted Data:
{json.dumps(extracted, indent=2)}

Flags:
{json.dumps(flags, indent=2)}

TASK:
1. Identify top 3 risks
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