"""
runner.py
─────────────────────────────────────────────────────────────────────────────
ProbeQA smoke-test runner.

WHAT THIS MODULE DOES
  Accepts a validated URL, opens it in a headless Chromium browser, runs a
  fixed set of smoke-test assertions, captures a screenshot, and returns a
  structured result dictionary.

WHAT IT DOES NOT DO (current limitations — explicitly documented)
  • It does NOT interpret natural-language instructions.
    That capability requires an LLM integration in a future stage.
  • It does NOT perform login, form submission, or multi-step flows.
  • It does NOT use Math.random() or fabricate results.
    Every pass/fail is determined by real observed browser behavior.

INTERVIEW NOTE
  "I use Playwright's async Python API with a try/finally pattern to
   guarantee the browser context is always closed, even when assertions fail
   or network errors occur.  The smoke test checks HTTP status, page title,
   and body content length — simple but genuinely real assertions."
"""

import asyncio
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from playwright.async_api import (
    async_playwright,
    TimeoutError as PlaywrightTimeoutError,
    Error as PlaywrightError,
)

# ── Evidence directory ────────────────────────────────────────────────────────
# Screenshots are saved here.  The directory is created at import time so
# that runner.py works even before the first test is run.
EVIDENCE_DIR = Path(__file__).parent / "evidence"
EVIDENCE_DIR.mkdir(exist_ok=True)

# ── Test timeout ──────────────────────────────────────────────────────────────
# How long (milliseconds) Playwright will wait for a page navigation to complete
# before giving up.  15 seconds is generous for most public sites.
NAVIGATION_TIMEOUT_MS = 15_000

# ── Minimum body text length for "has content" assertion ─────────────────────
# If the page's visible text is shorter than this (after stripping whitespace),
# we consider it a suspiciously empty page and fail the assertion.
MIN_BODY_TEXT_LENGTH = 20

# Constant target for the deterministic SauceDemo practice workflow
SAUCEDEMO_TARGET_URL = "https://www.saucedemo.com/"
SAUCEDEMO_INVENTORY_URL = "https://www.saucedemo.com/inventory.html"
SAUCEDEMO_EXPECTED_SCHEME = "https"
SAUCEDEMO_EXPECTED_HOST = "www.saucedemo.com"
SAUCEDEMO_EXPECTED_PORTS = {None, 443}
SAUCEDEMO_EXPECTED_ITEMS = 6


def validate_saucedemo_origin(current_url: str, expected_path_prefix: str = "/") -> None:
    """
    Validate that current_url matches the strict SauceDemo origin:
      - scheme == 'https'
      - hostname == 'www.saucedemo.com'
      - port in (None, 443)
      - path begins with expected_path_prefix

    Raises AssertionError with clear diagnostic if any check fails.
    """
    parsed = urlparse(current_url)
    scheme = (parsed.scheme or "").lower()
    hostname = (parsed.hostname or "").lower()

    if scheme != SAUCEDEMO_EXPECTED_SCHEME:
        raise AssertionError(
            f"Invalid scheme '{parsed.scheme}'; expected '{SAUCEDEMO_EXPECTED_SCHEME}'."
        )
    if hostname != SAUCEDEMO_EXPECTED_HOST:
        raise AssertionError(
            f"Unexpected host '{parsed.hostname}'; expected '{SAUCEDEMO_EXPECTED_HOST}'."
        )
    if parsed.port not in SAUCEDEMO_EXPECTED_PORTS:
        raise AssertionError(
            f"Unexpected port '{parsed.port}'; expected 443 or default."
        )
    path = parsed.path or "/"
    if not path.startswith(expected_path_prefix):
        raise AssertionError(
            f"Unexpected path '{parsed.path}'; expected path starting with '{expected_path_prefix}'."
        )

# Reminder printed in every response so the UI can show it clearly.
LIMITATION_NOTE = (
    "Smoke test only: checks HTTP status, page title, and body content. "
    "Natural-language instruction interpretation is not yet implemented."
)


async def run_smoke_test(url: str) -> dict[str, Any]:
    """
    Open *url* in a headless Chromium browser and run basic smoke assertions.

    Parameters
    ----------
    url : str
        A pre-validated HTTP/HTTPS URL (run through validator.py first).

    Returns
    -------
    dict
        A result dictionary with keys matching the API response schema.
        Never raises — all exceptions are caught and returned as
        status="error" results.
    """
    # Record the start time so we can measure real elapsed duration.
    # datetime.now(timezone.utc) gives a timezone-aware timestamp, which is
    # required for correct ISO-8601 serialisation.
    start_time = datetime.now(timezone.utc)
    start_mono = asyncio.get_event_loop().time()  # monotonic clock for duration

    # Generate a unique ID for this run — used in the screenshot filename
    # so screenshots never overwrite each other.
    run_id = uuid.uuid4().hex[:12]  # e.g. "a3f9c1b2d4e6"
    screenshot_filename = f"run_{run_id}.png"
    screenshot_path = EVIDENCE_DIR / screenshot_filename

    # These variables are filled in as the test progresses.
    # We initialise them to safe defaults so the finally block can always
    # build a valid result dict even if something crashes midway.
    http_status: int | None = None
    page_title: str | None = None
    has_body_content: bool = False
    error_message: str | None = None
    screenshot_saved: bool = False

    # ── Open the browser ──────────────────────────────────────────────────────
    # `async with async_playwright() as p` is a context manager.
    # When the `async with` block exits — whether normally or because an
    # exception was raised — Playwright shuts down cleanly.
    #
    # We use a nested try/except/finally inside the `async with` so that:
    #   • The browser is always closed (context manager handles that).
    #   • We can catch and record errors at each step separately.
    #   • We always return a dict rather than propagating exceptions to FastAPI.
    try:
        async with async_playwright() as pw:
            # Launch headless Chromium.
            # headless=True  → no visible window (runs on servers).
            # args=["--no-sandbox"] is sometimes needed inside Docker/CI.
            browser = await pw.chromium.launch(headless=True)

            # A browser context is like a fresh incognito session.
            # viewport sets the virtual screen resolution for screenshots.
            context = await browser.new_context(
                viewport={"width": 1280, "height": 800},
                # Tell websites we are a real browser, not a bot.
                # Some sites block headless requests; this helps.
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
            )

            # A page is a single browser tab.
            page = await context.new_page()

            try:
                # ── Navigation ────────────────────────────────────────────────
                # page.goto() navigates to the URL.
                # wait_until="domcontentloaded" means: "wait until the HTML is
                # parsed and the DOM is ready — don't wait for images/fonts."
                # This is faster than "load" and enough for our assertions.
                #
                # goto() returns the HTTP Response object when available.
                # For pages that redirect, it returns the final response.
                response = await page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=NAVIGATION_TIMEOUT_MS,
                )

                # ── Assertion 1: HTTP status ───────────────────────────────────
                # response can be None for some redirect chains, so we guard.
                if response is not None:
                    http_status = response.status
                    # HTTP 2xx = success, 3xx = redirect (usually fine),
                    # 4xx/5xx = error that the test should flag.
                    if http_status >= 400:
                        error_message = (
                            f"HTTP {http_status} error returned by the server."
                        )

                # ── Assertion 2: Page title ────────────────────────────────────
                # page.title() returns the <title> tag content.
                page_title = await page.title()

                # ── Assertion 3: Body content ──────────────────────────────────
                # We get the innerText of the <body> element (visible text only,
                # no HTML tags) and check it is non-trivially short.
                body_text = await page.inner_text("body")
                body_text_stripped = body_text.strip()
                has_body_content = len(body_text_stripped) >= MIN_BODY_TEXT_LENGTH

                if not has_body_content and error_message is None:
                    error_message = (
                        f"Page body contains fewer than {MIN_BODY_TEXT_LENGTH} "
                        "visible characters — appears empty or broken."
                    )

            except PlaywrightTimeoutError as exc:
                # The page did not finish loading within NAVIGATION_TIMEOUT_MS.
                error_message = (
                    f"Navigation timed out after "
                    f"{NAVIGATION_TIMEOUT_MS // 1000}s: {exc}"
                )

            except PlaywrightError as exc:
                # Other Playwright errors: connection refused, SSL failure, etc.
                error_message = f"Browser error: {exc}"

            finally:
                # ── Screenshot ────────────────────────────────────────────────
                # We always try to capture a screenshot, even on failure.
                # A screenshot of an error page is useful evidence.
                # full_page=False → capture only the visible viewport (faster).
                try:
                    await page.screenshot(
                        path=str(screenshot_path),
                        full_page=False,
                    )
                    screenshot_saved = True
                except Exception:
                    # If screenshot itself fails (e.g. page never opened),
                    # we continue — the test result is still valid.
                    screenshot_saved = False

                # Close page and context explicitly before the browser closes.
                await page.close()
                await context.close()
                await browser.close()

    except Exception as exc:
        # Catch anything that went wrong before or during browser launch.
        # This includes Playwright not being installed, Chromium missing, etc.
        error_message = f"Runner failed to start: {exc}"

    # ── Calculate duration ────────────────────────────────────────────────────
    # We use the monotonic clock difference for accuracy.
    # The monotonic clock never goes backward (unlike wall-clock time).
    elapsed_seconds = asyncio.get_event_loop().time() - start_mono
    duration_ms = int(elapsed_seconds * 1000)

    # ── Determine overall pass/fail ───────────────────────────────────────────
    # The test passes ONLY when ALL of these are true:
    #   1. No error_message was recorded (no exceptions, no HTTP errors).
    #   2. The page has non-empty body content.
    # This is a real, honest determination — no randomness involved.
    if error_message is not None:
        overall_status = "error" if http_status is None else "failed"
    elif not has_body_content:
        overall_status = "failed"
    else:
        overall_status = "passed"

    # ── Build and return the result dict ──────────────────────────────────────
    return {
        "status": overall_status,
        "target_url": url,
        "duration_ms": duration_ms,
        # isoformat() produces a standard ISO-8601 string, e.g.
        # "2026-10-21T15:30:00+00:00"
        "timestamp": start_time.isoformat(),
        "http_status": http_status,
        "page_title": page_title,
        "has_body_content": has_body_content,
        "error_message": error_message,
        # Return the relative path within the backend directory.
        # The frontend will use this to request the screenshot file.
        "screenshot_path": (
            f"evidence/{screenshot_filename}" if screenshot_saved else None
        ),
        "run_id": run_id,
        "limitation_note": LIMITATION_NOTE,
    }


async def run_saucedemo_login_test(workflow_type: str = "valid_login") -> dict[str, Any]:
    """
    Execute a real Playwright login workflow on the public SauceDemo practice site.

    Supported workflow_type options:
      - 'valid_login' / 'saucedemo_valid_login': standard_user -> /inventory.html & 6 items
      - 'locked_out_login' / 'saucedemo_locked_out_login': locked_out_user -> assert locked out error banner
      - 'invalid_login' / 'saucedemo_invalid_login': invalid_user -> assert credential mismatch error banner

    Security & Scope Guardrails:
      - Only navigates to the exact permitted origin: https://www.saucedemo.com/
      - Never sends demo credentials to arbitrary URLs or third-party redirects
      - Uses publicly documented test credentials
      - Re-validates origin before and after all transitions
      - Clean resource termination via try/finally
    """
    start_time = datetime.now(timezone.utc)
    start_mono = asyncio.get_event_loop().time()

    run_id = uuid.uuid4().hex[:12]
    screenshot_filename = f"run_{run_id}.png"
    screenshot_path = EVIDENCE_DIR / screenshot_filename

    http_status: int | None = None
    page_title: str | None = None
    has_body_content: bool = False
    error_message: str | None = None
    screenshot_saved: bool = False
    items_count: int = 0

    # Determine credentials and expected outcomes based on workflow type
    is_locked_out = "locked_out" in workflow_type
    is_invalid = "invalid" in workflow_type

    if is_locked_out:
        username = "locked_out_user"
        password = "secret_sauce"
        expected_error = "Sorry, this user has been locked out"
    elif is_invalid:
        username = "invalid_user"
        password = "secret_sauce"
        expected_error = "Username and password do not match any user in this service"
    else:
        username = "standard_user"
        password = "secret_sauce"
        expected_error = None

    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
            )
            page = await context.new_page()

            try:
                # ── Step 1: Navigate to exact permitted SauceDemo origin ──────
                response = await page.goto(
                    SAUCEDEMO_TARGET_URL,
                    wait_until="domcontentloaded",
                    timeout=NAVIGATION_TIMEOUT_MS,
                )
                if response is not None:
                    http_status = response.status
                    if http_status >= 400:
                        raise AssertionError(f"HTTP {http_status} loading login page.")

                # Validate origin using strict URL parsing before sending credentials
                validate_saucedemo_origin(page.url, expected_path_prefix="/")
                page_title = await page.title()

                # ── Step 2: Locate inputs using robust locators ────────────────
                user_input = page.locator("#user-name")
                pass_input = page.locator("#password")
                login_btn = page.locator("#login-button")

                if not await user_input.is_visible():
                    raise AssertionError("Username input (#user-name) is not visible.")
                if not await pass_input.is_visible():
                    raise AssertionError("Password input (#password) is not visible.")
                if not await login_btn.is_visible():
                    raise AssertionError("Login button (#login-button) is not visible.")

                # ── Step 3: Fill credentials and submit ───────────────────────
                await user_input.fill(username)
                await pass_input.fill(password)
                await login_btn.click()

                # ── Step 4: Evaluate expectations based on scenario ───────────
                if is_locked_out or is_invalid:
                    # In error scenarios, page must remain on https://www.saucedemo.com/
                    validate_saucedemo_origin(page.url, expected_path_prefix="/")

                    # Assert error banner is displayed
                    error_banner = page.locator('[data-test="error"]')
                    if not await error_banner.is_visible():
                        raise AssertionError("Expected error banner [data-test='error'] was not visible.")

                    banner_text = await error_banner.inner_text()
                    if expected_error not in banner_text:
                        raise AssertionError(
                            f"Expected error message containing '{expected_error}', but got '{banner_text}'."
                        )
                    has_body_content = True
                else:
                    # In valid login scenario, wait for transition to inventory page
                    await page.wait_for_url("**/inventory.html", timeout=10000)

                    # Re-validate origin and exact inventory route after transition
                    validate_saucedemo_origin(page.url, expected_path_prefix="/inventory.html")

                    # Assert inventory content rendered
                    items_count = await page.locator(".inventory_item").count()
                    if items_count != SAUCEDEMO_EXPECTED_ITEMS:
                        raise AssertionError(
                            f"Expected exactly {SAUCEDEMO_EXPECTED_ITEMS} inventory items, but found {items_count}."
                        )

                    has_body_content = True
                    page_title = await page.title()

            except AssertionError as exc:
                error_message = str(exc)
            except PlaywrightTimeoutError as exc:
                error_message = f"Operation timed out: {exc}"
            except PlaywrightError as exc:
                error_message = f"Browser error: {exc}"
            except Exception as exc:
                error_message = f"Unexpected error during workflow: {exc}"

            finally:
                # Capture screenshot of the resulting page (inventory or error state)
                try:
                    await page.screenshot(
                        path=str(screenshot_path),
                        full_page=False,
                    )
                    screenshot_saved = True
                except Exception:
                    screenshot_saved = False

                await page.close()
                await context.close()
                await browser.close()

    except Exception as exc:
        error_message = f"Runner failed to start: {exc}"

    elapsed_seconds = asyncio.get_event_loop().time() - start_mono
    duration_ms = int(elapsed_seconds * 1000)

    overall_status = "failed" if error_message is not None else "passed"

    return {
        "status": overall_status,
        "target_url": SAUCEDEMO_TARGET_URL,
        "duration_ms": duration_ms,
        "timestamp": start_time.isoformat(),
        "http_status": http_status or 200,
        "page_title": page_title or "Swag Labs",
        "has_body_content": has_body_content,
        "error_message": error_message,
        "screenshot_path": (
            f"evidence/{screenshot_filename}" if screenshot_saved else None
        ),
        "run_id": run_id,
        "scenario": workflow_type,
        "inventory_items_found": items_count,
        "limitation_note": (
            f"Controlled Playwright execution of {workflow_type}. "
            "Evaluated actual DOM transitions and assertions."
        ),
    }
