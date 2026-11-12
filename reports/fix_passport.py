
import os
import re
import json
import logging
import html

from pathlib import Path
from datetime import datetime, timezone

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle
)


logger = logging.getLogger("yukticorex.fix_passport")


# ----------------------------------------------------
# 1. REPORT DIRECTORY
# ----------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent

REPORTS_DIR = Path(
    os.getenv(
        "GENERATED_REPORTS_DIR",
        str(BASE_DIR / "generated_reports")
    )
)


# ----------------------------------------------------
# 2. DATA NORMALIZATION
# ----------------------------------------------------

def _to_dict(value):
    """Convert dictionaries and Pydantic models into dictionaries."""

    if isinstance(value, dict):
        return value

    if hasattr(value, "model_dump"):
        return value.model_dump()

    if hasattr(value, "dict"):
        return value.dict()

    if isinstance(value, str):
        try:
            parsed = json.loads(value)

            if isinstance(parsed, dict):
                return parsed

        except (ValueError, TypeError):
            return {"details": value}

    return {"details": str(value)}


def _get_text(data, *keys, default="Not available"):
    """Return the first available non-empty field."""

    for key in keys:
        value = data.get(key)

        if value is not None and value != "":
            if isinstance(value, (dict, list)):
                return json.dumps(value, indent=2, default=str)

            return str(value)

    return default


def _safe_filename(task_id):
    """Prevent unsafe filenames."""

    safe_id = re.sub(
        r"[^a-zA-Z0-9_-]",
        "_",
        str(task_id)
    )

    return "Fix_Passport_{}.pdf".format(safe_id)


def _paragraph_text(value):
    """Escape text before adding it to ReportLab paragraphs."""

    return html.escape(str(value)).replace("\n", "<br/>")


# ----------------------------------------------------
# 3. PDF STYLES
# ----------------------------------------------------

def _create_styles():

    styles = getSampleStyleSheet()

    styles.add(
        ParagraphStyle(
            name="PassportTitle",
            parent=styles["Title"],
            fontSize=24,
            leading=30,
            textColor=colors.HexColor("#173B65"),
            alignment=1,
            spaceAfter=8
        )
    )

    styles.add(
        ParagraphStyle(
            name="PassportSubtitle",
            parent=styles["Normal"],
            fontSize=10,
            alignment=1,
            textColor=colors.HexColor("#64748B"),
            spaceAfter=20
        )
    )

    styles.add(
        ParagraphStyle(
            name="SectionHeading",
            parent=styles["Heading2"],
            fontSize=13,
            leading=17,
            textColor=colors.HexColor("#173B65"),
            spaceBefore=14,
            spaceAfter=8
        )
    )

    styles.add(
        ParagraphStyle(
            name="PassportBody",
            parent=styles["BodyText"],
            fontSize=9,
            leading=14,
            spaceAfter=6
        )
    )

    styles.add(
        ParagraphStyle(
            name="CodeStyle",
            parent=styles["Code"],
            fontName="Courier",
            fontSize=7,
            leading=10,
            textColor=colors.HexColor("#E2E8F0"),
            backColor=colors.HexColor("#172033"),
            borderPadding=8,
            spaceBefore=4,
            spaceAfter=8,
            wordWrap="CJK"
        )
    )

    styles.add(
        ParagraphStyle(
            name="SmallText",
            parent=styles["Normal"],
            fontSize=8,
            leading=11
        )
    )

    return styles


# ----------------------------------------------------
# 4. PDF HELPERS
# ----------------------------------------------------

def _add_heading(story, text, styles):

    story.append(
        Paragraph(
            _paragraph_text(text),
            styles["SectionHeading"]
        )
    )


def _add_text(story, text, styles):

    story.append(
        Paragraph(
            _paragraph_text(text),
            styles["PassportBody"]
        )
    )


def _add_code(story, code, styles):

    if not code:
        code = "No code available."

    escaped = html.escape(str(code))
    escaped = escaped.replace("\n", "<br/>")

    story.append(
        Paragraph(
            escaped,
            styles["CodeStyle"]
        )
    )


def _add_table(story, rows, styles):

    table_data = []

    for row in rows:
        table_data.append([
            Paragraph(
                _paragraph_text(cell),
                styles["SmallText"]
            )
            for cell in row
        ])

    table = Table(
        table_data,
        colWidths=[45 * mm, 115 * mm],
        repeatRows=0,
        hAlign="LEFT"
    )

    table.setStyle(
        TableStyle([
            (
                "BACKGROUND",
                (0, 0),
                (0, -1),
                colors.HexColor("#EAF1F8")
            ),
            (
                "TEXTCOLOR",
                (0, 0),
                (-1, -1),
                colors.HexColor("#1E293B")
            ),
            (
                "GRID",
                (0, 0),
                (-1, -1),
                0.4,
                colors.HexColor("#CBD5E1")
            ),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7)
        ])
    )

    story.append(table)
    story.append(Spacer(1, 8))


# ----------------------------------------------------
# 5. PAGE FOOTER
# ----------------------------------------------------

def _add_page_number(canvas, document):

    canvas.saveState()

    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#64748B"))

    canvas.drawString(
        20 * mm,
        12 * mm,
        "YuktiC-oreX | AI-Powered Automated Bug Repair"
    )

    canvas.drawRightString(
        190 * mm,
        12 * mm,
        "Page {}".format(document.page)
    )

    canvas.restoreState()


# ----------------------------------------------------
# 6. GENERATE FIX PASSPORT
# ----------------------------------------------------

def generate_fix_passport(
    task_id,
    issue,
    bug_location,
    proposed_fix,
    verification,
    challenger_review
):
    """
    Generate a PDF Fix Passport.

    Returns:
        {
            "success": True,
            "report_path": "...",
            "file_name": "..."
        }
    """

    try:

        # ------------------------------------------------
        # NORMALIZE INCOMING DATA
        # ------------------------------------------------

        issue = _to_dict(issue)
        bug_location = _to_dict(bug_location)
        proposed_fix = _to_dict(proposed_fix)
        verification = _to_dict(verification)
        challenger_review = _to_dict(challenger_review)

        # ------------------------------------------------
        # VALIDATE VERIFICATION
        # ------------------------------------------------

        verification_passed = (
            verification.get("passed") is True
            or verification.get("test_status") == "passed"
        )

        if not verification_passed:
            raise ValueError(
                "Cannot generate Fix Passport: "
                "regression verification did not pass."
            )

        # ------------------------------------------------
        # VALIDATE FIX CHALLENGER
        # ------------------------------------------------

        if challenger_review.get("verdict") != "APPROVE":
            raise ValueError(
                "Cannot generate Fix Passport: "
                "Fix Challenger did not approve the repair."
            )

        # ------------------------------------------------
        # CREATE OUTPUT DIRECTORY
        # ------------------------------------------------

        REPORTS_DIR.mkdir(
            parents=True,
            exist_ok=True
        )

        filename = _safe_filename(task_id)
        report_path = REPORTS_DIR / filename

        # ------------------------------------------------
        # PREPARE DOCUMENT
        # ------------------------------------------------

        document = SimpleDocTemplate(
            str(report_path),
            pagesize=A4,
            rightMargin=20 * mm,
            leftMargin=20 * mm,
            topMargin=18 * mm,
            bottomMargin=22 * mm
        )

        styles = _create_styles()
        story = []

        generated_at = datetime.now(
            timezone.utc
        ).strftime("%d %B %Y, %H:%M UTC")

        # ------------------------------------------------
        # TITLE
        # ------------------------------------------------

        story.append(
            Paragraph(
                "YuktiC-oreX",
                styles["PassportTitle"]
            )
        )

        story.append(
            Paragraph(
                "AUTOMATED BUG REPAIR FIX PASSPORT",
                styles["PassportSubtitle"]
            )
        )

        _add_table(
            story,
            [
                ["Task ID", str(task_id)],
                ["Generated On", generated_at],
                [
                    "Repair Status",
                    "Verified - Awaiting Human Approval"
                ]
            ],
            styles
        )

        # ------------------------------------------------
        # 1. ISSUE DETAILS
        # ------------------------------------------------

        _add_heading(
            story,
            "1. GitHub Issue Details",
            styles
        )

        _add_table(
            story,
            [
                [
                    "Issue Number",
                    _get_text(issue, "number", "issue_number")
                ],
                [
                    "Issue Title",
                    _get_text(issue, "title", "issue_title")
                ],
                [
                    "Issue URL",
                    _get_text(
                        issue,
                        "issue_url",
                        "html_url",
                        "url"
                    )
                ]
            ],
            styles
        )

        _add_text(story, "Issue Description:", styles)

        _add_text(
            story,
            _get_text(issue, "body", "description"),
            styles
        )

        # ------------------------------------------------
        # 2. BUG LOCATION AND ROOT CAUSE
        # ------------------------------------------------

        _add_heading(
            story,
            "2. Bug Location and Root Cause",
            styles
        )

        _add_table(
            story,
            [
                [
                    "File",
                    _get_text(bug_location, "file_path", "file")
                ],
                [
                    "Function",
                    _get_text(
                        bug_location,
                        "function_name",
                        "function"
                    )
                ],
                [
                    "Bug Found",
                    _get_text(
                        bug_location,
                        "found",
                        default="Not specified"
                    )
                ]
            ],
            styles
        )

        _add_text(story, "Root Cause:", styles)

        _add_text(
            story,
            _get_text(
                proposed_fix,
                "root_cause",
                "explanation",
                default=_get_text(bug_location, "reason")
            ),
            styles
        )

        # ------------------------------------------------
        # 3. PROPOSED REPAIR
        # ------------------------------------------------

        _add_heading(
            story,
            "3. Proposed Repair",
            styles
        )

        _add_text(
            story,
            _get_text(
                proposed_fix,
                "explanation",
                "description",
                default="Automated repair proposal."
            ),
            styles
        )

        _add_text(story, "Changed Files:", styles)

        changed_files = proposed_fix.get("changed_files", [])

        if isinstance(changed_files, str):
            changed_files = [changed_files]

        if not isinstance(changed_files, list):
            changed_files = []

        if not changed_files:
            changed_files = [
                _get_text(
                    proposed_fix,
                    "file_path",
                    default="Not specified"
                )
            ]

        for file_path in changed_files:
            _add_text(
                story,
                "- {}".format(file_path),
                styles
            )

        # ------------------------------------------------
        # 4. ORIGINAL CODE
        # ------------------------------------------------

        _add_heading(
            story,
            "4. Original Code",
            styles
        )

        _add_code(
            story,
            proposed_fix.get("original_code", ""),
            styles
        )

        # ------------------------------------------------
        # 5. MODIFIED CODE
        # ------------------------------------------------

        _add_heading(
            story,
            "5. Modified Code",
            styles
        )

        _add_code(
            story,
            proposed_fix.get("modified_code", ""),
            styles
        )

        # ------------------------------------------------
        # 6. GENERATED PATCH
        # ------------------------------------------------

        _add_heading(
            story,
            "6. Generated Patch",
            styles
        )

        _add_code(
            story,
            proposed_fix.get(
                "patch",
                proposed_fix.get(
                    "diff",
                    "Patch details not available."
                )
            ),
            styles
        )

        # ------------------------------------------------
        # 7. FIX CHALLENGER REVIEW
        # ------------------------------------------------

        _add_heading(
            story,
            "7. Independent Fix Challenger Review",
            styles
        )

        _add_table(
            story,
            [
                [
                    "Verdict",
                    _get_text(challenger_review, "verdict")
                ],
                [
                    "Explanation",
                    _get_text(challenger_review, "explanation")
                ]
            ],
            styles
        )

        for label, key in [
            ("Findings", "findings"),
            ("Potential Regressions", "potential_regressions"),
            ("Required Corrections", "required_corrections")
        ]:

            _add_text(
                story,
                label + ":",
                styles
            )

            values = challenger_review.get(key, [])

            if isinstance(values, str):
                values = [values]

            if not values:
                _add_text(
                    story,
                    "None reported.",
                    styles
                )
            else:
                for value in values:
                    _add_text(
                        story,
                        "- " + str(value),
                        styles
                    )

        # ------------------------------------------------
        # 8. REGRESSION VERIFICATION
        # ------------------------------------------------

        _add_heading(
            story,
            "8. Regression Verification Results",
            styles
        )

        _add_table(
            story,
            [
                [
                    "Verification",
                    "PASSED"
                ],
                [
                    "Test Status",
                    _get_text(
                        verification,
                        "test_status",
                        default="passed"
                    )
                ],
                [
                    "Exit Code",
                    _get_text(
                        verification,
                        "exit_code",
                        default="Not available"
                    )
                ]
            ],
            styles
        )

        _add_text(
            story,
            "Verification Logs:",
            styles
        )

        _add_code(
            story,
            verification.get(
                "logs",
                verification.get(
                    "message",
                    "No verification logs available."
                )
            ),
            styles
        )

        # ------------------------------------------------
        # 9. FINAL REPAIR SUMMARY
        # ------------------------------------------------

        _add_heading(
            story,
            "9. Final Repair Summary",
            styles
        )

        _add_text(
            story,
            (
                "YuktiC-oreX analyzed the reported issue, "
                "located the suspected faulty code, generated "
                "a repair proposal, submitted it for independent "
                "AI review, and performed regression verification."
            ),
            styles
        )

        _add_text(
            story,
            (
                "This Fix Passport records the repair evidence. "
                "Human approval is required before the repair "
                "branch is pushed and a GitHub Pull Request is created."
            ),
            styles
        )

        _add_text(
            story,
            "Human Approval Status: PENDING",
            styles
        )

        # ------------------------------------------------
        # BUILD PDF
        # ------------------------------------------------

        document.build(
            story,
            onFirstPage=_add_page_number,
            onLaterPages=_add_page_number
        )

        if (
            not report_path.exists()
            or report_path.stat().st_size == 0
        ):
            raise RuntimeError(
                "PDF report was not created successfully."
            )

        logger.info(
            "Fix Passport generated successfully: %s",
            report_path
        )

        return {
            "success": True,
            "report_path": str(report_path.resolve()),
            "file_name": filename
        }

    except Exception as exc:

        logger.exception(
            "Fix Passport generation failed."
        )

        return {
            "success": False,
            "error": str(exc),
            "report_path": None
        }
