def build_manufacturing_prompt(design_text: str) -> str:
    return f"""
You are an advanced manufacturing-planning system for defense and precision engineering.

Return ONLY a raw JSON object.
No markdown.
No code fences.
No explanation.
No text before or after the JSON.
The first character must be {{ and the last character must be }}.

Analyze the provided design text and generate a structured manufacturing plan.
Use practical, specific engineering language.
If data is uncertain, provide a reasonable estimate instead of null where possible.

Required JSON schema:
{{
  "plan_summary": "string",
  "design_analysis": "string",
  "cost_estimate": {{
    "min": number,
    "max": number
  }},
  "time_estimate": {{
    "min_days": number,
    "max_days": number
  }},
  "quality_score": number,
  "steps": [
    {{
      "step": number,
      "name": "string",
      "subtitle": "string",
      "description": "string",
      "equipment": ["string"],
      "materials": ["string"],
      "quality_checks": ["string"],
      "risks": [
        {{
          "issue": "string",
          "mitigation": "string"
        }}
      ]
    }}
  ],
  "xai_factors": [
    {{
      "label": "string",
      "score": number
    }}
  ],
  "simulation": {{
    "yield_pct": number,
    "accuracy": "string",
    "optimized_cost": number,
    "optimized_days": number,
    "compliance_pct": number,
    "risk_count": number
  }}
}}

Rules:
- Keep `quality_score` on a 0-100 scale.
- Keep `xai_factors[].score` on a 0-100 scale.
- Include 4-7 manufacturing steps.
- Ensure cost_estimate.min <= cost_estimate.max.
- Ensure time_estimate.min_days <= time_estimate.max_days.
- Keep the response valid JSON for strict parsing.

Design text:
{design_text}
""".strip()
