import base64
import io

from PIL import Image

from flows.domain import images as images_module
from flows.domain.images import _compress, fetch_and_compress_image


def _generate_png_bytes(*, size: tuple[int, int] = (800, 800)) -> bytes:
    """A synthetic image, not a network fetch -- compression logic is what
    this module tests, not connectivity."""
    image = Image.new("RGB", size, color=(200, 120, 60))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_compress_produces_small_base64_jpeg_under_target() -> None:
    raw = _generate_png_bytes()

    result = _compress(raw)

    assert result is not None
    decoded = base64.b64decode(result)
    assert len(decoded) <= images_module._TARGET_BYTES
    # Round-trips as a real JPEG, not just small bytes.
    Image.open(io.BytesIO(decoded)).verify()


def test_compress_downscales_large_images() -> None:
    raw = _generate_png_bytes(size=(2000, 2000))

    result = _compress(raw)

    assert result is not None
    decoded_image = Image.open(io.BytesIO(base64.b64decode(result)))
    assert max(decoded_image.size) <= images_module._INITIAL_MAX_DIMENSION


def test_compress_returns_none_for_garbage_bytes() -> None:
    assert _compress(b"not an image") is None


async def test_fetch_and_compress_image_returns_none_on_http_error(monkeypatch) -> None:
    class _FailingClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc_info):
            return False

        async def get(self, url):
            raise Exception("network is down")

    monkeypatch.setattr(images_module.httpx, "AsyncClient", lambda **kwargs: _FailingClient())

    result = await fetch_and_compress_image("https://example.com/nonexistent.jpg")

    assert result is None


async def test_fetch_and_compress_image_returns_base64_on_success(monkeypatch) -> None:
    raw = _generate_png_bytes()

    class _FakeResponse:
        content = raw

        def raise_for_status(self) -> None:
            pass

    class _FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc_info):
            return False

        async def get(self, url):
            return _FakeResponse()

    monkeypatch.setattr(images_module.httpx, "AsyncClient", lambda **kwargs: _FakeClient())

    result = await fetch_and_compress_image("https://example.com/photo.jpg")

    assert result is not None
    Image.open(io.BytesIO(base64.b64decode(result))).verify()
