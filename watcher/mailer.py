"""
SMTP sending. Credentials come from environment variables so nothing secret
ever lives in the repo:

    SMTP_HOST      e.g. smtp.gmail.com
    SMTP_PORT      587 (STARTTLS) or 465 (SSL)
    SMTP_USER      the mailbox that sends
    SMTP_PASSWORD  an app password, not the account password
    SMTP_FROM      optional; defaults to SMTP_USER
"""

import os
import smtplib
import ssl
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr, formatdate, make_msgid


class MailNotConfigured(Exception):
    pass


def configured():
    return all(os.environ.get(key) for key in ("SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD"))


def send(subject, html_body, text_body, recipients, from_name="Team Howe Reddit Watch"):
    if not recipients:
        raise MailNotConfigured("no recipients configured")
    if not configured():
        raise MailNotConfigured(
            "set SMTP_HOST, SMTP_USER and SMTP_PASSWORD (repository secrets)"
        )

    host = os.environ["SMTP_HOST"]
    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ["SMTP_USER"]
    password = os.environ["SMTP_PASSWORD"]
    sender = os.environ.get("SMTP_FROM", user)

    message = MIMEMultipart("alternative")
    message["Subject"] = Header(subject, "utf-8")
    message["From"] = formataddr((str(Header(from_name, "utf-8")), sender))
    message["To"] = ", ".join(recipients)
    message["Date"] = formatdate(localtime=True)
    message["Message-ID"] = make_msgid(domain="teamhowe.com")
    message["X-TeamHowe-Source"] = "reddit-watch"
    message.attach(MIMEText(text_body, "plain", "utf-8"))
    message.attach(MIMEText(html_body, "html", "utf-8"))

    context = ssl.create_default_context()
    if port == 465:
        server = smtplib.SMTP_SSL(host, port, context=context, timeout=45)
    else:
        server = smtplib.SMTP(host, port, timeout=45)
        server.ehlo()
        server.starttls(context=context)
        server.ehlo()
    try:
        server.login(user, password)
        server.sendmail(sender, recipients, message.as_string())
    finally:
        try:
            server.quit()
        except Exception:
            pass
    return len(recipients)
