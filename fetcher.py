"""
Fetcher module - fetches document content from Tencent Docs.

Supports:
  - Public documents: fetched directly via opendoc API
  - Private documents: opens browser for user login, grabs cookies, then fetches
"""

import json
import os
import re
import time

import requests

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

OPENDOC_API = "https://docs.qq.com/dop-api/opendoc"
COOKIE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".cookies.json")

_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
)


def extract_doc_id(url):
    """Extract doc ID from a Tencent Docs URL."""
    match = re.search(r"/doc/([A-Za-z0-9_-]+)", url)
    if not match:
        raise ValueError(
            f"Invalid Tencent Docs URL: {url}\n"
            f"Expected format: https://docs.qq.com/doc/XXXXX"
        )
    return match.group(1)


def _build_headers(url, cookie_str=None):
    headers = {
        "Referer": url,
        "User-Agent": _USER_AGENT,
    }
    if cookie_str:
        headers["Cookie"] = cookie_str
    return headers


def _load_saved_cookies():
    """Load cookies from saved file if exists."""
    if os.path.isfile(COOKIE_FILE):
        with open(COOKIE_FILE, "r") as f:
            cookies = json.load(f)
        return "; ".join(f'{c["name"]}={c["value"]}' for c in cookies)
    return None


def _save_cookies(cookies):
    """Save cookies to file."""
    with open(COOKIE_FILE, "w") as f:
        json.dump(cookies, f, indent=2)


def _login_via_browser(url):
    """
    Open a browser window for user to log in to Tencent Docs.
    Returns cookie string after successful login.
    """
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
    except ImportError:
        raise RuntimeError(
            "This document requires login.\n"
            "Please install selenium: pip install selenium chromedriver-autoinstaller"
        )

    try:
        import chromedriver_autoinstaller
        chromedriver_autoinstaller.install()
    except Exception:
        pass

    options = Options()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1200,900")

    print()
    print("  Opening browser for login...")
    print("  Please scan QR code or enter credentials.")
    print()

    driver = webdriver.Chrome(options=options)
    try:
        driver.get(url)

        # Wait for login (detect uid/openid cookies)
        initial_count = len(driver.get_cookies())
        timeout = 300
        start = time.time()

        while time.time() - start < timeout:
            cookies = driver.get_cookies()
            names = {c["name"] for c in cookies}
            login_indicators = {"uid", "uid_key", "openid", "nickname"}

            if names & login_indicators:
                print("  Login detected!")
                time.sleep(3)  # let cookies settle
                break

            if len(cookies) > initial_count + 5:
                print("  Login detected!")
                time.sleep(3)
                break

            remaining = int(timeout - (time.time() - start))
            print(f"\r  Waiting for login... ({remaining}s remaining)", end="", flush=True)
            time.sleep(2)
        else:
            print("\n  Login timeout. Trying with available cookies anyway...")

        print()
        all_cookies = driver.get_cookies()
        _save_cookies(all_cookies)
        cookie_str = "; ".join(f'{c["name"]}={c["value"]}' for c in all_cookies)
        print(f"  Saved {len(all_cookies)} cookies.")
        return cookie_str

    finally:
        try:
            driver.quit()
        except Exception:
            pass


def _fetch_opendoc(url, doc_id, cookie_str=None):
    """Fetch document via opendoc API. Returns parsed JSON or raises."""
    params = {"id": doc_id, "outformat": "1", "normal": "1"}
    headers = _build_headers(url, cookie_str)

    resp = requests.get(OPENDOC_API, params=params, headers=headers, verify=False)
    if resp.status_code != 200:
        raise RuntimeError(f"API returned status {resp.status_code}")

    return resp.json()


def _extract_content(data):
    """Extract title, content_text, mutations from opendoc response."""
    client_vars = data.get("clientVars", {})
    title = client_vars.get("title", "Untitled")

    collab = client_vars.get("collab_client_vars", {})
    iat = collab.get("initialAttributedText", {})
    text_entries = iat.get("text", [])

    if not text_entries:
        return title, None, None

    entry = text_entries[0]
    commands = entry.get("commands", [])
    if not commands:
        return title, None, None

    cmd = commands[0]
    mutations = cmd.get("mutations", [])

    content_text = ""
    for m in mutations:
        if m.get("ty") == "is":
            content_text = m.get("s", "")
            break

    if not content_text:
        return title, None, None

    return title, content_text, mutations


def _needs_login(data):
    """Check if the document requires login to view content."""
    client_vars = data.get("clientVars", {})

    # Check if user is logged in
    is_login = client_vars.get("isLogin", False)

    # Check if content is available
    collab = client_vars.get("collab_client_vars", {})
    iat = collab.get("initialAttributedText", {})
    text_entries = iat.get("text", [])

    if not text_entries:
        return True

    entry = text_entries[0]
    commands = entry.get("commands", [])
    if not commands:
        return True

    # Check if content is empty
    cmd = commands[0]
    mutations = cmd.get("mutations", [])
    has_content = any(m.get("ty") == "is" and m.get("s") for m in mutations)

    return not has_content


def fetch_document(url):
    """
    Fetch a Tencent Docs document.

    1. Try fetching without login (public docs)
    2. If content is empty, try saved cookies
    3. If still empty, open browser for login

    Returns (title, content_text, mutations) tuple.
    """
    doc_id = extract_doc_id(url)
    print(f"  Document ID: {doc_id}")

    # Attempt 1: fetch without cookies (public doc)
    print("  Trying public access...")
    data = _fetch_opendoc(url, doc_id)
    title, content_text, mutations = _extract_content(data)

    if content_text:
        print(f"  Title: {title}")
        print(f"  Content: {len(content_text)} chars, {len(mutations)} mutations")
        return title, content_text, mutations

    # Attempt 2: try saved cookies
    print("  Public access returned no content.")
    saved_cookies = _load_saved_cookies()
    if saved_cookies:
        print("  Trying saved cookies...")
        data = _fetch_opendoc(url, doc_id, saved_cookies)
        title, content_text, mutations = _extract_content(data)
        if content_text:
            print(f"  Title: {title}")
            print(f"  Content: {len(content_text)} chars, {len(mutations)} mutations")
            return title, content_text, mutations
        print("  Saved cookies expired or insufficient.")

    # Attempt 3: login via browser
    print("  This document requires login.")
    cookie_str = _login_via_browser(url)
    data = _fetch_opendoc(url, doc_id, cookie_str)
    title, content_text, mutations = _extract_content(data)

    if not content_text:
        raise RuntimeError(
            "Failed to fetch document content even after login.\n"
            "The document may not be accessible to your account."
        )

    print(f"  Title: {title}")
    print(f"  Content: {len(content_text)} chars, {len(mutations)} mutations")
    return title, content_text, mutations
