import base64
import io
import logging

import httpx
from PIL import Image

logger = logging.getLogger(__name__)

# WhatsApp caps embedded CheckboxGroup option images at 100KB (Flow JSON
# v5.0+) and explicitly recommends staying well under that for performance
# -- this targets roughly 20KB so a whole category's worth of images stays
# small and fast to render, with real margin under the hard cap.
_TARGET_BYTES = 20_000
_INITIAL_MAX_DIMENSION = 300
_FALLBACK_MAX_DIMENSION = 150
_QUALITY_STEPS = (80, 65, 50, 35, 20)


async def fetch_and_compress_image(url: str) -> str | None:
    """Fetches a menu item's photo (image_url) and re-encodes it as a small
    JPEG, base64-encoded, ready to embed directly as a WhatsApp Flow
    CheckboxGroup option's `image` field. Best-effort: returns None on any
    failure (unreachable URL, corrupt/unsupported image, whatever) rather
    than raising -- a missing photo shouldn't block an item from being
    orderable. Callers cache the result (catalog/domain/models.py's
    MenuItem.flow_image_base64) rather than calling this on every Flow
    screen load, since it's a real network fetch plus CPU-bound resize."""
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()
        return _compress(response.content)
    except Exception as exc:
        logger.warning("Failed to fetch/compress image %s: %s", url, exc)
        return None


def _compress(raw_bytes: bytes) -> str | None:
    try:
        image: Image.Image = Image.open(io.BytesIO(raw_bytes)).convert("RGB")
        image.thumbnail((_INITIAL_MAX_DIMENSION, _INITIAL_MAX_DIMENSION))

        for quality in _QUALITY_STEPS:
            data = _encode_jpeg(image, quality)
            if len(data) <= _TARGET_BYTES:
                return base64.b64encode(data).decode("utf-8")

        # Still over budget even at the lowest quality step -- shrink
        # further and accept whatever the lowest quality gives at that size
        # rather than looping indefinitely chasing an exact target.
        image.thumbnail((_FALLBACK_MAX_DIMENSION, _FALLBACK_MAX_DIMENSION))
        return base64.b64encode(_encode_jpeg(image, _QUALITY_STEPS[-1])).decode("utf-8")
    except Exception as exc:
        logger.warning("Failed to compress image: %s", exc)
        return None


def _encode_jpeg(image: Image.Image, quality: int) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=quality, optimize=True)
    return buffer.getvalue()
