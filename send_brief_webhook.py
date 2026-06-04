#!/usr/bin/env python3
"""
Send the Weekly Morning Brief via n8n webhook.
Reads HTML from /tmp/brief_email.html and POSTs it to n8n,
which handles the actual Gmail send.

Usage:
    python send_brief_webhook.py
    python send_brief_webhook.py --to "other@email.com"
    python send_brief_webhook.py --dry-run
"""

import json
import os
import sys
import argparse
import urllib.request
from datetime import datetime

# ── CONFIG ──────────────────────────────────────────────────
WEBHOOK_URL = os.environ.get(
    "N8N_WEBHOOK_URL",
    "https://operacionesomaha.app.n8n.cloud/webhook/send-weekly-brief"
)
DEFAULT_TO = "dante@omaha.pe"
SUBJECT_TEMPLATE = "📊 Weekly Morning Brief — {date}"
HTML_FILE = "/tmp/brief_email.html"
# ────────────────────────────────────────────────────────────


def send_via_webhook(to_addr, subject, html_body, dry_run=False):
    payload = {
        "to": to_addr,
        "subject": subject,
        "html": html_body,
    }

    if dry_run:
        print(f"DRY RUN — would POST to: {WEBHOOK_URL}")
        print(f"To: {to_addr}")
        print(f"Subject: {subject}")
        print(f"HTML length: {len(html_body)} chars")
        return True

    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            WEBHOOK_URL,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            status = resp.status
            body = resp.read().decode("utf-8")

        if status in (200, 201):
            print(f"Webhook OK ({status}): {body}", file=sys.stderr)
            return True
        else:
            print(f"Webhook returned {status}: {body}", file=sys.stderr)
            return False

    except Exception as e:
        print(f"ERROR calling webhook: {e}", file=sys.stderr)
        return False


def main():
    parser = argparse.ArgumentParser(description="Send brief via n8n webhook")
    parser.add_argument("--to", default=DEFAULT_TO)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--file", default=HTML_FILE)
    args = parser.parse_args()

    if not os.path.exists(args.file):
        print(f"ERROR: {args.file} not found.", file=sys.stderr)
        sys.exit(1)

    with open(args.file, "r", encoding="utf-8") as f:
        html_body = f.read()

    if len(html_body.strip()) < 50:
        print(f"ERROR: {args.file} looks empty ({len(html_body)} chars).", file=sys.stderr)
        sys.exit(1)

    subject = SUBJECT_TEMPLATE.format(date=datetime.now().strftime("%B %d, %Y"))
    success = send_via_webhook(args.to, subject, html_body, dry_run=args.dry_run)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
