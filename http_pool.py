#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GET JSON προς τις δημόσιες βάσεις με επαναχρησιμοποίηση συνδέσεων (keep-alive).

Το urllib ανοίγει νέα σύνδεση TCP+TLS σε κάθε αίτημα (~0,1-0,3 s). Εδώ κάθε
νήμα κρατά μία ανοιχτή σύνδεση ανά υπηρεσία.

Ασφάλεια:
  • Μόνο HTTPS και μόνο προς τις υπηρεσίες της λίστας ALLOWED_HOSTS — ακόμη
    κι αν κάποιο κομμάτι URL προέρχεται από το κείμενο (π.χ. DOI), δεν μπορεί
    να στείλει αίτημα αλλού (προστασία τύπου SSRF).
  • Πλήρης έλεγχος πιστοποιητικού TLS (ssl.create_default_context).
  • Όριο μεγέθους απάντησης (MAX_RESPONSE_BYTES) — μια τεράστια/κακόβουλη
    απάντηση δεν γεμίζει τη μνήμη.
  • Χωρίς ακολούθηση redirects· τα μηνύματα σφάλματος δεν περιέχουν το URL
    (που μπορεί να έχει API key).
Αν υπάρχει ρυθμισμένος proxy (HTTPS_PROXY κ.λπ.), χρησιμοποιείται το urllib
όπως πριν, ώστε να λειτουργεί και σε δίκτυα πανεπιστημίων.
"""

import http.client
import json
import socket
import ssl
import threading
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional

ALLOWED_HOSTS = frozenset({
    "api.crossref.org",
    "api.openalex.org",
    "en.wikipedia.org",
    "el.wikipedia.org",
})
MAX_RESPONSE_BYTES = 8 * 1024 * 1024

_local = threading.local()
_ssl_context = ssl.create_default_context()
_RETRYABLE = (http.client.RemoteDisconnected, http.client.CannotSendRequest,
              http.client.BadStatusLine, BrokenPipeError, ConnectionResetError)


class ResponseTooLarge(ValueError):
    pass


def _validate(url: str) -> urllib.parse.SplitResult:
    parts = urllib.parse.urlsplit(url)
    if (parts.scheme != "https" or parts.hostname not in ALLOWED_HOSTS
            or parts.username or parts.password or parts.port not in (None, 443)):
        raise ValueError("blocked request: host not allowed")
    return parts


def _uses_proxy(host: str) -> bool:
    proxies = urllib.request.getproxies()
    return bool(proxies.get("https")) and not urllib.request.proxy_bypass(host)


def _read_limited(resp) -> bytes:
    body = resp.read(MAX_RESPONSE_BYTES + 1)
    if len(body) > MAX_RESPONSE_BYTES:
        raise ResponseTooLarge("response too large")
    return body


def _connection(host: str, timeout: float) -> http.client.HTTPSConnection:
    pool: Dict[str, http.client.HTTPSConnection] = getattr(_local, "pool", None) or {}
    _local.pool = pool
    conn = pool.get(host)
    if conn is None:
        conn = http.client.HTTPSConnection(host, timeout=timeout, context=_ssl_context)
        pool[host] = conn
    conn.timeout = timeout
    if conn.sock is not None:
        conn.sock.settimeout(timeout)
    return conn


def _drop(host: str) -> None:
    pool = getattr(_local, "pool", None) or {}
    conn = pool.pop(host, None)
    if conn is not None:
        conn.close()


def get_json(url: str, headers: Optional[Dict[str, str]] = None,
             timeout: float = 8.0) -> Any:
    """GET → JSON. Σε HTTP ≥ 300 σηκώνει urllib.error.HTTPError (με .code και
    .headers, όπως το urllib), σε πρόβλημα δικτύου OSError/http.client σφάλμα."""
    parts = _validate(url)
    host = parts.hostname
    headers = dict(headers or {})
    headers.setdefault("Accept", "application/json")

    if _uses_proxy(host):
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(_read_limited(r))

    path = parts.path or "/"
    if parts.query:
        path += "?" + parts.query
    for attempt in (0, 1):
        conn = _connection(host, timeout)
        try:
            conn.request("GET", path, headers=headers)
            resp = conn.getresponse()
            body = _read_limited(resp)
        except _RETRYABLE:
            _drop(host)                      # η παλιά σύνδεση έκλεισε από τον server
            if attempt == 0:
                continue
            raise
        except (socket.timeout, OSError, http.client.HTTPException, ValueError):
            _drop(host)
            raise
        if resp.will_close:
            _drop(host)
        if resp.status >= 300:
            raise urllib.error.HTTPError(f"https://{host}{parts.path}", resp.status,
                                         resp.reason, resp.headers, None)
        return json.loads(body)
    raise OSError("connection failed")      # δεν φτάνει εδώ — για τον type checker
