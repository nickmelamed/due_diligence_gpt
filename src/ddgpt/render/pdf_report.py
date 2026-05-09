from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    PageBreak
)

from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import letter

def render_ic_pdf(output_path: str, memo: str):
    styles = getSampleStyleSheet()

    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter
    )

    story = []

    for line in memo.split("\n"):
        if not line.strip():
            story.append(Spacer(1, 12))
            continue

        story.append(
            Paragraph(line, styles["BodyText"])
        )

    doc.build(story)