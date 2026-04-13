from generative import generate_with_gemini,generate_with_openrouter,OPENROUTER_MODELS

import io
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_LEFT
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer




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
