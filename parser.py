"""
Parser module - converts Tencent Docs content to HTML for PDF export.

Strategy: extract clean text, apply paragraph-level formatting only (headings,
alignment). Skip per-character run formatting to avoid index mapping bugs.
Images are inserted where possible.
"""

import html as html_mod


HEADING_STYLES = {
    "000001": "h1",
    "000002": "h2",
    "000003": "h3",
    "000004": "h4",
    "000005": "h5",
}


def _strip_fields(text):
    """
    Remove field codes (\x13...\x14...\x15) from raw text.
    Keep display text between \x14 and \x15.
    For TOC/PAGEREF fields, remove everything.
    Returns clean text string.
    """
    result = []
    i = 0
    n = len(text)

    while i < n:
        ch = text[i]

        if ch == "\x13":
            # Read field instruction until \x14 or \x15
            j = i + 1
            instr = []
            while j < n and text[j] not in ("\x14", "\x15", "\x13"):
                instr.append(text[j])
                j += 1
            field_type = "".join(instr).strip().split()[0] if instr else ""

            if field_type in ("TOC", "PAGEREF"):
                # Skip entire field including nested
                depth = 1
                k = i + 1
                while k < n and depth > 0:
                    if text[k] == "\x13":
                        depth += 1
                    elif text[k] == "\x15":
                        depth -= 1
                    k += 1
                i = k
                continue

            # For HYPERLINK etc: skip instruction, keep display text
            # Advance to \x14 separator
            k = i + 1
            nested = 0
            while k < n:
                if text[k] == "\x13":
                    nested += 1
                elif text[k] == "\x14" and nested == 0:
                    break
                elif text[k] == "\x15":
                    if nested > 0:
                        nested -= 1
                    else:
                        break
                k += 1

            if k < n and text[k] == "\x14":
                i = k + 1  # skip past \x14, display text follows
            else:
                i = k + 1
            continue

        elif ch == "\x14":
            i += 1
            continue

        elif ch == "\x15":
            i += 1
            continue

        elif ch == "\b":
            i += 1
            continue

        else:
            result.append(ch)
            i += 1

    return "".join(result)


def _build_para_format_map(content_text, mutations):
    """
    Build a map of original \r positions -> paragraph format.
    Returns dict: orig_cr_index -> {"style": ..., "align": ...}
    """
    para_fmt = {}
    for m in mutations:
        if m.get("ty") != "mp":
            continue
        if m.get("mt") != "paragraph":
            continue
        pr = m.get("pr", {})
        if "paragraph" not in pr:
            continue

        ei = m.get("ei", 0)
        para = pr["paragraph"]
        pstyle = para.get("pStyle", {}).get("val", "")
        jc = para.get("jc", {}).get("val", "")
        para_fmt[ei - 1] = {"style": pstyle, "align": jc}

    return para_fmt


def _find_images(mutations):
    """Extract image info from 'ir' mutations. Returns dict: orig_index -> image info."""
    images = {}
    for m in mutations:
        if m.get("ty") != "ir":
            continue
        bi = m.get("bi", 0)
        pr = m.get("pr", {})
        if "drawing" not in pr:
            continue
        drawing = pr["drawing"]
        blip = drawing.get("blipFill", {}).get("blip", {})
        src = blip.get("src", "")
        if src:
            cx = drawing.get("extent", {}).get("cx", 0)
            images[bi] = {"src": src, "cx": cx}
    return images


def parse_to_html(title, content_text, mutations):
    """
    Convert Tencent Docs content into HTML.

    We split the ORIGINAL text by \r to get paragraphs, because paragraph
    format positions (from mutations) refer to original indices.
    Then we clean each paragraph line individually.
    """
    # Build paragraph format map (keyed by original \r position)
    para_fmt = _build_para_format_map(content_text, mutations)
    images = _find_images(mutations)

    # Split original text into paragraphs at \r
    orig_lines = content_text.split("\r")
    orig_pos = 0  # tracks position in original text

    paragraphs = []

    for line in orig_lines:
        line_end = orig_pos + len(line)  # position of the \r

        # Get paragraph format for this \r position
        pf = para_fmt.get(line_end, {})

        # Clean this line (strip field codes)
        clean_line = _strip_fields(line)

        # Check if there are images in this paragraph range
        img_html = ""
        for img_pos, img_info in images.items():
            if orig_pos <= img_pos < line_end:
                src = img_info["src"]
                cx = img_info.get("cx", 0)
                w_px = min(int(cx / 914400 * 96), 500) if cx else 0
                style = f' style="max-width:100%;width:{w_px}px"' if w_px else ' style="max-width:100%"'
                img_html += f'<img src="{html_mod.escape(src)}"{style}/>'

        # Escape HTML in the clean text
        escaped = html_mod.escape(clean_line)

        # Combine
        para_content = img_html + escaped if img_html else escaped

        paragraphs.append((para_content, pf))
        orig_pos = line_end + 1  # +1 for the \r

    # Assemble full HTML document
    html_parts = [
        "<!DOCTYPE html>",
        '<html lang="zh-CN">',
        "<head>",
        '<meta charset="utf-8">',
        f"<title>{html_mod.escape(title)}</title>",
        "<style>",
        CSS_STYLE,
        "</style>",
        "</head>",
        "<body>",
    ]

    for content, pf in paragraphs:
        style = pf.get("style", "")
        align = pf.get("align", "")

        tag = HEADING_STYLES.get(style, "p")

        attrs = ""
        if "center" in align.lower():
            attrs = ' style="text-align:center"'
        elif "right" in align.lower():
            attrs = ' style="text-align:right"'

        if not content.strip():
            html_parts.append(f"<{tag}{attrs}><br/></{tag}>")
        else:
            html_parts.append(f"<{tag}{attrs}>{content}</{tag}>")

    html_parts.append("</body>")
    html_parts.append("</html>")
    return "\n".join(html_parts)


CSS_STYLE = """
@page {
    size: A4;
    margin: 2cm 2.5cm;
}
body {
    font-family: "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei",
                 "WenQuanYi Micro Hei", "Noto Sans CJK SC", sans-serif;
    font-size: 11pt;
    line-height: 1.8;
    color: #333;
}
h1 {
    font-size: 20pt;
    color: #1a1a1a;
    border-bottom: 2px solid #333;
    padding-bottom: 6px;
    margin-top: 20pt;
    margin-bottom: 10pt;
}
h2 {
    font-size: 16pt;
    color: #2a2a2a;
    margin-top: 16pt;
    margin-bottom: 8pt;
}
h3 {
    font-size: 14pt;
    color: #3a3a3a;
    margin-top: 12pt;
    margin-bottom: 6pt;
}
h4, h5 {
    font-size: 12pt;
    margin-top: 10pt;
    margin-bottom: 4pt;
}
p {
    margin: 3pt 0;
}
img {
    max-width: 100%;
    margin: 6pt 0;
    display: block;
}
"""
