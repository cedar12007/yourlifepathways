#!/usr/bin/env python3
"""
Generates an official, interactive AcroForm Fillable PDF for the YourLifePathways Coaching Agreement.
Fields are genuinely fillable in Adobe Acrobat Reader, Apple Preview, and modern web browsers.
"""

import os
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor

NAVY = HexColor("#0F172A")
SLATE = HexColor("#475569")
LIGHT_SLATE = HexColor("#64748B")
BORDER_COLOR = HexColor("#CBD5E1")
FIELD_BG = HexColor("#F1F5F9")
FIELD_BORDER = HexColor("#94A3B8")
PRIMARY_BLUE = HexColor("#0284C7")
LIGHT_BLUE_BG = HexColor("#F0F9FF")
LIGHT_BLUE_BORDER = HexColor("#BAE6FD")
WHITE = HexColor("#FFFFFF")

PAGE_W, PAGE_H = letter  # 612 x 792 pt
MARGIN_X = 40
USABLE_W = PAGE_W - (2 * MARGIN_X)  # 532 pt

def draw_header(c, y):
    logo_path = os.path.abspath("static/images/logo_your_life_pathways.png")
    if os.path.exists(logo_path):
        c.drawImage(logo_path, MARGIN_X, y - 48, width=155, height=48, preserveAspectRatio=True, mask='auto')
    else:
        c.setFont("Helvetica-Bold", 14)
        c.setFillColor(NAVY)
        c.drawString(MARGIN_X, y - 25, "YourLifePathways")
    
    # Right-aligned Doc Title & Badge
    c.setFont("Helvetica-Bold", 13.5)
    c.setFillColor(NAVY)
    c.drawRightString(PAGE_W - MARGIN_X, y - 20, "PROFESSIONAL COACHING AGREEMENT")
    
    # Badge
    badge_text = "International Coaching Federation (ICF) Code of Ethics Aligned"
    c.setFont("Helvetica-Bold", 7.5)
    badge_w = c.stringWidth(badge_text, "Helvetica-Bold", 7.5) + 12
    badge_x = PAGE_W - MARGIN_X - badge_w
    badge_y = y - 38
    c.setFillColor(LIGHT_BLUE_BG)
    c.setStrokeColor(LIGHT_BLUE_BORDER)
    c.setLineWidth(0.8)
    c.roundRect(badge_x, badge_y, badge_w, 14, 3, stroke=1, fill=1)
    c.setFillColor(PRIMARY_BLUE)
    c.drawString(badge_x + 6, badge_y + 4, badge_text)

    # Dividing line under masthead
    c.setStrokeColor(NAVY)
    c.setLineWidth(1.5)
    c.line(MARGIN_X, y - 56, PAGE_W - MARGIN_X, y - 56)
    return y - 66

def draw_section_title(c, y, title):
    # Top rule
    c.setStrokeColor(BORDER_COLOR)
    c.setLineWidth(0.8)
    c.line(MARGIN_X, y, PAGE_W - MARGIN_X, y)
    
    # Title Text
    c.setFont("Helvetica-Bold", 9.2)
    c.setFillColor(NAVY)
    c.drawString(MARGIN_X, y - 11, title.upper())
    
    # Bottom rule
    c.line(MARGIN_X, y - 16, PAGE_W - MARGIN_X, y - 16)
    return y - 24

def draw_footer(c, page_num, total_pages=2):
    y = 30
    c.setStrokeColor(BORDER_COLOR)
    c.setLineWidth(0.8)
    c.line(MARGIN_X, y + 10, PAGE_W - MARGIN_X, y + 10)
    
    c.setFont("Helvetica", 8)
    c.setFillColor(LIGHT_SLATE)
    c.drawString(MARGIN_X, y, "YourLifePathways • Business, Executive & Life Coaching • www.yourlifepathways.com")
    c.drawRightString(PAGE_W - MARGIN_X, y, f"Page {page_num} of {total_pages}")

def create_pdf(output_path):
    c = canvas.Canvas(output_path, pagesize=letter)
    form = c.acroForm

    # ==========================================
    # PAGE 1
    # ==========================================
    y = 756
    y = draw_header(c, y)

    # Effective Date Row
    c.setFont("Helvetica", 8.8)
    c.setFillColor(NAVY)
    c.drawString(MARGIN_X, y - 8, "This Coaching Agreement is entered into as of")
    form.textfield(
        name="effective_date",
        tooltip="Enter Effective Date (YYYY-MM-DD)",
        x=MARGIN_X + 195, y=y - 13,
        width=100, height=16,
        fontSize=8.5, fontName="Helvetica",
        fillColor=FIELD_BG, borderColor=FIELD_BORDER, borderWidth=0.8
    )
    c.drawString(MARGIN_X + 302, y - 8, "(the \"Effective Date\") by and between:")
    y -= 25

    # Parties Box
    box_h = 58
    c.setFillColor(HexColor("#F8FAFC"))
    c.setStrokeColor(BORDER_COLOR)
    c.setLineWidth(0.8)
    c.roundRect(MARGIN_X, y - box_h, USABLE_W, box_h, 3, stroke=1, fill=1)

    # Left party: Coach
    c.setFont("Helvetica-Bold", 8.8)
    c.setFillColor(NAVY)
    c.drawString(MARGIN_X + 10, y - 16, "Coach:  Erez Asif")
    c.setFont("Helvetica", 8)
    c.setFillColor(SLATE)
    c.drawString(MARGIN_X + 10, y - 29, "Erickson International Trained Coach")
    c.setFont("Helvetica", 8)
    c.setFillColor(PRIMARY_BLUE)
    c.drawString(MARGIN_X + 10, y - 42, "YourLifePathways (www.yourlifepathways.com)")

    # Right party: Client
    right_x = MARGIN_X + 225
    c.setFont("Helvetica-Bold", 8.5)
    c.setFillColor(NAVY)
    c.drawString(right_x, y - 18, "Client / Org:")
    form.textfield(
        name="client_name_org",
        tooltip="Client Full Name or Organization",
        x=right_x + 65, y=y - 23,
        width=230, height=16,
        fontSize=8.5, fontName="Helvetica",
        fillColor=FIELD_BG, borderColor=FIELD_BORDER, borderWidth=0.8
    )

    c.drawString(right_x, y - 42, "Representing:")
    form.textfield(
        name="client_representing",
        tooltip="Department / Sponsoring Entity",
        x=right_x + 65, y=y - 47,
        width=230, height=16,
        fontSize=8.5, fontName="Helvetica",
        fillColor=FIELD_BG, borderColor=FIELD_BORDER, borderWidth=0.8
    )
    y -= (box_h + 14)

    # 1. SCOPE OF COACHING SERVICES
    y = draw_section_title(c, y, "1. Scope of Coaching Services")

    # Scope Grid (2 rows x 2 cols)
    col1_label_w = 80
    col1_field_x = MARGIN_X + col1_label_w
    col2_x = MARGIN_X + 275
    col2_label_w = 90
    col2_field_x = col2_x + col2_label_w

    # Row 1
    c.setFont("Helvetica-Bold", 8.5)
    c.setFillColor(NAVY)
    c.drawString(MARGIN_X, y - 10, "Total Sessions:")
    form.textfield(
        name="total_sessions",
        tooltip="e.g. 6 sessions / Ongoing",
        x=col1_field_x, y=y - 14,
        width=175, height=15,
        fontSize=8.5, fontName="Helvetica",
        fillColor=FIELD_BG, borderColor=FIELD_BORDER, borderWidth=0.8
    )

    c.drawString(col2_x, y - 10, "Session Duration:")
    form.textfield(
        name="session_duration",
        tooltip="e.g. 60",
        value="60",
        x=col2_field_x, y=y - 14,
        width=40, height=15,
        fontSize=8.5, fontName="Helvetica",
        fillColor=FIELD_BG, borderColor=FIELD_BORDER, borderWidth=0.8
    )
    c.setFont("Helvetica", 8.5)
    c.setFillColor(SLATE)
    c.drawString(col2_field_x + 46, y - 10, "minutes")

    y -= 22

    # Row 2
    c.setFont("Helvetica-Bold", 8.5)
    c.setFillColor(NAVY)
    c.drawString(MARGIN_X, y - 10, "Frequency:")
    form.textfield(
        name="frequency",
        tooltip="Weekly / Bi-weekly / Monthly",
        x=col1_field_x, y=y - 14,
        width=175, height=15,
        fontSize=8.5, fontName="Helvetica",
        fillColor=FIELD_BG, borderColor=FIELD_BORDER, borderWidth=0.8
    )

    c.drawString(col2_x, y - 10, "Delivery Format:")
    form.textfield(
        name="delivery_format",
        tooltip="Teams / Meet / Zoom / Phone",
        x=col2_field_x, y=y - 14,
        width=155, height=15,
        fontSize=8.5, fontName="Helvetica",
        fillColor=FIELD_BG, borderColor=FIELD_BORDER, borderWidth=0.8
    )

    y -= 22
    c.setFont("Helvetica", 8)
    c.setFillColor(SLATE)
    c.drawString(MARGIN_X, y - 4, "Program Extension: May be extended for additional sessions upon mutual written agreement via email, maintaining established terms.")
    y -= 18

    # 2. COMPENSATION STRUCTURE
    y = draw_section_title(c, y, "2. Compensation Structure")

    c.setFont("Helvetica", 8.2)
    c.setFillColor(SLATE)
    c.drawString(MARGIN_X, y - 6, "To satisfy ICF credentialing standards, this engagement is established under a formal professional fee agreement. Select one:")
    y -= 16

    # Option A Box
    opt_a_h = 58
    c.setFillColor(HexColor("#F8FAFC"))
    c.setStrokeColor(BORDER_COLOR)
    c.setLineWidth(0.8)
    c.roundRect(MARGIN_X, y - opt_a_h, USABLE_W, opt_a_h, 3, stroke=1, fill=1)

    form.checkbox(
        name="opt_a_selected",
        tooltip="Select Option A",
        x=MARGIN_X + 10, y=y - 18,
        size=12, buttonStyle="check",
        fillColor=WHITE, borderColor=FIELD_BORDER
    )
    c.setFont("Helvetica-Bold", 8.6)
    c.setFillColor(NAVY)
    c.drawString(MARGIN_X + 28, y - 15, "Option A: Subsidized Professional Fee Structure")

    c.setFont("Helvetica", 8.4)
    c.drawString(MARGIN_X + 28, y - 32, "The Client agrees to pay a subsidized professional fee of  $")
    form.textfield(
        name="fee_per_session",
        tooltip="Fee per session (e.g. 150.00)",
        x=MARGIN_X + 248, y=y - 36,
        width=65, height=15,
        fontSize=8.5, fontName="Helvetica",
        fillColor=FIELD_BG, borderColor=FIELD_BORDER, borderWidth=0.8
    )
    c.drawString(MARGIN_X + 318, y - 32, "per session, for a total program investment of  $")
    form.textfield(
        name="total_investment",
        tooltip="Total Program Fee (e.g. 900.00)",
        x=MARGIN_X + 488, y=y - 36,
        width=70, height=15,
        fontSize=8.5, fontName="Helvetica",
        fillColor=FIELD_BG, borderColor=FIELD_BORDER, borderWidth=0.8
    )

    c.setFont("Helvetica-Bold", 8.4)
    c.drawString(MARGIN_X + 28, y - 50, "Payment Terms:")
    c.setFont("Helvetica", 8.4)
    c.drawString(MARGIN_X + 96, y - 50, "Fees shall be paid via")
    form.textfield(
        name="payment_method",
        tooltip="Zelle / Venmo / Bank Transfer / Invoice",
        x=MARGIN_X + 185, y=y - 54,
        width=330, height=15,
        fontSize=8.5, fontName="Helvetica",
        fillColor=FIELD_BG, borderColor=FIELD_BORDER, borderWidth=0.8
    )
    y -= (opt_a_h + 8)

    # Option B Box
    opt_b_h = 56
    c.setFillColor(HexColor("#F8FAFC"))
    c.setStrokeColor(BORDER_COLOR)
    c.setLineWidth(0.8)
    c.roundRect(MARGIN_X, y - opt_b_h, USABLE_W, opt_b_h, 3, stroke=1, fill=1)

    form.checkbox(
        name="opt_b_selected",
        tooltip="Select Option B",
        x=MARGIN_X + 10, y=y - 18,
        size=12, buttonStyle="check",
        fillColor=WHITE, borderColor=FIELD_BORDER
    )
    c.setFont("Helvetica-Bold", 8.6)
    c.setFillColor(NAVY)
    c.drawString(MARGIN_X + 28, y - 15, "Option B: Professional Barter & Service Exchange")

    c.setFont("Helvetica", 8.3)
    c.setFillColor(SLATE)
    c.drawString(MARGIN_X + 28, y - 31, "In lieu of direct financial payment, the parties agree to a professional barter exchange: Client provides a comprehensive written")
    c.drawString(MARGIN_X + 28, y - 44, "testimonial & review upon completion of every")
    form.textfield(
        name="barter_sessions_count",
        tooltip="Number of sessions per review (default 10)",
        value="10",
        x=MARGIN_X + 208, y=y - 48,
        width=30, height=14,
        fontSize=8.5, fontName="Helvetica",
        fillColor=FIELD_BG, borderColor=FIELD_BORDER, borderWidth=0.8
    )
    c.drawString(MARGIN_X + 244, y - 44, "sessions, suitable for Coach's website (www.yourlifepathways.com). Full, fair compensation.")
    y -= (opt_b_h + 6)

    c.setFont("Helvetica", 7.8)
    c.setFillColor(SLATE)
    c.drawString(MARGIN_X, y - 4, "Extension Billing: If extended under Section 1, the chosen compensation rate will apply to all additional sessions.")
    y -= 18

    # 3. PROFESSIONAL BOUNDARIES, DISCLAIMER & CLIENT RESPONSIBILITY
    y = draw_section_title(c, y, "3. Professional Boundaries, Disclaimer & Client Responsibility")

    c.setFont("Helvetica-Bold", 8.5)
    c.setFillColor(NAVY)
    c.drawString(MARGIN_X, y - 8, "What Coaching Is Not:")
    c.setFont("Helvetica", 8.4)
    c.setFillColor(SLATE)
    c.drawString(MARGIN_X + 96, y - 8, "Client understands Coach is not acting as a therapist, counselor, consultant, manager, or legal/medical advisor.")
    c.drawString(MARGIN_X, y - 20, "Coaching is distinct from consulting; recommendations or expert guidance must be offered under a separate agreement.")

    c.setFont("Helvetica-Bold", 8.5)
    c.setFillColor(NAVY)
    c.drawString(MARGIN_X, y - 36, "Client Responsibility & Liability:")
    c.setFont("Helvetica", 8.4)
    c.setFillColor(SLATE)
    c.drawString(MARGIN_X + 138, y - 36, "Client is solely responsible for their own decisions and actions. Coach is not liable for indirect or")
    c.drawString(MARGIN_X, y - 48, "consequential damages. Coach's total aggregate liability under any cause of action shall not exceed fees actually paid under Section 2.")

    draw_footer(c, 1, 2)
    c.showPage()

    # ==========================================
    # PAGE 2
    # ==========================================
    y = 756

    # 4. CONFIDENTIALITY, ETHICS & ICF AUDITING
    y = draw_section_title(c, y, "4. Confidentiality, Ethics & ICF Auditing")

    c.setFont("Helvetica", 8.5)
    c.setFillColor(SLATE)
    c.drawString(MARGIN_X, y - 8, "The Coach agrees to maintain strict confidentiality of all coaching conversations in full alignment with the")
    c.setFont("Helvetica-Bold", 8.5)
    c.setFillColor(NAVY)
    c.drawString(MARGIN_X + 382, y - 8, "ICF Code of Ethics.")
    c.setFont("Helvetica", 8.5)
    c.setFillColor(SLATE)
    c.drawString(MARGIN_X, y - 20, "No personal, proprietary, or organizational information shared during sessions will be disclosed without written consent.")

    c.setFont("Helvetica-Bold", 8.5)
    c.setFillColor(NAVY)
    c.drawString(MARGIN_X, y - 36, "ICF Client Log Audit Consent:")
    c.setFont("Helvetica", 8.5)
    c.setFillColor(SLATE)
    c.drawString(MARGIN_X + 124, y - 36, "The Client agrees that their name, email address, and total coaching hours completed may be listed")
    c.drawString(MARGIN_X, y - 48, "on Coach's confidential client coaching log for credentialing audit purposes with the ICF. (ICF verifies hours only; never content).")
    y -= 58

    # Optional Recording Consent Panel
    panel_h = 135
    c.setFillColor(LIGHT_BLUE_BG)
    c.setStrokeColor(LIGHT_BLUE_BORDER)
    c.setLineWidth(0.8)
    c.roundRect(MARGIN_X, y - panel_h, USABLE_W, panel_h, 4, stroke=1, fill=1)

    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(PRIMARY_BLUE)
    c.drawString(MARGIN_X + 12, y - 16, "Optional Session Recording Consent (ICF Credentialing Performance Evaluation)")

    c.setFont("Helvetica", 8.3)
    c.setFillColor(SLATE)
    c.drawString(MARGIN_X + 12, y - 30, "For Coach's ongoing credentialing with the International Coaching Federation (ICF), the ICF requires submission of unedited")
    c.drawString(MARGIN_X + 12, y - 42, "audio/video recordings to assess the Coach's core competency performance.")

    c.drawString(MARGIN_X + 24, y - 56, "• Recordings are used exclusively for confidential evaluation by certified ICF performance assessors and/or mentor coaches.")
    c.drawString(MARGIN_X + 24, y - 68, "• Recordings will never be published, distributed, or shared publicly.")
    c.drawString(MARGIN_X + 24, y - 80, "• Coach will give verbal notice before starting, and Client retains the right to decline or stop recording at any time.")

    # Dotted line inside panel
    c.setStrokeColor(HexColor("#93C5FD"))
    c.setLineWidth(0.7)
    c.setDash(2, 2)
    c.line(MARGIN_X + 10, y - 90, PAGE_W - MARGIN_X - 10, y - 90)
    c.setDash()  # reset solid

    # Consent Checkbox Yes
    form.checkbox(
        name="rec_consent_yes",
        tooltip="I consent to session recordings",
        x=MARGIN_X + 16, y=y - 108,
        size=12, buttonStyle="check",
        fillColor=WHITE, borderColor=PRIMARY_BLUE
    )
    c.setFont("Helvetica-Bold", 8.5)
    c.setFillColor(NAVY)
    c.drawString(MARGIN_X + 34, y - 105, "I consent")
    c.setFont("Helvetica", 8.4)
    c.setFillColor(SLATE)
    c.drawString(MARGIN_X + 76, y - 105, "to having selected coaching sessions recorded for ICF credentialing and mentor evaluation purposes.")

    # Consent Checkbox No
    form.checkbox(
        name="rec_consent_no",
        tooltip="I do not consent to session recordings",
        x=MARGIN_X + 16, y=y - 126,
        size=12, buttonStyle="check",
        fillColor=WHITE, borderColor=PRIMARY_BLUE
    )
    c.setFont("Helvetica-Bold", 8.5)
    c.setFillColor(NAVY)
    c.drawString(MARGIN_X + 34, y - 123, "I do not consent")
    c.setFont("Helvetica", 8.4)
    c.setFillColor(SLATE)
    c.drawString(MARGIN_X + 105, y - 123, "to session recordings at this time. (Opting out does not affect our coaching engagement).")

    y -= (panel_h + 16)

    # 5. CANCELLATION & SCHEDULING POLICY
    y = draw_section_title(c, y, "5. Cancellation & Scheduling Policy")

    c.setFont("Helvetica", 8.5)
    c.setFillColor(SLATE)
    c.drawString(MARGIN_X, y - 8, "Both parties commit to honoring appointments. Sessions must be rescheduled with at least")
    c.setFont("Helvetica-Bold", 8.5)
    c.setFillColor(NAVY)
    c.drawString(MARGIN_X + 360, y - 8, "24 hours' advance notice.")
    c.setFont("Helvetica", 8.5)
    c.setFillColor(SLATE)
    c.drawString(MARGIN_X, y - 20, "Missed appointments with less than 24h notice are deducted from program total, except in acute personal/medical emergencies.")
    y -= 30

    # 6. AGREEMENT & EXECUTION
    y = draw_section_title(c, y, "6. Agreement & Execution")

    c.setFont("Helvetica", 8.4)
    c.setFillColor(SLATE)
    c.drawString(MARGIN_X, y - 8, "By signing below, the Coach and Client acknowledge they have read, understood, and agreed to the terms of this Agreement,")
    c.drawString(MARGIN_X, y - 20, "confirming that the compensation selected in Section 2 serves as complete payment for the coaching program.")
    y -= 28

    # Signatures Table (Two Columns)
    sig_w = USABLE_W / 2
    sig_h = 140

    # Coach Box
    c.setFillColor(HexColor("#F8FAFC"))
    c.setStrokeColor(BORDER_COLOR)
    c.setLineWidth(0.8)
    c.rect(MARGIN_X, y - sig_h, sig_w, sig_h, stroke=1, fill=1)

    # Client Box
    c.rect(MARGIN_X + sig_w, y - sig_h, sig_w, sig_h, stroke=1, fill=1)

    # COACH COLUMN
    cx = MARGIN_X + 12
    cy = y - 16
    c.setFont("Helvetica-Bold", 8.8)
    c.setFillColor(NAVY)
    c.drawString(cx, cy, "COACH:")
    c.setFont("Helvetica-Bold", 8.5)
    c.drawString(cx, cy - 14, "Erez Asif")
    c.setFont("Helvetica", 8)
    c.setFillColor(SLATE)
    c.drawString(cx, cy - 26, "Erickson International Trained Coach")
    c.setFont("Helvetica", 8)
    c.setFillColor(PRIMARY_BLUE)
    c.drawString(cx, cy - 38, "YourLifePathways (www.yourlifepathways.com)")

    # Coach Signature Line
    c.setStrokeColor(HexColor("#64748B"))
    c.setLineWidth(0.8)
    c.setDash(2, 2)
    c.line(cx, cy - 54, cx + sig_w - 24, cy - 54)
    c.setDash()

    c.setFont("Helvetica-Bold", 8.5)
    c.setFillColor(NAVY)
    c.drawString(cx, cy - 72, "Signature:")
    form.textfield(
        name="coach_signature",
        tooltip="Coach Signature",
        value="Erez Asif",
        x=cx + 50, y=cy - 77,
        width=180, height=16,
        fontSize=9, fontName="Helvetica-Bold",
        fillColor=FIELD_BG, borderColor=FIELD_BORDER, borderWidth=0.8
    )

    c.drawString(cx, cy - 98, "Date:")
    form.textfield(
        name="coach_sig_date",
        tooltip="Coach Date (YYYY-MM-DD)",
        x=cx + 50, y=cy - 103,
        width=100, height=16,
        fontSize=8.5, fontName="Helvetica",
        fillColor=FIELD_BG, borderColor=FIELD_BORDER, borderWidth=0.8
    )

    # CLIENT COLUMN
    clx = MARGIN_X + sig_w + 12
    c.setFont("Helvetica-Bold", 8.8)
    c.setFillColor(NAVY)
    c.drawString(clx, cy, "CLIENT / REPRESENTATIVE:")

    c.setFont("Helvetica-Bold", 8.5)
    c.drawString(clx, cy - 18, "Name:")
    form.textfield(
        name="client_signer_name",
        tooltip="Client Signer Name",
        x=clx + 40, y=cy - 22,
        width=190, height=15,
        fontSize=8.5, fontName="Helvetica",
        fillColor=FIELD_BG, borderColor=FIELD_BORDER, borderWidth=0.8
    )

    c.drawString(clx, cy - 38, "Title / Org:")
    form.textfield(
        name="client_signer_title",
        tooltip="Title & Organization",
        x=clx + 55, y=cy - 42,
        width=175, height=15,
        fontSize=8.5, fontName="Helvetica",
        fillColor=FIELD_BG, borderColor=FIELD_BORDER, borderWidth=0.8
    )

    # Client Signature Line
    c.setStrokeColor(HexColor("#64748B"))
    c.setLineWidth(0.8)
    c.setDash(2, 2)
    c.line(clx, cy - 54, clx + sig_w - 24, cy - 54)
    c.setDash()

    c.drawString(clx, cy - 72, "Signature:")
    form.textfield(
        name="client_signature",
        tooltip="Client Signature",
        x=clx + 55, y=cy - 77,
        width=175, height=16,
        fontSize=9, fontName="Helvetica",
        fillColor=FIELD_BG, borderColor=FIELD_BORDER, borderWidth=0.8
    )

    c.drawString(clx, cy - 98, "Date:")
    form.textfield(
        name="client_sig_date",
        tooltip="Client Date (YYYY-MM-DD)",
        x=clx + 55, y=cy - 103,
        width=100, height=16,
        fontSize=8.5, fontName="Helvetica",
        fillColor=FIELD_BG, borderColor=FIELD_BORDER, borderWidth=0.8
    )

    draw_footer(c, 2, 2)
    c.showPage()

    c.save()
    print(f"Fillable PDF successfully generated at: {output_path}")

if __name__ == "__main__":
    out_file = os.path.abspath("docs/Professional_Coaching_Agreement_Fillable.pdf")
    create_pdf(out_file)

