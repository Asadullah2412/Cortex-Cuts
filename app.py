import os
import streamlit as st
from dotenv import load_dotenv
from warnings import filterwarnings
from urllib.parse import urlparse, parse_qs
import google.genai as genai

# ── LangChain YouTube Loader ──────────────────────────────────────────────────
try:
    from langchain_community.document_loaders import YoutubeLoader
except ImportError:
    st.error("Run: pip install langchain-community youtube-transcript-api --upgrade")
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
            language=language,      # e.g. ["en"] or ["en", "hi", "te"]
            # translation="en"      # ❌ removed — causes issues when unavailable
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
            st.error(
                "❌ Transcript not available in the selected language.\n\n"
                "**Try:** Select **'Auto (try all)'** from the language dropdown."
            )
        elif "blocked" in error_msg or "429" in error_msg:
            st.error("❌ YouTube blocked the request. Try locally or with a VPN.")
        elif "disabled" in error_msg:
            st.error("❌ Transcripts are disabled for this video.")
        else:
            st.error(f"❌ Unexpected error: {e}")

        return None, {}

# ── Gemini summary ────────────────────────────────────────────────────────────
def generate_summary(transcript_text: str):
    try:
        client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])

        prompt = (
            "You are a YouTube video summarizer. Summarize the transcript below, "
            "highlighting the key points under clear sub-headings. "
            "Keep it concise (within 500 words).\n\nTranscript:\n"
        )

        response = client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=prompt + transcript_text,
        )

        return response.text

    except KeyError:
        st.error("❌ GOOGLE_API_KEY not set in your .env file.")
    except Exception as e:
        st.error(f"❌ Gemini error: {e}")
    return None

        # model = genai.GenerativeModel("models/gemini-2.5-flash-lite")

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
            "🌐 Preferred Transcript Language",
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

        # Thumbnail
        _, col, _ = st.columns([0.1, 0.8, 0.1])
        with col:
            st.image(
                f"https://img.youtube.com/vi/{video_id}/0.jpg",
                use_container_width=True,
            )

        # Transcript
        with st.spinner("📄 Fetching transcript…"):
            transcript, metadata = extract_transcript(video_url, language_codes)

        if not transcript:
            st.stop()

        # Basic metadata (source + language — no pytube needed)
        with st.expander("ℹ️ Video Info", expanded=False):
            st.markdown(f"**Source:** {metadata.get('source', video_url)}")
            st.markdown(f"**Language:** {metadata.get('language', 'N/A')}")

        st.info(f"📝 Transcript length: **{len(transcript.split()):,} words**")

        with st.expander("📃 View raw transcript"):
            st.write(transcript)

        # Summary
        with st.spinner("🤖 Generating summary with Gemini…"):
            summary = generate_summary(transcript)

        if not summary:
            st.stop()

        st.subheader("📋 Summary")
        st.write(summary)


if __name__ == "__main__":
    main()