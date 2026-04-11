import os
import io
import streamlit as st
from dotenv import load_dotenv
from warnings import filterwarnings
from urllib.parse import urlparse, parse_qs

# ── LangChain YouTube Loader ──────────────────────────────────────────────────
try:
    from langchain_community.document_loaders import YoutubeLoader
except ImportError:
    st.error("Run: pip install langchain-community youtube-transcript-api --upgrade")
    st.stop()

# ── Google Genai (new SDK) ────────────────────────────────────────────────────
try:
    from google import genai as google_genai
except ImportError:
    google_genai = None

# ── OpenAI (used for OpenRouter) ──────────────────────────────────────────────
try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

# ── ReportLab PDF ─────────────────────────────────────────────────────────────
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib.enums import TA_LEFT
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
except ImportError:
    st.error("Run: pip install reportlab")
    st.stop()


# ── Page config ───────────────────────────────────────────────────────────────
def streamlit_config():
    st.set_page_config(page_title="YouTube Summarizer", page_icon="▶️")
    st.markdown("""
        <style>
        [data-testid="stHeader"] { background: rgba(0,0,0,0); }
        .block-container { padding-top: 1rem; }
        </style>
    """, unsafe_allow_html=True)
    st.markdown(
        '<h2 style="text-align:center;">▶️ YouTube Transcript Summarizer</h2>',
        unsafe_allow_html=True,
    )


# ── Video ID extraction ───────────────────────────────────────────────────────
def extract_video_id(url: str) -> str | None:
    try:
        parsed = urlparse(url.strip())
        host = (parsed.hostname or "").replace("www.", "")

        if host == "youtu.be":
            return parsed.path.lstrip("/").split("?")[0]

        if host in ("youtube.com", "m.youtube.com"):
            parts = parsed.path.split("/")
            if len(parts) >= 3 and parts[1] in ("shorts", "embed", "v"):
                return parts[2]
            vid = parse_qs(parsed.query).get("v", [None])[0]
            if vid:
                return vid
    except Exception:
        pass
    return None


# ── Transcript extraction ─────────────────────────────────────────────────────
def extract_transcript(video_url: str, language: list) -> tuple:
    try:
        loader = YoutubeLoader.from_youtube_url(
            video_url,
            add_video_info=False,
            language=language,
        )

        docs = loader.load()

        if not docs:
            st.error("❌ No transcript found. The video may have transcripts disabled.")
            return None, {}

        transcript_text = " ".join(doc.page_content for doc in docs)
        metadata = docs[0].metadata
        return transcript_text, metadata

    except Exception as e:
        error_msg = str(e).lower()

        if "translation" in error_msg or "language" in error_msg:
            st.error("❌ Transcript not available in selected language. Try **'Auto (try all)'**.")
        elif "blocked" in error_msg or "429" in error_msg or "could not retrieve" in error_msg:
            st.error(
                "❌ YouTube blocked the request.\n\n"
                "**Fix:** Run locally, try a different video, or use a VPN.\n\n"
                f"Details: `{e}`"
            )
        elif "disabled" in error_msg:
            st.error("❌ Transcripts are disabled for this video.")
        elif "unavailable" in error_msg or "private" in error_msg:
            st.error("❌ Video is unavailable or private.")
        else:
            st.error(f"❌ Unexpected error: {e}")

        return None, {}


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

    try:
        client = google_genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
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

    try:
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=os.environ["OPENROUTER_API_KEY"],
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


# ── Unified summary dispatcher ────────────────────────────────────────────────
def generate_summary(transcript_text: str, provider: str, openrouter_model: str) -> str | None:
    prompt = (
        "You are a YouTube video summarizer. Summarize the transcript below, "
        "highlighting the key points under clear sub-headings. "
        "Keep it concise (within 500 words).\n\nTranscript:\n"
    )

    if provider == "Gemini (Google)":
        return generate_with_gemini(transcript_text, prompt)
    else:
        return generate_with_openrouter(transcript_text, prompt, openrouter_model)


# ── PDF generator ─────────────────────────────────────────────────────────────
def generate_pdf(summary_text: str) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        rightMargin=inch, leftMargin=inch,
        topMargin=inch, bottomMargin=inch,
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle("CustomTitle", parent=styles["Title"], fontSize=20, spaceAfter=20)
    heading_style = ParagraphStyle("CustomHeading", parent=styles["Heading2"], fontSize=13, spaceAfter=8, spaceBefore=14)
    body_style = ParagraphStyle("CustomBody", parent=styles["Normal"], fontSize=11, leading=16, spaceAfter=8, alignment=TA_LEFT)

    story = [Paragraph("YouTube Video Summary", title_style), Spacer(1, 0.2 * inch)]

    for line in summary_text.split("\n"):
        line = line.strip()
        if not line:
            story.append(Spacer(1, 0.1 * inch))
        elif line.startswith("## "):
            story.append(Paragraph(line[3:], heading_style))
        elif line.startswith("# "):
            story.append(Paragraph(line[2:], heading_style))
        elif line.startswith("**") and line.endswith("**"):
            story.append(Paragraph(f"<b>{line[2:-2]}</b>", body_style))
        elif line.startswith("- ") or line.startswith("* "):
            story.append(Paragraph(f"• {line[2:]}", body_style))
        else:
            story.append(Paragraph(line, body_style))

    doc.build(story)
    buffer.seek(0)
    return buffer.read()


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    filterwarnings("ignore")
    load_dotenv()
    streamlit_config()

    video_url = None
    submit = False

    with st.sidebar:
        st.image(
            "https://raw.githubusercontent.com/gopiashokan/YouTube-Video-Transcript-Summarizer-with-GenAI/main/image/youtube_banner.JPG"
        )

        st.markdown("### ⚙️ Settings")

        # ── AI Provider ──
        provider = st.selectbox(
            "🤖 AI Provider",
            options=["Gemini (Google)", "OpenRouter (Free Models)"],
            index=0,
        )

        openrouter_model = None
        if provider == "OpenRouter (Free Models)":
            model_label = st.selectbox(
                "🧠 Select Model",
                options=list(OPENROUTER_MODELS.keys()),
                index=0,
            )
            openrouter_model = OPENROUTER_MODELS[model_label]

            
                

        st.markdown("---")

        # ── Video input ──
        video_link = st.text_input("🔗 YouTube Video URL")

        lang_options = {
            "English": ["en"],
            "Hindi": ["hi"],
            "Telugu": ["te"],
            "Tamil": ["ta"],
            "Spanish": ["es"],
            "French": ["fr"],
            "German": ["de"],
            "Auto (try all)": ["en", "hi", "te", "ta", "es", "fr", "de"],
        }
        lang_input = st.selectbox(
            "🌐 Transcript Language",
            options=list(lang_options.keys()),
            index=0,
        )
        language_codes = lang_options[lang_input]

        if video_link:
            video_id = extract_video_id(video_link)
            if not video_id:
                st.error("❌ Could not parse video ID. Check your URL.")
                st.stop()
            video_url = video_link.strip()
            submit = st.button("▶️ Summarize")

    # ── Output ────────────────────────────────────────────────────────────────
    if submit and video_url:
        video_id = extract_video_id(video_url)

        _, col, _ = st.columns([0.1, 0.8, 0.1])
        with col:
            st.image(f"https://img.youtube.com/vi/{video_id}/0.jpg", use_container_width=True)

        with st.spinner("📄 Fetching transcript…"):
            transcript, metadata = extract_transcript(video_url, language_codes)

        if not transcript:
            st.stop()

        with st.expander("ℹ️ Video Info", expanded=False):
            st.markdown(f"**Source:** {metadata.get('source', video_url)}")
            st.markdown(f"**Language:** {metadata.get('language', 'N/A')}")

        st.info(f"📝 Transcript length: **{len(transcript.split()):,} words**")

        with st.expander("📃 View raw transcript"):
            st.write(transcript)

        with st.spinner(f"🤖 Generating summary via {provider}…"):
            summary = generate_summary(transcript, provider, openrouter_model)

        if not summary:
            st.stop()

        st.subheader("📋 Summary")
        st.write(summary)

        # ── Download buttons ──────────────────────────────────────────────────
        st.markdown("---")
        st.markdown("**📥 Download Summary**")

        col1, col2, col3 = st.columns(3)
        with col1:
            st.download_button(
                label="📄 TXT",
                data=summary,
                file_name="summary.txt",
                mime="text/plain",
                use_container_width=True,
            )
        with col2:
            st.download_button(
                label="📝 Markdown",
                data=summary,
                file_name="summary.md",
                mime="text/markdown",
                use_container_width=True,
            )
        with col3:
            pdf_bytes = generate_pdf(summary)
            st.download_button(
                label="📑 PDF",
                data=pdf_bytes,
                file_name="summary.pdf",
                mime="application/pdf",
                use_container_width=True,
            )


if __name__ == "__main__":
    main()