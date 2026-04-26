#!/usr/bin/env python3
"""Capture screenshots of all 5 models in KDeepMatrixAI Streamlit UI."""

from playwright.sync_api import sync_playwright
import time

BASE_URL = "http://localhost:8501"
OUTPUT_DIR = "docs/images"


def wait_for_streamlit_load(page):
    """Wait for Streamlit page to fully load."""
    for _ in range(30):
        title = page.title()
        if "KDeepMatrixAI" in title:
            return True
        time.sleep(1)
    return False


def select_model(page, model_text):
    """Select a model from the dropdown."""
    # Click the model selector combobox
    page.get_by_role("combobox").first.click()
    time.sleep(1)
    # Click the option
    page.get_by_role("option", name=model_text).click()
    time.sleep(3)


def click_run_and_wait(page, wait_seconds):
    """Click the run button and wait for results."""
    page.get_by_test_id("stBaseButton-primary").click()
    time.sleep(wait_seconds)


def fill_text_input(page, label, value):
    """Fill a text input by label."""
    page.get_by_role("textbox", name=label).fill(value)
    time.sleep(0.5)


def capture_model(page, model_name, model_option_text, actions, wait_time, filename):
    """Capture a screenshot for a specific model."""
    print(f"\n=== Capturing {model_name} ===")
    page.goto(BASE_URL)
    if not wait_for_streamlit_load(page):
        print(f"  ERROR: Page failed to load for {model_name}")
        return False

    time.sleep(3)
    select_model(page, model_option_text)

    # Perform custom actions
    for action in actions:
        action(page)

    click_run_and_wait(page, wait_time)

    # Scroll to bottom to capture full results
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    time.sleep(1)

    page.screenshot(path=f"{OUTPUT_DIR}/{filename}", full_page=True)
    print(f"  SAVED: {OUTPUT_DIR}/{filename}")
    return True


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 900})

        results = []

        # 001 RAM - single part number for speed
        results.append(capture_model(
            page, "001 RAM", "af_ba_req_001",
            actions=[
                lambda p: fill_text_input(p, "부품번호 (pn)", "부품번호00001"),
            ],
            wait_time=40,
            filename="kdeep_model_001_ram.png"
        ))

        # 002 Life - single part number for speed
        results.append(capture_model(
            page, "002 Life", "af_ba_req_002",
            actions=[
                lambda p: fill_text_input(p, "부품번호 (pn)", "부품번호01217"),
            ],
            wait_time=25,
            filename="kdeep_model_002_life.png"
        ))

        # 004 Simulation - default values
        results.append(capture_model(
            page, "004 Simulation", "af_ba_req_004",
            actions=[],
            wait_time=5,
            filename="kdeep_model_004_sim.png"
        ))

        # 005 Recommendation - default values
        results.append(capture_model(
            page, "005 Recommend", "af_ba_req_005",
            actions=[],
            wait_time=5,
            filename="kdeep_model_005_recommend.png"
        ))

        # 007 IMQC - default values
        results.append(capture_model(
            page, "007 IMQC", "af_ba_req_007",
            actions=[],
            wait_time=20,
            filename="kdeep_model_007_imqc.png"
        ))

        browser.close()

        success = sum(results)
        print(f"\n=== Done: {success}/{len(results)} screenshots captured ===")


if __name__ == "__main__":
    main()
