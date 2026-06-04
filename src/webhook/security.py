"""
Webhook signature verification using HMAC-SHA256.

GitHub signs every webhook delivery with a secret. This module verifies
that signature to ensure payloads are authentic and haven't been tampered with.
"""

from __future__ import annotations

import hashlib
import hmac
import logging

from fastapi import HTTPException, Request

logger = logging.getLogger(__name__)


async def verify_webhook_signature(
    request: Request,
    webhook_secret: str,
) -> bytes:
    """
    Verify the GitHub webhook signature and return the raw request body.

    GitHub sends an X-Hub-Signature-256 header with every webhook delivery.
    This header contains an HMAC-SHA256 digest of the payload body, computed
    using the webhook secret as the key.

    Args:
        request: The incoming FastAPI request.
        webhook_secret: The secret configured in GitHub webhook settings.

    Returns:
        The raw request body bytes (for downstream JSON parsing).

    Raises:
        HTTPException: 403 if signature is missing or invalid.
    """
    # If no webhook secret is configured, skip verification (dev mode)
    if not webhook_secret:
        logger.warning("⚠ Webhook secret not configured — skipping signature verification")
        return await request.body()

    # Get the signature header
    signature_header = request.headers.get("X-Hub-Signature-256")
    if not signature_header:
        logger.error("❌ Missing X-Hub-Signature-256 header")
        raise HTTPException(
            status_code=403,
            detail="Missing X-Hub-Signature-256 header",
        )

    # Read the raw body
    body = await request.body()

    # Compute expected signature
    expected_signature = (
        "sha256="
        + hmac.new(
            webhook_secret.encode("utf-8"),
            body,
            hashlib.sha256,
        ).hexdigest()
    )

    # Timing-safe comparison
    if not hmac.compare_digest(signature_header, expected_signature):
        logger.error("❌ Webhook signature verification failed")
        raise HTTPException(
            status_code=403,
            detail="Invalid webhook signature",
        )

    logger.debug("✅ Webhook signature verified")
    return body
