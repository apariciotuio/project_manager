"""HMAC-SHA256 signature verification for Puppet callback requests.

Puppet signs the raw request body with a shared secret (PUPPET_CALLBACK_SECRET)
and sends the hex digest in the X-Puppet-Signature header.

Security notes:
  - Uses hmac.compare_digest for constant-time comparison.
  - Never raises — all failure modes return False so callers can return 401.
"""

from __future__ import annotations

import hashlib
import hmac
import logging

logger = logging.getLogger(__name__)


def verify_puppet_signature(raw_body: bytes, header_signature: str, secret: str) -> bool:
    """Verify that header_signature is HMAC-SHA256(raw_body, secret).

    Args:
        raw_body: The raw request body bytes.
        header_signature: Hex digest from X-Puppet-Signature header.
        secret: Shared secret from PUPPET_CALLBACK_SECRET env var.

    Returns:
        True if the signature is valid, False otherwise.
        Never raises.
    """
    if not header_signature:
        return False

    try:
        expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected.lower(), header_signature.lower())
    except Exception:
        logger.warning(
            "verify_puppet_signature: unexpected error during verification", exc_info=True
        )
        return False
