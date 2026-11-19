"""
backend/posters.py - Validate uploaded poster images.

The file's real format is detected from its bytes; the client-supplied filename
and content type are ignored, so a crafted name (e.g. "../../x") can't affect
where anything is stored.
"""
import hashlib
from dataclasses import dataclass
from io import BytesIO

from PIL import Image, UnidentifiedImageError

MAX_POSTER_BYTES = 10 * 1024 * 1024  # matches the storage bucket's file_size_limit

# Pillow format name -> (file extension, MIME type)
ALLOWED_FORMATS = {
    "JPEG": ("jpg", "image/jpeg"),
    "PNG": ("png", "image/png"),
    "WEBP": ("webp", "image/webp"),
}


class InvalidPoster(ValueError):
    """The upload isn't an acceptable poster image."""


@dataclass(frozen=True)
class PosterInfo:
    sha256: str
    ext: str
    content_type: str

    @property
    def storage_path(self) -> str:
        # Content-addressed: the same image always maps to the same object.
        return f"{self.sha256}.{self.ext}"


def inspect_poster(data: bytes) -> PosterInfo:
    if not data:
        raise InvalidPoster("The poster file is empty.")
    if len(data) > MAX_POSTER_BYTES:
        raise InvalidPoster("The poster is larger than 10 MB.")
    try:
        with Image.open(BytesIO(data)) as img:
            fmt = img.format
            img.verify()
    except (UnidentifiedImageError, OSError, SyntaxError) as exc:
        raise InvalidPoster("The file isn't a readable image.") from exc
    if fmt not in ALLOWED_FORMATS:
        raise InvalidPoster("Posters must be JPG, PNG or WEBP.")
    ext, content_type = ALLOWED_FORMATS[fmt]
    return PosterInfo(hashlib.sha256(data).hexdigest(), ext, content_type)
