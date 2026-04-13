import streamlit as st
from google import genai as google_genai
from openai import OpenAI
import os

# import streamlit as st

# Works both locally and on Streamlit Cloud
def get_secret(key: str) -> str:
    """Read from st.secrets (Streamlit Cloud) or os.environ (local)."""
    try:
        return st.secrets[key]
    except (FileNotFoundError, KeyError):
        return os.getenv(key, "")

# ── Gemini summary ────────────────────────────────────────────────────────────
def generate_with_gemini(transcript_text: str, prompt: str) -> str | None:
    if google_genai is None:
        st.error("❌ google-genai not installed. Run: pip install google-genai")
        return None

    models_to_try = [
        "gemini-2.0-flash",
        "gemini-2.0-flash-lite",
        "gemini-2.5-flash-lite",
    ]
    api_key = get_secret("GOOGLE_API_KEY")
    try:
        client = google_genai.Client(api_key=api_key)
    except KeyError:
        st.error("❌ GOOGLE_API_KEY not set. Run: export GOOGLE_API_KEY=your_key")
        return None

    for model in models_to_try:
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt + transcript_text,
            )
            st.caption(f"✅ Used Gemini model: `{model}`")
            return response.text
        except Exception as e:
            if "429" in str(e) or "quota" in str(e).lower():
                st.warning(f"⚠️ `{model}` quota exceeded — trying next model...")
                continue
            else:
                st.error(f"❌ Gemini error with `{model}`: {e}")
                return None

    st.error(
        "❌ All Gemini models quota exhausted.\n\n"
        "**Switch to OpenRouter** in the sidebar or try again tomorrow."
    )
    return None


# ── OpenRouter summary ────────────────────────────────────────────────────────
OPENROUTER_MODELS = {
    "Auto (Best Free Model)":     "openrouter/free",           # ✅ always works
    "Llama 3.3 70B (Free)":       "meta-llama/llama-3.3-70b-instruct:free",
    "Mistral Small 3.1 (Free)":   "mistralai/mistral-small-3.1-24b-instruct:free",
    "DeepSeek R1 (Free)":         "deepseek/deepseek-r1:free",
    "Gemma 3 12B (Free)":         "google/gemma-3-12b-it:free",
}

def generate_with_openrouter(transcript_text: str, prompt: str, model: str) -> str | None:
    if OpenAI is None:
        st.error("❌ openai not installed. Run: pip install openai")
        return None
    api_key = get_secret("OPENROUTER_API_KEY")
    try:
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
        )

        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt + transcript_text}],
        )

        st.caption(f"✅ Used OpenRouter model: `{model}`")
        return response.choices[0].message.content

    except KeyError:
        st.error("❌ OPENROUTER_API_KEY not set. Run: export OPENROUTER_API_KEY=your_key")
    except Exception as e:
        st.error(f"❌ OpenRouter error: {e}")
    return None
