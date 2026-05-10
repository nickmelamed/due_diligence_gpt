from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    PageBreak
)

from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors

from markdown2 import markdown

import re

def clean_markdown(md: str):
    md = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", md)
    md = re.sub(r"(?m)^# (.*?)$", r"<font size=20><b>\1</b></font>", md)
    md = re.sub(r"(?m)^## (.*?)$", r"<font size=16><b>\1</b></font>", md)

    return md

def render_ic_pdf(output_path: str, memo: str):
    styles = getSampleStyleSheet()

    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40
    )

    story = []

    cleaned = clean_markdown(memo)

    blocks = cleaned.split("\n")

    for block in blocks:
        if not block.strip():
            story.append(Spacer(1, 10))
            continue

        story.append(
            Paragraph(
                block,
                styles["BodyText"]
            )
        )

    doc.build(story)