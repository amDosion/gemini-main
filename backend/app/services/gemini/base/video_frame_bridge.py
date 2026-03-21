"""
Frame-extraction helpers for long-video chaining.

This module converts the last frame of an input video into a source image so
provider-mode video generation can keep continuity even when direct video
extension is unavailable on the selected platform/model combination.
"""

from __future__ import annotations

import io
import logging
from pathlib import Path
from typing import Optional

from PIL import Image

from .video_common import LoadedReferenceImage, LoadedSourceVideo, save_bytes_to_temp_file, suffix_for_mime_type

logger = logging.getLogger(__name__)

try:
    import imageio.v2 as imageio

    IMAGEIO_AVAILABLE = True
except ImportError:
    imageio = None
    IMAGEIO_AVAILABLE = False


def extract_last_frame_image(source_video: LoadedSourceVideo) -> LoadedReferenceImage:
    """
    Decode the final frame from a video payload and encode it as PNG bytes.

    The Google SDK accepts an input `image` for image-to-video generation.
    Using the last frame of the previous segment as the next segment's source
    image provides a stable fallback when direct video extension is unsupported
    or unavailable.
    """

    if not IMAGEIO_AVAILABLE:
        raise RuntimeError(
            "imageio and imageio-ffmpeg are required for Google video last-frame chaining."
        )

    temp_path = save_bytes_to_temp_file(
        source_video.video_bytes,
        suffix_for_mime_type(source_video.mime_type) or ".mp4",
    )
    reader = None
    try:
        reader = imageio.get_reader(str(temp_path))
        frame = None
        for frame_candidate in reader:
            frame = frame_candidate
        if frame is None:
            raise RuntimeError("Unable to decode any frame from the source video.")

        image = Image.fromarray(frame)
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return LoadedReferenceImage(
            image_bytes=buffer.getvalue(),
            mime_type="image/png",
        )
    except Exception as exc:
        raise RuntimeError(f"Failed to extract the last frame from the source video: {exc}") from exc
    finally:
        if reader is not None:
            try:
                reader.close()
            except Exception:
                logger.debug("Failed to close imageio reader for source video frame extraction", exc_info=True)
        try:
            Path(temp_path).unlink(missing_ok=True)
        except Exception:
            logger.debug("Failed to remove temporary source-video file %s", temp_path, exc_info=True)
