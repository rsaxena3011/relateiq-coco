#!/usr/bin/env python3
"""Build RelateIQ 6-slide deck PDF (reportlab). 16:9 slides, clean dark theme."""
from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor, white, black
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

W, H = landscape(A4)  # 297 x 210 mm
BG = HexColor("#0F1B2D")
ACCENT = HexColor("#38BDF8")
TEXT = HexColor("#E8EEF6")
MUTED = HexColor("#9FB3C8")
CARD = HexColor("#16263D")
GREEN = HexColor("#34D399")
AMBER = HexColor("#FBBF24")

slides = []

# ---- Slide 1: Title ----
slides.append({
    "kicker": "SNOWFLAKE COCO CLI HACKATHON 2026  |  GCC EDITION",
    "title": "RelateIQ",
    "subtitle": "Customer 360 + Next Best Action Engine",
    "tagline": "Turn fragmented borrower signals into the right action, today.",
    "bullets": [
        "Team Name: Ratnesh Saxena (Solo)",
        "Problem Statement: PS2 \u2014 Customer 360 and Next Best Action Engine",
        "Team Leader: Ratnesh Saxena",
        "Team Size: 1",
    ],
})

# ---- Slide 2: Problem ----
slides.append({
    "kicker": "02  /  PROBLEM BRIEF",
    "title": "The Problem: Arjun Guesses Every Morning",
    "bullets": [
        "Arjun Mehta, Relationship Manager at a digital lender, oversees 2,000 retail borrowers.",
        "Every morning he must answer: which customers need attention TODAY, and exactly what to do about each one.",
        "Today he guesses. The cost: disputes get dunned (relationships torched), churners slip away unnoticed, upsell windows close before anyone acts.",
        "The gap: structured account data and unstructured conversation signals (calls, emails) live in separate worlds \u2014 no single customer view exists.",
        "Key stat: 2,000 borrowers \u00b7 1 manager \u00b7 0 single view of the customer.",
    ],
})

# ---- Slide 3: Architecture ----
slides.append({
    "kicker": "03  /  ARCHITECTURE",
    "title": "How It Works",
    "bullets": [
        "DATA SOURCES: Accounts | Transactions | Repayment History | Credit Utilization | Tenure  +  Call Transcripts | Support Emails | KYC / Document Notes",
        "SNOWFLAKE CUSTOMER 360 LAYER: governed semantic views over structured + unstructured data; SQL + Cortex-ready; auditable decision tables.",
        "SKILL 1 \u2014 360 PROFILER: fuses structured signals into Attention (0\u2013100) + Opportunity (0\u2013100) scores. Deterministic, explainable weighted scoring.",
        "SKILL 2 \u2014 SIGNAL READER: extracts intent from unstructured touchpoints: churn-risk, dispute-open, complaint, life-event, upsell-window.",
        "SKILL 3 \u2014 NEXT-BEST-ACTION ORCHESTRATOR: six decision branches (dispute-hold, churn callback, collections gentle/firm, retention offer, pre-approved upsell); drafts outreach; append-only audit write.",
        "STREAMLIT APP: Priority Feed (rank) \u00b7 Customer 360 (diagnose) \u00b7 Action Queue (approve). Demo mode offline / Live mode Snowflake with graceful fallback.",
    ],
})

# ---- Slide 4: CoCo skills ----
slides.append({
    "kicker": "04  /  COCO CLI SKILLS",
    "title": "Three Modular Skills, One Pipeline",
    "bullets": [
        "1. 360-profiler  \u2014  in: accounts, transactions, repayments, credit, tenure  \u2014  out: Attention + Opportunity scores + reasoning trace  (.coco/skills/360-profiler/SKILL.md)",
        "2. signal-reader  \u2014  in: call_transcripts.md, support_emails.md  \u2014  out: intent signal + CLEAR/HOLD clearance  (.coco/skills/signal-reader/SKILL.md)",
        "3. next-best-action-orchestrator  \u2014  in: scores + signals + DPD  \u2014  out: action + reason + drafted outreach + audit row  (.coco/skills/next-best-action-orchestrator/SKILL.md)",
        "Connection: profiler output feeds orchestrator branch thresholds; signal-reader gates branches (dispute-open forces dispute-hold with zero outreach).",
        "Every decision appends exactly one row to the audit table \u2014 never UPDATE, never DELETE.",
    ],
})

# ---- Slide 5: Impact ----
slides.append({
    "kicker": "05  /  IMPACT STATEMENT",
    "title": "From Guesswork to a Ranked Queue in Seconds",
    "bullets": [
        "Speed: a 40-customer portfolio is profiled, signal-scanned and action-queued in seconds; the same engine scales to Arjun's full 2,000-borrower book.",
        "Risk eliminated: dispute-hold guarantees zero dunning of customers with open disputes (the Amit Verma case).",
        "Revenue protected + grown: churn-intervention callbacks target high-LTV at-risk customers (Vikram Rao); pre-approved top-ups surface exactly when utilization and score qualify (Kavya Nair).",
        "Trust by design: every score shows its reasoning trace; every decision carries its reason; every approved action lands in an append-only audit table.",
        "Projected outcomes: delinquency down through earlier, correctly-toned collections; upsell conversion up through perfectly timed offers.",
    ],
})

# ---- Slide 6: Roadmap ----
slides.append({
    "kicker": "06  /  ROADMAP",
    "title": "What Comes Next",
    "bullets": [
        "1. Live Snowflake wiring: run sql/01_schema.sql + sql/02_load.py, flip the toggle, validate Demo/Live score parity.",
        "2. Cortex Analyst in production: ship the relateiq_model semantic model for plain-language portfolio questions.",
        "3. Real signal ingestion: replace markdown fixtures with a nightly pipeline from call-recording and ticketing systems.",
        "4. Pilot with one RM team: measure dispute-dun rate, callback conversion and upsell uptake vs a control group for one quarter.",
        "5. Expand the branch library: EMI restructuring, referral offers and more as new data becomes available.",
        "Closing line: Arjun no longer guesses. He just opens the feed.",
    ],
})


def draw_slide(c, s, idx):
    c.setFillColor(BG)
    c.rect(0, 0, W, H, fill=1, stroke=0)
    # accent bar
    c.setFillColor(ACCENT)
    c.rect(0, H - 14 * mm, W, 4 * mm, fill=1, stroke=0)
    # slide number
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 9)
    c.drawRightString(W - 15 * mm, 10 * mm, f"{idx + 1} / 6")

    y = H - 30 * mm
    c.setFillColor(ACCENT)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(15 * mm, y, s["kicker"])
    y -= 14 * mm
    c.setFillColor(TEXT)
    c.setFont("Helvetica-Bold", 30)
    c.drawString(15 * mm, y, s["title"])
    y -= 12 * mm

    if "subtitle" in s:
        c.setFillColor(MUTED)
        c.setFont("Helvetica", 15)
        c.drawString(15 * mm, y, s["subtitle"])
        y -= 10 * mm
    if "tagline" in s:
        c.setFillColor(GREEN)
        c.setFont("Helvetica-Oblique", 13)
        c.drawString(15 * mm, y, s["tagline"])
        y -= 12 * mm

    c.setFont("Helvetica", 11.5)
    max_w = W - 30 * mm
    for b in s["bullets"]:
        # wrap
        words, lines, line = b.split(), [], ""
        for w_ in words:
            t = (line + " " + w_).strip()
            if c.stringWidth(t, "Helvetica", 11.5) > max_w:
                lines.append(line)
                line = w_
            else:
                line = t
        lines.append(line)
        c.setFillColor(ACCENT)
        c.drawString(15 * mm, y, "\u2022")
        c.setFillColor(TEXT)
        ty = y
        for li, ln in enumerate(lines):
            c.drawString(20 * mm, ty, ln)
            ty -= 6.5 * mm
        y = ty - 4 * mm


def main():
    out = "/home/hatch/workspace/snowflake-coco-hackathon/docs/RelateIQ_deck.pdf"
    c = canvas.Canvas(out, pagesize=landscape(A4))
    c.setTitle("RelateIQ - Customer 360 + Next Best Action Engine")
    c.setAuthor("Ratnesh Saxena")
    for i, s in enumerate(slides):
        draw_slide(c, s, i)
        c.showPage()
    c.save()
    import os
    print("wrote", out, os.path.getsize(out), "bytes")


main()
