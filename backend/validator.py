"""
validator.py
─────────────────────────────────────────────────────────────────────────────
URL safety validator for ProbeQA.

WHY THIS EXISTS
  Users supply a URL string through the frontend form.  Before we hand that
  URL to a real browser, we must verify it cannot be used to:
    • Access local files      (file://)
    • Access private networks (192.168.x.x, 10.x.x.x, 172.16-31.x.x)
    • Access loopback         (127.0.0.1, ::1, localhost)
    • Access link-local       (169.254.x.x — AWS/GCP metadata endpoints)
    • Use non-HTTP schemes    (ftp://, javascript:, data:, etc.)

INTERVIEW NOTE
  "I validate user-supplied URLs on the server side before any network
   access occurs, using Python's ipaddress stdlib to block RFC-1918 ranges,
   loopback, and link-local addresses.  This prevents SSRF
   (Server-Side Request Forgery) attacks where an attacker tricks the server
   into fetching internal resources."
"""

import ipaddress
import socket
from urllib.parse import urlparse


class ValidationError(ValueError):
    """Raised when a URL fails a safety check.  Message is user-readable."""
    pass


# ── Allowed URL schemes ───────────────────────────────────────────────────────
ALLOWED_SCHEMES = {"http", "https"}


def validate_url(url: str) -> str:
    """
    Validate and normalise a URL string.

    Returns the cleaned URL string if all checks pass.
    Raises ValidationError with a descriptive message if any check fails.

    Parameters
    ----------
    url : str
        The raw URL provided by the user.
    """
    # ── 1. Basic structure check ──────────────────────────────────────────────
    # urlparse is tolerant — it won't raise on garbage input, so we check
    # the parsed components ourselves.
    url = url.strip()
    if not url:
        raise ValidationError("URL must not be empty.")

    parsed = urlparse(url)

    # ── 2. Scheme check ───────────────────────────────────────────────────────
    # parsed.scheme is always lowercase after urlparse.
    # We reject anything that isn't http or https.
    if parsed.scheme not in ALLOWED_SCHEMES:
        raise ValidationError(
            f"URL scheme '{parsed.scheme}' is not allowed. "
            "Only http:// and https:// are accepted."
        )

    # ── 3. Hostname presence check ────────────────────────────────────────────
    # A URL like "https://" with no host has an empty netloc.
    hostname = parsed.hostname  # strips port, lowercased
    if not hostname:
        raise ValidationError("URL must include a valid hostname.")

    # ── 4. Resolve hostname to IP and check for private/internal ranges ───────
    # We resolve first so that a crafted domain like "evil.com" that resolves
    # to 192.168.1.1 is also blocked (DNS rebinding prevention).
    try:
        # getaddrinfo returns a list of tuples; we check every resolved address.
        # This handles both IPv4 and IPv6.
        addr_infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror as exc:
        # Could not resolve the hostname at all.
        raise ValidationError(
            f"Could not resolve hostname '{hostname}': {exc}"
        ) from exc

    for addr_info in addr_infos:
        # addr_info[4] is the sockaddr tuple; [0] is the IP string.
        ip_str = addr_info[4][0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            # Should not happen, but skip unparseable entries.
            continue

        # ipaddress provides these boolean properties on both IPv4Address
        # and IPv6Address:
        #   .is_loopback      → 127.0.0.0/8, ::1
        #   .is_private       → RFC-1918 ranges + ULA IPv6
        #   .is_link_local    → 169.254.0.0/16 (metadata endpoints), fe80::/10
        #   .is_reserved      → IANA reserved blocks
        if ip.is_loopback:
            raise ValidationError(
                f"Access to loopback address '{ip_str}' is not permitted."
            )
        if ip.is_private:
            raise ValidationError(
                f"Access to private network address '{ip_str}' is not permitted."
            )
        if ip.is_link_local:
            raise ValidationError(
                f"Access to link-local address '{ip_str}' (e.g. cloud metadata) "
                "is not permitted."
            )
        if ip.is_reserved:
            raise ValidationError(
                f"Access to reserved address '{ip_str}' is not permitted."
            )

    # ── 5. Return the cleaned URL ─────────────────────────────────────────────
    # We return the original (stripped) URL, not a re-assembled version, to
    # preserve path, query, and fragment exactly as the user typed them.
    return url
