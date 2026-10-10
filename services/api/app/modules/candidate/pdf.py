"""Private, in-memory export with an explicit allowlist; never serialize ORM objects."""
from html import escape
from io import BytesIO
from pathlib import Path
from threading import Lock

from fastapi import APIRouter, HTTPException, Request, Response
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from app.modules.assessments.qualification import qualification
from app.modules.auth.dependencies import AuthSession
from app.modules.candidate.router import CandidateUser
from app.modules.candidate.schemas import contact_free
from app.modules.candidate.service import get_profile

router = APIRouter(tags=["candidate"])
FONT_PATH = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
_font_lock = Lock()


def render_profile(name: str | None, specialization: str | None, skills: list[str],
                   verified_grade: str | None, verified_specialization: str | None) -> bytes:
    # Register once under a lock: independent concurrent documents share the font registry.
    with _font_lock:
        if "ProfileDejaVu" not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont("ProfileDejaVu", str(FONT_PATH)))
    stream = BytesIO()
    document = SimpleDocTemplate(stream, pagesize=A4, rightMargin=48, leftMargin=48,
                                 topMargin=48, bottomMargin=48,
                                 title="Профиль кандидата", author="FSP Platform",
                                 subject="", creator="FSP Platform")
    body = ParagraphStyle("body", fontName="ProfileDejaVu", fontSize=11, leading=17,
                          textColor=colors.HexColor("#243247"), spaceAfter=10,
                          splitLongWords=True)
    title = ParagraphStyle("title", parent=body, fontSize=24, leading=31, spaceAfter=22)
    label = ParagraphStyle("label", parent=body, fontSize=10,
                           textColor=colors.HexColor("#607086"), spaceBefore=12)
    story = [Paragraph("FSP Platform", label), Paragraph("Профиль кандидата", title)]

    def field(caption, value):
        story.extend([Paragraph(caption, label), Paragraph(escape(value), body)])

    field("Имя", name or "Не указано")
    field("Специализация профиля", specialization or "Не указана")
    story.append(Paragraph("Стек / навыки", label))
    for skill in skills or ["Не указаны"]:
        story.append(Paragraph(escape(skill), body))
    story.append(Spacer(1, 10))
    if verified_grade and verified_specialization:
        field("Подтверждённая квалификация", f"{verified_specialization} — {verified_grade}")
    else:
        story.append(Paragraph("Квалификация не подтверждена", body))
    document.build(story)
    return stream.getvalue()


@router.get("/me/profile-pdf", response_class=Response,
            responses={200: {"content": {"application/pdf": {"schema": {"type": "string", "format": "binary"}}}},
                       401: {"description": "Authentication required"},
                       403: {"description": "Candidate role required"},
                       404: {"description": "Candidate profile not found"},
                       422: {"description": "Query parameters are not supported"}})
def profile_pdf(request: Request, user: CandidateUser, session: AuthSession) -> Response:
    if request.query_params:
        raise HTTPException(422, "Query parameters are not supported")
    profile = get_profile(session, user.id)
    if profile is None:
        raise HTTPException(404, "Candidate profile not found")
    proof = qualification(session, profile.id)

    def safe(value):
        # Export never grants contact disclosure. Also exclude contact-bearing free text.
        if not value or any(secret and secret.casefold() in value.casefold()
                            for secret in (user.email, profile.phone)):
            return None
        return contact_free(value)

    content = render_profile(safe(profile.full_name), safe(profile.specialization),
                             [v for item in profile.stack if (v := safe(item))],
                             safe(profile.verified_grade) if proof else None,
                             safe(profile.verified_specialization) if proof else None)
    return Response(content, media_type="application/pdf", headers={
        "Content-Disposition": 'attachment; filename="candidate-profile.pdf"',
        "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
    })
