"""
Generate a contextual reply with the Groq API (OpenAI-compatible chat endpoint).

Returns None on any problem (no key, network error, bad response) so the caller
can fall back to a hand-written template. We pass the real on-chain numbers in
the prompt and instruct the model to use ONLY those, so it can't invent figures.
"""

from __future__ import annotations
import os
import requests

GROQ_URL   = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")

SYSTEM_PROMPT = (
    "You are xINJ, a friendly X (Twitter) bot for the Injective blockchain "
    "ecosystem. Reply to the user's tweet in a warm, concise, hype-but-credible "
    "tone. Rules:\n"
    "- Max 240 characters. One short paragraph, no line breaks needed.\n"
    "- Only state numbers that are given to you in FACTS. Never invent figures, "
    "prices, or promises.\n"
    "- If no relevant FACTS are given, give a friendly engagement reply without "
    "specific numbers.\n"
    "- Do NOT give financial advice or price predictions.\n"
    "- You may use 1-2 emojis and the #Injective hashtag. Do not @-mention anyone."
)


def _facts_block(metrics: dict | None) -> str:
    if not metrics:
        return "FACTS: (none available)"
    def fmt(v, p="$"):
        if v is None:
            return "N/A"
        if v >= 1_000_000:
            return f"{p}{v/1e6:.2f}M"
        if v >= 1_000:
            return f"{p}{v/1e3:.1f}K"
        return f"{p}{v:,.0f}"
    price = metrics.get("inj_price")
    return (
        "FACTS (latest weekly snapshot):\n"
        f"- INJ price: {('$%.2f' % price) if price else 'N/A'}\n"
        f"- Total TVL: {fmt(metrics.get('tvl_usd'))}\n"
        f"- DEX volume 7D: {fmt(metrics.get('dex_volume_7d'))}\n"
        f"- Chain fees 7D: {fmt(metrics.get('chain_fees_7d'))}\n"
        f"- Revenue/burn 7D: {fmt(metrics.get('chain_revenue_7d'))}"
    )


def groq_reply(tweet_text: str, metrics: dict | None) -> str | None:
    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    if not api_key:
        return None

    user_msg = (
        f"{_facts_block(metrics)}\n\n"
        f"Someone tweeted at you:\n\"{tweet_text}\"\n\n"
        f"Write a single reply tweet."
    )

    try:
        resp = requests.post(
            GROQ_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": GROQ_MODEL,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                "temperature": 0.7,
                "max_tokens": 120,
            },
            timeout=20,
        )
        resp.raise_for_status()
        text = resp.json()["choices"][0]["message"]["content"].strip()
        # Strip wrapping quotes the model sometimes adds, and trim to tweet length
        text = text.strip('"').strip()
        if not text:
            return None
        return text[:270]
    except Exception as e:
        print(f"Groq reply failed, falling back to template: {e}")
        return None
