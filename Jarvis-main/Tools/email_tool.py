"""
Email Tool for JARVIS 2.0
Robust 3-Tier Autonomous Email Engine:
1. Tier 1: Direct SMTP Engine (smtplib with TLS/SSL using SENDER_EMAIL & SENDER_PASSWORD / App Password)
2. Tier 2: Google Apps Script Web App (if APPS_SCRIPT_URL configured)
3. Tier 3: Autonomous Web Mail Browser Compose (opens Gmail web compose with pre-filled fields)
"""

import os
import re
import sys
import time
import json
import smtplib
import urllib.parse
import webbrowser
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from typing import Dict, Any, Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

# Environment credentials
SENDER_EMAIL = os.getenv("SENDER_EMAIL", os.getenv("EMAIL_USER", ""))
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD", os.getenv("EMAIL_PASSWORD", os.getenv("GMAIL_APP_PASSWORD", "")))
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
APPS_SCRIPT_URL = os.getenv("APPS_SCRIPT_URL", "")


def send_email(to: str, subject: str = "Message from JARVIS", body: str = "", attachment_path: Optional[str] = None, cc: str = "", bcc: str = "") -> Dict[str, Any]:
    """
    Sends an email using the 3-Tier Autonomous Engine.
    Returns result dict with status, method_used, and user message.
    """
    to = (to or "").strip()
    subject = (subject or "Message from JARVIS").strip()
    body = (body or "").strip()

    if not to or "@" not in to:
        return {
            "status": "error",
            "error": "Invalid recipient email address.",
            "response": "Sir, please specify a valid recipient email address."
        }

    # ── Tier 1: Native SMTP Engine ──────────────────────────────────────────
    sender_email = os.getenv("SENDER_EMAIL", os.getenv("EMAIL_USER", ""))
    sender_pass = os.getenv("SENDER_PASSWORD", os.getenv("EMAIL_PASSWORD", os.getenv("GMAIL_APP_PASSWORD", "")))

    if sender_email and sender_pass and "YOUR_" not in sender_pass:
        try:
            print(f"[EmailEngine] Attempting Tier 1 SMTP via {SMTP_SERVER}:{SMTP_PORT}...")
            msg = MIMEMultipart()
            msg["From"] = sender_email
            msg["To"] = to
            msg["Subject"] = subject
            if cc:
                msg["Cc"] = cc

            msg.attach(MIMEText(body, "plain", "utf-8"))

            if attachment_path and os.path.exists(attachment_path):
                with open(attachment_path, "rb") as f:
                    part = MIMEBase("application", "octet-stream")
                    part.set_payload(f.read())
                    encoders.encode_base64(part)
                    part.add_header(
                        "Content-Disposition",
                        f"attachment; filename={os.path.basename(attachment_path)}"
                    )
                    msg.attach(part)

            server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=15)
            server.starttls()
            server.login(sender_email, sender_pass)

            recipients = [to]
            if cc:
                recipients.append(cc)
            if bcc:
                recipients.append(bcc)

            server.sendmail(sender_email, recipients, msg.as_string())
            server.quit()

            success_msg = f"✓ Email successfully sent to {to} via SMTP."
            print(f"[EmailEngine] {success_msg}")
            return {
                "status": "success",
                "method": "SMTP",
                "response": f"Sir, your email to {to} has been sent successfully."
            }
        except Exception as e:
            print(f"[EmailEngine] Tier 1 SMTP failed: {e}")

    # ── Tier 2: Google Apps Script Bridge ─────────────────────────────────────
    script_url = os.getenv("APPS_SCRIPT_URL", "")
    if script_url and "YOUR_" not in script_url and "http" in script_url:
        try:
            print("[EmailEngine] Attempting Tier 2 Google Apps Script Bridge...")
            from Brain.google_workspace_client import get_google_client
            client = get_google_client()
            res = client.gmail_send(to, subject, body, cc, bcc)
            if res.get("status") == "success":
                return {
                    "status": "success",
                    "method": "AppsScript",
                    "response": f"Sir, your email to {to} has been sent via Google Workspace."
                }
        except Exception as e:
            print(f"[EmailEngine] Tier 2 Apps Script failed: {e}")

    # ── Tier 3: Autonomous Web Mail Compose Fallback ──────────────────────────
    try:
        print("[EmailEngine] Launching Tier 3 Autonomous Web Mail Compose...")
        encoded_to = urllib.parse.quote(to)
        encoded_su = urllib.parse.quote(subject)
        encoded_body = urllib.parse.quote(body)

        web_compose_url = f"https://mail.google.com/mail/?view=cm&fs=1&to={encoded_to}&su={encoded_su}&body={encoded_body}"
        webbrowser.open(web_compose_url)

        return {
            "status": "success",
            "method": "WebCompose",
            "response": f"Sir, I have opened Gmail web composer with your email draft to {to}. Please click send."
        }
    except Exception as e:
        print(f"[EmailEngine] Tier 3 Web Compose failed: {e}")
        return {
            "status": "error",
            "error": str(e),
            "response": "Sir, I encountered an issue attempting to send the email."
        }


def parse_email_request(text: str) -> Dict[str, str]:
    """
    Extract recipient, subject, and body from natural language text.
    Examples:
    - "send an email to test@gmail.com with subject Hello and body How are you"
    - "send email to test@gmail.com"
    """
    text_clean = text.strip()

    # Extract email address
    email_match = re.search(r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', text_clean)
    to_addr = email_match.group(1) if email_match else ""

    # Extract subject
    subj_match = re.search(r'(?:subject|with subject)\s+:?\s*([^.\n,]+?)(?=\s+(?:and body|body|message|$))', text_clean, re.IGNORECASE)
    subject = subj_match.group(1).strip() if subj_match else "Message from JARVIS"

    # Extract body
    body_match = re.search(r'(?:body|message|saying)\s+:?\s*(.+)$', text_clean, re.IGNORECASE)
    body = body_match.group(1).strip() if body_match else ""

    if not body and to_addr:
        # Fallback body extraction: remove command words and email
        body = text_clean
        for r in ["send an email to", "send email to", "email to", "email", to_addr, "with subject", subject]:
            body = body.replace(r, "")
        body = body.strip(" :,-")

    if not body:
        body = f"Hello,\n\nThis is an automated message sent via JARVIS 2.0 AI OS.\n\nBest regards,\nJARVIS"

    return {
        "to": to_addr,
        "subject": subject,
        "body": body
    }
