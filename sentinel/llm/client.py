"""
llm/client.py
-------------
Thin wrapper so the rest of the codebase never imports langchain_groq /
langchain_openai directly. Reads provider config from environment
variables (see .env.example).

If no API key is configured, `chat()` falls back to a deterministic mock
so the pipeline is still runnable end-to-end for local testing/demoing
without any credentials. Set SENTINEL_FORCE_MOCK=1 to force this even
with a key present.
"""
from __future__ import annotations
import os


def _mock_reply(prompt: str) -> str:
    """A deliberately simple stand-in used only when no LLM is configured.
    It's not meant to be smart — the pattern-matching NL2SQL fallback and
    the TF-IDF RAG backend carry the actual offline demo; this just keeps
    any direct chat() call from crashing."""
    return (
        "[MOCK LLM — no GROQ_API_KEY / OPENAI_API_KEY configured] "
        "Set an API key in .env to get real model output for: "
        f"{prompt[:120]}..."
    )


def get_chat_model():
    """Returns a LangChain-compatible chat model, or None if running in
    mock mode."""
    if os.getenv("SENTINEL_FORCE_MOCK") == "1":
        return None

    if os.getenv("OPENROUTER_API_KEY"):
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=os.getenv("SENTINEL_MODEL", "openai/gpt-oss-20b:free"),
            api_key=os.getenv("OPENROUTER_API_KEY"),
            base_url="https://openrouter.ai/api/v1",
            temperature=0,
            default_headers={
                # OpenRouter uses these for its (optional) app leaderboard/rankings;
                # harmless to include, safe to remove.
                "HTTP-Referer": os.getenv("OPENROUTER_SITE_URL", "https://sentinel.local"),
                "X-Title": "Sentinel",
            },
        )

    if os.getenv("GROQ_API_KEY"):
        from langchain_groq import ChatGroq

        return ChatGroq(
            model=os.getenv("SENTINEL_MODEL", "openai/gpt-oss-20b"),
            temperature=0,
        )

    if os.getenv("OPENAI_API_KEY"):
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=os.getenv("SENTINEL_MODEL", "gpt-4o-mini"),
            temperature=0,
        )

    return None


def chat(prompt: str, system: str | None = None) -> str:
    model = get_chat_model()
    if model is None:
        return _mock_reply(prompt)

    messages = []
    if system:
        messages.append(("system", system))
    messages.append(("human", prompt))
    response = model.invoke(messages)
    return response.content


def get_embeddings(texts: list[str]) -> list[list[float]]:
    """Only used by the optional FAISS RAG backend."""
    if os.getenv("OPENAI_API_KEY"):
        from langchain_openai import OpenAIEmbeddings

        model = OpenAIEmbeddings()
        return model.embed_documents(texts)
    raise RuntimeError("No embeddings provider configured (need OPENAI_API_KEY).")
