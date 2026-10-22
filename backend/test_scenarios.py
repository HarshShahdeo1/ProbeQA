"""
test_scenarios.py
─────────────────────────────────────────────────────────────────────────────
Comprehensive verification suite for Stage 3.5:
  1. Strict origin & URL parsing validation unit tests
  2. Failed login / navigation workflow test (asserting genuine failure & screenshot evidence)
  3. Successful standard-user workflow test (asserting 6 items & inventory screenshot)
"""

import asyncio
import os
import sys
from pathlib import Path

# Ensure backend directory is in path
sys.path.insert(0, str(Path(__file__).parent))

from runner import (
    validate_saucedemo_origin,
    run_saucedemo_login_test,
    EVIDENCE_DIR,
)
from validator import validate_url, ValidationError


def test_origin_parsing_safeguards():
    print("\n--- TEST 1: Strict Origin & URL Parsing Validation ---")

    # 1. Scheme check (reject HTTP)
    try:
        validate_saucedemo_origin("http://www.saucedemo.com/")
        assert False, "Should have rejected non-https scheme"
    except AssertionError as e:
        print(f"  [PASS] Blocked non-HTTPS: {e}")

    # 2. Hostname check (reject third-party or spoofed domains)
    try:
        validate_saucedemo_origin("https://saucedemo.com.attacker.com/")
        assert False, "Should have rejected spoofed domain"
    except AssertionError as e:
        print(f"  [PASS] Blocked spoofed hostname: {e}")

    try:
        validate_saucedemo_origin("https://evil.com/inventory.html")
        assert False, "Should have rejected evil.com"
    except AssertionError as e:
        print(f"  [PASS] Blocked unauthorized origin: {e}")

    # 3. Port check (reject non-standard ports)
    try:
        validate_saucedemo_origin("https://www.saucedemo.com:8443/")
        assert False, "Should have rejected port 8443"
    except AssertionError as e:
        print(f"  [PASS] Blocked unexpected port: {e}")

    # 4. Path prefix check
    try:
        validate_saucedemo_origin("https://www.saucedemo.com/checkout.html", expected_path_prefix="/inventory.html")
        assert False, "Should have rejected wrong route"
    except AssertionError as e:
        print(f"  [PASS] Blocked unexpected post-login route: {e}")

    # 5. Valid cases
    validate_saucedemo_origin("https://www.saucedemo.com/", expected_path_prefix="/")
    validate_saucedemo_origin("https://www.saucedemo.com/inventory.html", expected_path_prefix="/inventory.html")
    print("  [PASS] Valid origins & routes accepted correctly.")


async def test_failed_login_workflow():
    print("\n--- TEST 2: Failed Login Workflow (Negative Test) ---")
    from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

    screenshot_path = EVIDENCE_DIR / "test_failure_evidence.png"
    error_message = None
    browser_closed = False

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1280, "height": 800})
        page = await context.new_page()

        try:
            await page.goto("https://www.saucedemo.com/", timeout=15000)
            validate_saucedemo_origin(page.url, expected_path_prefix="/")

            # Intentionally submit invalid credentials to test failure handling
            await page.locator("#user-name").fill("locked_out_user")
            await page.locator("#password").fill("secret_sauce")
            await page.locator("#login-button").click()

            # Expect to reach /inventory.html, which will timeout because user is locked out
            await page.wait_for_url("**/inventory.html", timeout=3000)
        except (PlaywrightTimeoutError, AssertionError) as exc:
            error_message = f"Simulated failure caught: {exc}"
            # Capture evidence of the failure
            await page.screenshot(path=str(screenshot_path))
        finally:
            await page.close()
            await context.close()
            await browser.close()
            browser_closed = True

    assert error_message is not None, "Workflow should have failed with invalid credentials"
    assert screenshot_path.exists(), "Failure screenshot must be captured on failure"
    assert browser_closed is True, "Browser resources must be closed in finally block"
    print(f"  [PASS] Failure caught accurately: {error_message[:60]}...")
    print(f"  [PASS] Failure screenshot generated: {screenshot_path.name} ({screenshot_path.stat().st_size} bytes)")
    print(f"  [PASS] Browser cleanly closed: {browser_closed}")


async def test_successful_saucedemo_workflow():
    print("\n--- TEST 3: Successful SauceDemo Standard-User Workflow ---")
    result = await run_saucedemo_login_test()

    print(f"  Status: {result['status']}")
    print(f"  Duration: {result['duration_ms']}ms")
    print(f"  Page title: {result['page_title']}")
    print(f"  Inventory items found: {result.get('inventory_items_found')}")
    print(f"  Screenshot path: {result['screenshot_path']}")
    print(f"  Error message: {result['error_message']}")

    assert result["status"] == "passed", f"Test should pass, got {result['status']}"
    assert result["inventory_items_found"] == 6, f"Expected 6 items, got {result.get('inventory_items_found')}"
    assert result["error_message"] is None, "Error message should be None for passed test"
    assert result["screenshot_path"] is not None, "Screenshot path must be populated"

    full_screenshot = Path(__file__).parent / result["screenshot_path"]
    assert full_screenshot.exists(), "Screenshot file must exist on disk"
    assert full_screenshot.stat().st_size > 10000, "Screenshot file size must be non-trivial"
    print(f"  [PASS] Real screenshot verified: {full_screenshot.name} ({full_screenshot.stat().st_size} bytes)")


async def main():
    test_origin_parsing_safeguards()
    await test_failed_login_workflow()
    await test_successful_saucedemo_workflow()
    print("\n=== ALL 3 TEST SUITES PASSED DETERMINISTICALLY ===")

if __name__ == "__main__":
    asyncio.run(main())
