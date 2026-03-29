#!/usr/bin/env python3
"""
qqdown - Tencent Docs PDF Downloader
=====================================
Download any Tencent Docs document as PDF.

Usage:
    python main.py <url>
    python main.py https://docs.qq.com/doc/DWXJVY2V6SHFHanNz

Options:
    -o, --output   Output filename (default: auto-detect from title)
    --relogin      Force re-login even if saved cookies exist

Features:
    - Public documents: downloaded directly, no login needed
    - Private documents: opens browser for QR code / password login
    - Generates PDF compatible with macOS Preview, Chrome, WPS
"""

import argparse
import os
import re
import shutil
import subprocess
import sys

from fetcher import fetch_document
from parser import parse_to_html


def find_chrome():
    """Find Chrome executable path."""
    candidates = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        shutil.which("google-chrome"),
        shutil.which("chromium"),
    ]
    for c in candidates:
        if c and os.path.isfile(c):
            return c
    return None


def html_to_pdf_chrome(html_path, pdf_path):
    """Convert HTML to PDF using Chrome headless. Compatible with all PDF readers."""
    chrome = find_chrome()
    if not chrome:
        raise RuntimeError(
            "Google Chrome not found.\n"
            "Please install Chrome or set its path."
        )

    cmd = [
        chrome,
        "--headless",
        "--disable-gpu",
        "--no-sandbox",
        "--run-all-compositor-stages-before-draw",
        f"--print-to-pdf={pdf_path}",
        "--no-pdf-header-footer",
        f"file://{html_path}",
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if not os.path.isfile(pdf_path):
        raise RuntimeError(f"Chrome PDF generation failed:\n{result.stderr}")


def sanitize_filename(name):
    """Remove invalid characters from filename."""
    # Remove characters not allowed in filenames
    name = re.sub(r'[<>:"/\\|?*]', '', name)
    # Remove leading/trailing whitespace and dots
    name = name.strip().strip(".")
    # Limit length
    if len(name) > 100:
        name = name[:100]
    return name or "document"


def validate_url(url):
    """Validate and normalize a Tencent Docs URL."""
    # Accept bare doc IDs
    if re.match(r'^[A-Za-z0-9_-]+$', url):
        url = f"https://docs.qq.com/doc/{url}"

    # Strip query params for cleaner URL
    url = re.sub(r'\?.*$', '', url)

    if not re.search(r'docs\.qq\.com/doc/[A-Za-z0-9_-]+', url):
        print(f"Error: Invalid Tencent Docs URL: {url}")
        print(f"Expected: https://docs.qq.com/doc/XXXXX")
        sys.exit(1)

    return url


def main():
    ap = argparse.ArgumentParser(
        prog="qqdown",
        description="Download Tencent Docs documents as PDF",
    )
    ap.add_argument(
        "url",
        nargs="?",
        help="Tencent Docs URL (e.g. https://docs.qq.com/doc/XXXXX)",
    )
    ap.add_argument(
        "-o", "--output",
        help="Output PDF filename (default: auto from title)",
    )
    ap.add_argument(
        "--relogin",
        action="store_true",
        help="Force re-login, ignore saved cookies",
    )
    args = ap.parse_args()

    # If no URL provided, prompt for it
    url = args.url
    if not url:
        url = input("Enter Tencent Docs URL: ").strip()
        if not url:
            print("Error: No URL provided.")
            sys.exit(1)

    url = validate_url(url)

    print()
    print("=" * 55)
    print("  Tencent Docs PDF Downloader")
    print("=" * 55)
    print(f"  URL: {url}")
    print()

    # Handle --relogin: delete saved cookies
    if args.relogin:
        from fetcher import COOKIE_FILE
        if os.path.isfile(COOKIE_FILE):
            os.remove(COOKIE_FILE)
            print("  Cleared saved cookies.")

    # Step 1: Fetch document
    print("[1/3] Fetching document...")
    title, content_text, mutations = fetch_document(url)
    print()

    # Step 2: Parse to HTML
    print("[2/3] Parsing document...")
    html_content = parse_to_html(title, content_text, mutations)

    project_dir = os.path.dirname(os.path.abspath(__file__))
    html_path = os.path.join(project_dir, ".output.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    print()

    # Step 3: Convert to PDF
    print("[3/3] Generating PDF...")

    # Determine output filename
    if args.output:
        output_name = args.output
        if not output_name.endswith(".pdf"):
            output_name += ".pdf"
    else:
        # Remove surrounding markers like 《》
        clean_title = re.sub(r'^[《\u300a]+|[》\u300b]+$', '', title)
        output_name = sanitize_filename(clean_title) + ".pdf"

    output_path = os.path.join(os.getcwd(), output_name)

    try:
        html_to_pdf_chrome(html_path, output_path)
    except RuntimeError as e:
        print(f"  Chrome failed: {e}")
        print("  Falling back to WeasyPrint...")
        from weasyprint import HTML
        HTML(filename=html_path).write_pdf(
            output_path,
            presentational_hints=True,
            optimize_size=('fonts',),
        )

    # Cleanup temp HTML
    try:
        os.remove(html_path)
    except OSError:
        pass

    file_size = os.path.getsize(output_path)
    if file_size < 1024 * 1024:
        size_str = f"{file_size / 1024:.1f} KB"
    else:
        size_str = f"{file_size / 1024 / 1024:.1f} MB"

    print()
    print("=" * 55)
    print(f"  Done!")
    print(f"  File: {output_path}")
    print(f"  Size: {size_str}")
    print("=" * 55)


if __name__ == "__main__":
    main()
