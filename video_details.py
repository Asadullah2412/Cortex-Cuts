from urllib.parse import urlparse, parse_qs
from langchain_community.document_loaders import YoutubeLoader
import streamlit as st


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