#!/usr/bin/env python3
"""Assemble RelateIQ demo video: shots + voiceovers + subtle zoom, concat."""
import subprocess, os, json

BASE = "/home/hatch/workspace/snowflake-coco-hackathon/demo"
SHOTS = f"{BASE}/shots"
VO = f"{BASE}/vo"
SEG = f"{BASE}/segments"
os.makedirs(SEG, exist_ok=True)

# (image, vo, pad_after_seconds)
PLAN = [
    ("00_title.png", "vo01.mp3", 3.0),
    ("card_input.png", "vo02.mp3", 2.5),
    ("01_priority_feed.png", "vo03.mp3", 2.5),
    ("card_signals.png", "vo04.mp3", 2.5),
    ("card_decision.png", "vo05.mp3", 2.5),
    ("01_priority_feed.png", "vo06.mp3", 2.5),
    ("02_customer360.png", "vo07.mp3", 2.5),
    ("03_action_queue.png", "vo08.mp3", 2.5),
    ("card_arch.png", "vo09.mp3", 2.5),
    ("00_title.png", "vo10.mp3", 5.0),
]

def vo_dur(p):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                        "format=duration", "-of", "csv=p=0", p],
                       capture_output=True, text=True)
    return float(r.stdout.strip())

segs = []
for i, (img, vo, pad) in enumerate(PLAN):
    vd = vo_dur(f"{VO}/{vo}")
    total = vd + pad
    frames = int(total * 30)
    seg = f"{SEG}/seg{i:02d}.mp4"
    # slow zoom-in via zoompan, then ensure yuv420p
    vf = (f"scale=1920:1080,"
          f"zoompan=z='min(zoom+0.0006,1.12)':d={frames}:"
          f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1920x1080:fps=30,"
          f"format=yuv420p")
    cmd = ["ffmpeg", "-y", "-loop", "1", "-i", f"{SHOTS}/{img}",
           "-i", f"{VO}/{vo}",
           "-filter_complex",
           f"[0:v]{vf}[v];[1:a]apad=pad_dur={pad}[a]",
           "-map", "[v]", "-map", "[a]",
           "-t", str(total), "-c:v", "libx264", "-preset", "medium",
           "-crf", "20", "-c:a", "aac", "-b:a", "128k",
           "-shortest", seg]
    subprocess.run(cmd, capture_output=True)
    segs.append(seg)
    print(f"seg {i}: {total:.1f}s")

# concat
lst = f"{SEG}/list.txt"
with open(lst, "w") as f:
    for s in segs:
        f.write(f"file '{s}'\n")
out = f"{BASE}/RelateIQ_demo.mp4"
subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0",
                "-i", lst, "-c", "copy", out], capture_output=True)
sz = os.path.getsize(out)
r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                    "format=duration", "-of", "csv=p=0", out],
                   capture_output=True, text=True)
print("FINAL:", out, f"{sz/1e6:.1f}MB", f"{float(r.stdout.strip()):.0f}s")
