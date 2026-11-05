"""Send email through Azure Communication Services (ACS), with its REST API.

Configured by two app settings (environment variables), both set in Azure:
- ACS_CONNECTION_STRING: the Communication Services resource's connection string,
  "endpoint=https://<name>.communication.azure.com/;accesskey=<base64 key>".
- MAIL_SENDER: the address mail comes from, e.g. "DoNotReply@<id>.azurecomm.net"
  (the Azure-managed domain linked to that resource).
Without them, sending is off: send() returns False and nothing leaves the app.

Requests are signed with the access key (HMAC-SHA256, ACS's "HMAC authentication"),
so only the standard library is needed.

Azure's limits: with its free Azure-managed domain, 5 emails a minute and 10 an hour
for the whole subscription (a custom domain: 30 a minute, 100 an hour). Over them ACS
answers 429. So batches go at a pace (MAIL_PAUSE seconds between emails) and in chunks
(MAIL_PER_RUN per hourly run), both app settings; see docs/processes/EMAIL.md.
"""
import base64
import hashlib
import hmac
import json
import os
import urllib.error
import urllib.request
from email.utils import formatdate
from urllib.parse import urlsplit

API = "/emails:send?api-version=2023-03-31"
THROTTLED = 429  # ACS: over the sending limits
last_status = None  # HTTP status of the last failed send (None: sent, off, or no answer)
last_error = None   # why the last send failed, for the email log


def per_run():
    """How many emails one run of the daily job may send (Azure-managed domain: 10 an hour,
    so 9 leaves one for the admins' test buttons)."""
    return int(os.environ.get("MAIL_PER_RUN", "9"))


def pause():
    """Seconds between two emails of a batch (13 keeps under 5 a minute)."""
    return float(os.environ.get("MAIL_PAUSE", "13"))


def settings():
    """(endpoint, access key, sender), or None when email isn't configured."""
    conn = os.environ.get("ACS_CONNECTION_STRING", "")
    sender = os.environ.get("MAIL_SENDER", "")
    parts = dict(p.split("=", 1) for p in conn.split(";") if "=" in p)
    endpoint, key = parts.get("endpoint", "").rstrip("/"), parts.get("accesskey", "")
    return (endpoint, key, sender) if endpoint and key and sender else None


def enabled():
    return settings() is not None


def signed_headers(endpoint, key, body, date=None):
    """The headers of an ACS request signed with its access key."""
    host = urlsplit(endpoint).netloc
    date = date or formatdate(usegmt=True)
    content_hash = base64.b64encode(hashlib.sha256(body).digest()).decode()
    to_sign = f"POST\n{API}\n{date};{host};{content_hash}"
    signature = base64.b64encode(hmac.new(base64.b64decode(key), to_sign.encode(),
                                          hashlib.sha256).digest()).decode()
    return {"Content-Type": "application/json", "x-ms-date": date,
            "x-ms-content-sha256": content_hash,
            "Authorization": "HMAC-SHA256 SignedHeaders=x-ms-date;host;x-ms-content-sha256"
                             f"&Signature={signature}"}


def message(sender, to, name, subject, text, html):
    return {"senderAddress": sender,
            "recipients": {"to": [{"address": to, "displayName": name or to}]},
            "content": {"subject": subject, "plainText": text, "html": html}}


def send(to, name, subject, text, html):
    """Send one email. True when ACS accepted it, False when email is off or it failed
    (the reason goes to the app's log)."""
    global last_status, last_error
    last_status = last_error = None
    config = settings()
    if config is None:
        return False
    endpoint, key, sender = config
    body = json.dumps(message(sender, to, name, subject, text, html)).encode()
    request = urllib.request.Request(endpoint + API, data=body, method="POST",
                                     headers=signed_headers(endpoint, key, body))
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            if response.status != 202:
                last_error = f"HTTP {response.status}"
            return response.status == 202
    except (urllib.error.URLError, TimeoutError) as e:
        if isinstance(e, urllib.error.HTTPError):
            last_status = e.code
        detail = e.read().decode(errors="replace")[:300] if isinstance(e, urllib.error.HTTPError) else e
        last_error = (f"HTTP {last_status}: {detail}" if last_status else str(detail))[:500]
        print(f"mailer: sending to {to} failed: {detail}", flush=True)
        return False
