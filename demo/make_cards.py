#!/usr/bin/env python3
"""Generate title/terminal/architecture cards for the RelateIQ demo video (1920x1080)."""
from PIL import Image, ImageDraw, ImageFont
import os

OUT = "/home/hatch/workspace/snowflake-coco-hackathon/demo/shots"
W, H = 1920, 1080
BG = (15, 27, 45)
ACCENT = (56, 189, 248)
TEXT = (232, 238, 246)
MUTED = (159, 179, 200)
GREEN = (52, 211, 153)

def font(sz, bold=False):
    for p in ["/usr/share/fonts/truetype/dejavu/DejaVuSans%s.ttf" % ("-Bold" if bold else ""),
              "/usr/share/fonts/TTF/DejaVuSans%s.ttf" % ("-Bold" if bold else "")]:
        if os.path.exists(p):
            return ImageFont.truetype(p, sz)
    return ImageFont.load_default()

def mono(sz):
    for p in ["/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
              "/usr/share/fonts/TTF/DejaVuSansMono.ttf"]:
        if os.path.exists(p):
            return ImageFont.truetype(p, sz)
    return ImageFont.load_default()

def base():
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 18], fill=ACCENT)
    return img, d

def title_card(path, title, subtitle, tagline):
    img, d = base()
    d.text((120, 380), title, font=font(130, True), fill=TEXT)
    d.text((120, 540), subtitle, font=font(48), fill=MUTED)
    d.text((120, 640), tagline, font=font(40), fill=GREEN)
    d.text((120, 980), "Ratnesh Saxena  ·  Solo  ·  Snowflake CoCo CLI Hackathon 2026",
           font=font(28), fill=MUTED)
    img.save(path)

def term_card(path, heading, lines):
    img, d = base()
    d.text((120, 90), heading, font=font(44, True), fill=ACCENT)
    y = 200
    mf = mono(30)
    for ln, col in lines:
        d.text((120, y), ln, font=mf, fill=col)
        y += 52
    img.save(path)

title_card(f"{OUT}/00_title.png",
           "RelateIQ",
           "Customer 360 + Next Best Action Engine",
           "Turn fragmented borrower signals into the right action, today.")

term_card(f"{OUT}/card_input.png", "INPUT  ·  what RelateIQ ingests", [
    ("$ ls data/ .cortex/skills/", MUTED),
    ("customers.csv  accounts.csv  transactions.csv  repayments.csv", TEXT),
    ("call_transcripts.md  support_emails.md  audit_log.csv", TEXT),
    ("", TEXT),
    (".cortex/skills/360-profiler/SKILL.md", GREEN),
    (".cortex/skills/signal-reader/SKILL.md", GREEN),
    (".cortex/skills/next-best-action-orchestrator/SKILL.md", GREEN),
    ("", TEXT),
    ("40 synthetic customers  ·  fully offline  ·  no API keys", MUTED),
])

term_card(f"{OUT}/card_signals.png", "SIGNAL READER  ·  unstructured to intent", [
    ("call_transcripts.md  >  CUST-007 Aditya Kulkarni", MUTED),
    ('" ...thinking of closing my account, service has been poor..."', TEXT),
    ("", TEXT),
    ("support_emails.md  >  CUST-003 Amit Verma", MUTED),
    ('" ...I dispute this charge, please do not debit my account..."', TEXT),
    ("", TEXT),
    ("extracted signals:", ACCENT),
    ("CUST-007 -> churn-risk      CUST-003 -> dispute-open  [HOLD]", GREEN),
    ("CUST-002 -> life-event      CUST-009 -> upsell-window", GREEN),
])

term_card(f"{OUT}/card_decision.png", "ORCHESTRATOR  ·  signals to next best action", [
    ("CUST-003 Amit Verma  |  attention 68  |  signal: dispute-open", TEXT),
    ("  -> branch: DISPUTE-HOLD   (dispute-open = do not contact)", GREEN),
    ("  -> outreach: none drafted  |  audit: 1 row appended", GREEN),
    ("", TEXT),
    ("CUST-007 Aditya Kulkarni  |  attention 39  |  signal: churn-risk", TEXT),
    ("  -> branch: CHURN-INTERVENTION  -> human callback drafted", GREEN),
    ("  -> audit: 1 row appended", GREEN),
    ("", TEXT),
    ("CUST-009  |  opportunity 71  |  signal: upsell-window", TEXT),
    ("  -> branch: PRE-APPROVED TOP-UP  -> offer drafted", GREEN),
])

term_card(f"{OUT}/card_arch.png", "TWO MODES  ·  ONE ENGINE", [
    ("DEMO MODE (default)", ACCENT),
    ("  local CSVs + markdown  ·  deterministic rules engine", TEXT),
    ("  no API keys  ·  runs offline  ·  judge-machine safe", TEXT),
    ("", TEXT),
    ("LIVE MODE", ACCENT),
    ("  Snowflake via env vars / Streamlit secrets", TEXT),
    ("  SQL + Cortex-ready semantic model", TEXT),
    ("  unreachable?  ->  graceful fallback to demo mode", GREEN),
])

print("cards done")
