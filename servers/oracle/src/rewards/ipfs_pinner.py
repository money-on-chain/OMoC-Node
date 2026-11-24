"""Optional IPFS gateway fetcher (for fast sync) and Kubo local pinner (post-publish).

Completely decoupled from consensus/signing: IPFS outages never block signing or publishing.
"""

import logging
from typing import Optional, Sequence

import aiohttp

from oracle.src.rewards.cid import compute_cid_v1

logger = logging.getLogger(__name__)


async def fetch_from_ipfs_gateways(
    cid: str,
    gateways: Sequence[str],
    timeout_secs: float = 30.0,
) -> Optional[bytes]:
    """Download raw bytes for `cid` from configured gateways, verifying CIDv1 locally."""
    if not cid or not gateways:
        return None
    for gateway in gateways:
        base = gateway.rstrip("/")
        url = f"{base}/{cid}"
        try:
            timeout = aiohttp.ClientTimeout(total=timeout_secs)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        logger.warning("IPFS gateway %s returned HTTP %s", url, resp.status)
                        continue
                    raw_bytes = await resp.read()
            computed = compute_cid_v1(raw_bytes)
            if computed != cid:
                logger.warning(
                    "IPFS gateway %s returned CID mismatch (%s != %s)", url, computed, cid
                )
                continue
            return raw_bytes
        except Exception as err:
            logger.warning("IPFS gateway %s failed: %r", url, err)
    return None


class IpfsPinner:
    """Uploads and pins canonical epoch JSON bytes to a private local Kubo API."""

    def __init__(self, api_url: str, timeout_secs: float = 60.0):
        self.api_url = api_url.rstrip("/") if api_url else ""
        self.timeout_secs = timeout_secs

    @property
    def enabled(self) -> bool:
        return bool(self.api_url)

    async def pin_bytes(self, raw_bytes: bytes, expected_cid: str, filename: str) -> str:
        """Upload `raw_bytes` to Kubo and assert the returned Hash equals `expected_cid`."""
        if not self.enabled:
            raise RuntimeError("IPFS pinner is not configured")

        endpoint = (
            f"{self.api_url}/api/v0/add"
            "?cid-version=1&raw-leaves=true&chunker=size-262144&pin=true"
        )
        form = aiohttp.FormData()
        form.add_field(
            "file",
            raw_bytes,
            filename=filename,
            content_type="application/json",
        )
        timeout = aiohttp.ClientTimeout(total=self.timeout_secs)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(endpoint, data=form) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise RuntimeError(f"Kubo add failed (HTTP {resp.status}): {text[:200]}")
                body = await resp.json()

        returned_cid = body.get("Hash") if isinstance(body, dict) else None
        if returned_cid != expected_cid:
            raise RuntimeError(
                f"Kubo returned CID {returned_cid!r}, expected {expected_cid!r}"
            )
        return returned_cid
