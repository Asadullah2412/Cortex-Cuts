
import streamlit as st
from dotenv import load_dotenv
from warnings import filterwarnings
from video_details import extract_video_id,extract_transcript
from summary_pdf import generate_summary,generate_pdf

from generative import OPENROUTER_MODELS


# ── Page config ───────────────────────────────────────────────────────────────
def streamlit_config():
    st.set_page_config(page_title="cortex cuts-YouTube Summarizer", page_icon="▶️")
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