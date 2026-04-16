import os
import json
import cohere

class ICCopilot:
    def __init__(self, model="command-a-03-2025"):
        self.client = cohere.Client(os.getenv("CO_API_KEY"))
        self.model = model

    def generate(self, extracted, flags):
        prompt = f"""
You are an Investment Committee member.

INPUT:
Extracted Data:
{json.dumps(extracted, indent=2)}

Flags:
{json.dumps([f.dict() for f in flags], indent=2)}

TASK:
1. Identify top 3 risks
2. Identify inconsistencies
3. Provide recommendation: APPROVE / INVESTIGATE / PASS
4. Justify using evidence

Return structured markdown.
"""

        resp = self.client.chat(
            model=self.model,
            message=prompt,
            temperature=0.3
        )

        return resp.text