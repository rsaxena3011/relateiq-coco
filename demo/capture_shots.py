#!/usr/bin/env python3
"""Capture RelateIQ Streamlit screenshots for the demo video."""
from playwright.sync_api import sync_playwright

URL = "http://localhost:8501"
OUT = "/home/hatch/workspace/snowflake-coco-hackathon/demo/shots"

import os
os.makedirs(OUT, exist_ok=True)

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1280, "height": 720})
    pg.goto(URL)
    # wait for the app to render
    pg.wait_for_selector("text=Priority Feed", timeout=30000)
    pg.wait_for_timeout(2500)
    pg.screenshot(path=f"{OUT}/01_priority_feed.png")
    print("shot 1 ok")

    # Customer 360 tab
    pg.get_by_role("tab", name="Customer 360").click()
    pg.wait_for_timeout(2000)
    pg.screenshot(path=f"{OUT}/02_customer360.png")
    print("shot 2 ok")

    # Action Queue tab
    pg.get_by_role("tab", name="Action Queue").click()
    pg.wait_for_timeout(2000)
    pg.screenshot(path=f"{OUT}/03_action_queue.png")
    print("shot 3 ok")

    b.close()
print("done")
