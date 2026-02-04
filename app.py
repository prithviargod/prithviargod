from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from io import BytesIO
from typing import Dict, List

from flask import Flask, render_template, request, send_file, url_for
from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
import smtplib
from email.message import EmailMessage

app = Flask(__name__)


@dataclass(frozen=True)
class Domain:
    name: str
    questions: List[str]


domains: List[Domain] = [
    Domain(
        name="Vitality & Rigor",
        questions=[
            "I maintain consistent physical energy to sustain high performance across demanding workdays.",
            "I regulate my rest, nutrition, and work rhythms to avoid burnout.",
            "I demonstrate stamina and composure during prolonged periods of pressure.",
            "I avoid lethargy and procrastination in fulfilling my professional responsibilities.",
            "I recover quickly from fatigue or setbacks and return to effective performance.",
        ],
    ),
    Domain(
        name="Cognitive Acumen",
        questions=[
            "I seek to understand issues deeply before forming judgments or opinions.",
            "I actively listen, reflect, and integrate diverse perspectives when making decisions.",
            "I learn quickly from past successes and failures and apply those lessons.",
            "I demonstrate clarity of thought and make decisions under ambiguity and complexity.",
            "I reject faulty reasoning and remain anchored in evidence and sound principles.",
        ],
    ),
    Domain(
        name="Emotional Resilience",
        questions=[
            "I remain calm and composed when faced with conflict or provocation.",
            "I manage stress without allowing it to impair my judgment or behavior.",
            "I regulate anger and do not allow emotional reactions to harm my connections.",
            "I maintain psychological stability during periods of uncertainty or crisis.",
            "I recover emotionally from setbacks without prolonged negativity or withdrawal.",
        ],
    ),
    Domain(
        name="Ethical Integrity",
        questions=[
            "I uphold truthfulness and do not compromise integrity for short-term gain.",
            "My words, intentions, and actions are aligned and consistent.",
            "I avoid unethical shortcuts even under pressure to deliver results.",
            "I am willing to accept personal cost to uphold what is right.",
            "I consciously avoid character flaws such as falsehood, indiscipline, and misuse of power.",
        ],
    ),
    Domain(
        name="Stakeholder Stewardship",
        questions=[
            "I consider the impact of my decisions on all stakeholders, not only immediate outcomes.",
            "I demonstrate fairness and impartiality in allocating opportunities and resources.",
            "I take responsibility for the well-being of people who depend on my leadership.",
            "I balance organizational goals with long-term social and ethical considerations.",
            "I act as a steward of collective welfare rather than a narrow self-interest actor.",
        ],
    ),
    Domain(
        name="Communication & Influence",
        questions=[
            "I communicate with clarity, calmness, and respect even in difficult conversations.",
            "I use measured, thoughtful language rather than reactive or harmful speech.",
            "I am perceived as trustworthy and sincere by colleagues and stakeholders.",
            "I empower my team with clear intent and trust them to execute without unnecessary oversight.",
            "I actively build relationships grounded in mutual respect and goodwill.",
        ],
    ),
    Domain(
        name="Self-Mastery and Execution",
        questions=[
            "I demonstrate self-control over impulses that could undermine my effectiveness.",
            "I convert decisions into timely and disciplined action.",
            "I avoid delays and ensure consistent follow-through on commitments.",
            "I maintain confidentiality and discretion in sensitive matters.",
            "I execute responsibilities with consistency, even when motivation fluctuates.",
        ],
    ),
]

RECOMMENDATIONS = {
    "Vitality & Rigor": [
        "Design a weekly recovery plan with clear boundaries for rest and focused work.",
        "Track energy patterns for two weeks and adjust routines to sustain momentum.",
    ],
    "Cognitive Acumen": [
        "Schedule deep-thinking sessions to analyze complex issues without interruptions.",
        "Use decision logs to capture assumptions and learn from outcomes.",
    ],
    "Emotional Resilience": [
        "Practice a daily reset ritual (breathing, journaling, or reflection) to manage stress.",
        "Identify trigger situations and create response scripts before they happen.",
    ],
    "Ethical Integrity": [
        "Clarify personal leadership principles and revisit them before key decisions.",
        "Invite accountability by sharing commitments with a trusted peer.",
    ],
    "Stakeholder Stewardship": [
        "Map stakeholders for current priorities and note potential long-term impact.",
        "Set quarterly check-ins to review fairness and resource allocation choices.",
    ],
    "Communication & Influence": [
        "Ask for feedback on communication style after important conversations.",
        "Prepare clear intent statements before meetings to reduce ambiguity.",
    ],
    "Self-Mastery and Execution": [
        "Break priorities into weekly execution goals and review progress every Friday.",
        "Create implementation triggers to move decisions into action within 48 hours.",
    ],
}


PDF_STORAGE: Dict[str, bytes] = {}


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        if not name or not email:
            return render_template(
                "index.html",
                domains=domains,
                error="Please provide your name and email.",
                form_data=request.form,
            )

        responses: Dict[str, int] = {}
        missing = []
        for index in range(1, 36):
            field = f"q{index}"
            value = request.form.get(field)
            if value is None:
                missing.append(field)
            else:
                responses[field] = int(value)

        if missing:
            return render_template(
                "index.html",
                domains=domains,
                error="Please answer all 35 questions before submitting.",
                form_data=request.form,
            )

        scores: Dict[str, int] = {}
        classifications: Dict[str, str] = {}
        recommendations: Dict[str, List[str]] = {}
        question_index = 1
        for domain in domains:
            total = 0
            for _ in domain.questions:
                total += responses[f"q{question_index}"]
                question_index += 1
            scores[domain.name] = total
            if total >= 20:
                classifications[domain.name] = "Strength"
            elif total >= 14:
                classifications[domain.name] = "Developing"
            else:
                classifications[domain.name] = "Priority Area"

            if total < 20:
                recommendations[domain.name] = RECOMMENDATIONS[domain.name]

        overall_score = sum(scores.values())
        report_payload = {
            "name": name,
            "email": email,
            "scores": scores,
            "classifications": classifications,
            "recommendations": recommendations,
            "overall_score": overall_score,
        }

        pdf_bytes = build_pdf(report_payload)
        report_id = str(uuid.uuid4())
        PDF_STORAGE[report_id] = pdf_bytes

        email_status = send_email_report(email, name, pdf_bytes)

        return render_template(
            "result.html",
            report_id=report_id,
            report=report_payload,
            email_status=email_status,
        )

    return render_template("index.html", domains=domains, error=None, form_data={})


@app.route("/download/<report_id>")
def download_report(report_id: str):
    pdf_bytes = PDF_STORAGE.get(report_id)
    if not pdf_bytes:
        return "Report not found.", 404

    return send_file(
        BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name="leadership-self-assessment-report.pdf",
    )


def build_pdf(payload: Dict[str, object]) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=LETTER)
    styles = getSampleStyleSheet()
    elements = [Paragraph("Leadership Self-Assessment Report", styles["Title"])]
    elements.append(Spacer(1, 12))
    elements.append(Paragraph(f"Participant: {payload['name']}", styles["Normal"]))
    elements.append(Paragraph(f"Overall Score: {payload['overall_score']} / 175", styles["Normal"]))
    elements.append(Spacer(1, 12))

    table_data = [["Domain", "Score", "Classification"]]
    for domain_name, score in payload["scores"].items():
        table_data.append([
            domain_name,
            f"{score} / 25",
            payload["classifications"][domain_name],
        ])

    table = Table(table_data, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f4e79")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("BACKGROUND", (0, 1), (-1, -1), colors.whitesmoke),
            ]
        )
    )
    elements.append(table)
    elements.append(Spacer(1, 12))

    strengths = [name for name, status in payload["classifications"].items() if status == "Strength"]
    improvements = [
        name
        for name, status in payload["classifications"].items()
        if status != "Strength"
    ]

    elements.append(Paragraph("Strengths", styles["Heading2"]))
    elements.append(Paragraph(", ".join(strengths) if strengths else "None identified.", styles["Normal"]))
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("Improvement Areas", styles["Heading2"]))
    elements.append(
        Paragraph(", ".join(improvements) if improvements else "None identified.", styles["Normal"])
    )
    elements.append(Spacer(1, 10))

    elements.append(Paragraph("Recommended Actions", styles["Heading2"]))
    if payload["recommendations"]:
        for domain_name, actions in payload["recommendations"].items():
            elements.append(Paragraph(f"<b>{domain_name}</b>", styles["Normal"]))
            for action in actions:
                elements.append(Paragraph(f"• {action}", styles["Normal"]))
    else:
        elements.append(Paragraph("No recommendations. Keep up the great work!", styles["Normal"]))

    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()


def send_email_report(recipient: str, name: str, pdf_bytes: bytes) -> str:
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")
    smtp_use_tls = os.getenv("SMTP_USE_TLS", "true").lower() == "true"
    sender = os.getenv("SMTP_SENDER", smtp_user or "")

    if not smtp_host or not smtp_user or not smtp_password or not sender:
        return "Email not sent (missing SMTP configuration)."

    message = EmailMessage()
    message["Subject"] = "Your Leadership Self-Assessment Report"
    message["From"] = sender
    message["To"] = recipient
    message.set_content(
        f"Hello {name},\n\nThank you for completing the leadership self-assessment. "
        "Your PDF report is attached.\n\nRegards,\nLeadership Development Team"
    )
    message.add_attachment(
        pdf_bytes,
        maintype="application",
        subtype="pdf",
        filename="leadership-self-assessment-report.pdf",
    )

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            if smtp_use_tls:
                server.starttls()
            server.login(smtp_user, smtp_password)
            server.send_message(message)
        return "Email sent successfully."
    except (smtplib.SMTPException, OSError):
        return "Email failed to send (check SMTP settings)."


if __name__ == "__main__":
    app.run(debug=True)
