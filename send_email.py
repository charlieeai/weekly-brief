#!/usr/bin/env python3
"""
Send the Weekly Morning Brief email via Gmail SMTP.
Reads HTML content from /tmp/brief_email.html and sends it.

Requires environment variable:
    GMAIL_APP_PASSWORD — 16-character App Password from Google Account

Usage:
    python send_email.py
    python send_email.py --to "other@email.com"
    python send_email.py --dry-run   # Print HTML to stdout, don't send
"""

import os
import sys
import smtplib
import argparse
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

SENDER = "charlieai@omaha.pe"
DEFAULT_TO = "christian@omaha.pe"
SUBJECT_TEMPLATE = "📊 Weekly Morning Brief — {date}"
HTML_FILE = "/tmp/brief_email.html"


def send_email(to_addr, subject, html_body, dry_run=False):
    if dry_run:
        print(f"DRY RUN — would send to: {to_addr}")
        print(f"Subject: {subject}")
        print(f"Body length: {len(html_body)} chars")
        print("--- HTML preview (first 500 chars) ---")
        print(html_body[:500])
        return True

    app_password = os.environ.get("GMAIL_APP_PASSWORD")
    if not app_password:
        print("ERROR: GMAIL_APP_PASSWORD environment variable not set.", file=sys.stderr)
        print("Generate one at: myaccount.google.com → Security → App passwords", file=sys.stderr)
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"Charlie AI <{SENDER}>"
    msg["To"] = to_addr
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(SENDER, app_password)
            server.send_message(msg)
        print(f"Email sent to {to_addr}", file=sys.stderr)
        return True
    except smtplib.SMTPAuthenticationError:
        print("ERROR: SMTP auth failed. Check GMAIL_APP_PASSWORD and that 2FA is enabled.", file=sys.stderr)
        return False
    except Exception as e:
        print(f"ERROR sending email: {e}", file=sys.stderr)
        return False


def main():
    parser = argparse.ArgumentParser(description="Send Weekly Morning Brief email")
    parser.add_argument("--to", default=DEFAULT_TO, help=f"Recipient (default: {DEFAULT_TO})")
    parser.add_argument("--dry-run", action="store_true", help="Don't send, just print preview")
    parser.add_argument("--file", default=HTML_FILE, help=f"HTML file to send (default: {HTML_FILE})")
    args = parser.parse_args()

    if not os.path.exists(args.file):
        print(f"ERROR: {args.file} not found. Claude should create this file first.", file=sys.stderr)
        sys.exit(1)

    with open(args.file, "r", encoding="utf-8") as f:
        html_body = f.read()

    if len(html_body.strip()) < 50:
        print(f"ERROR: {args.file} is too short ({len(html_body)} chars). Looks empty.", file=sys.stderr)
        sys.exit(1)

    date_str = datetime.now().strftime("%B %d, %Y")
    subject = SUBJECT_TEMPLATE.format(date=date_str)

    success = send_email(args.to, subject, html_body, dry_run=args.dry_run)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
