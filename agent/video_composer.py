from __future__ import annotations

import os
import textwrap
from typing import List, Dict, Optional
from .storage import get_storage_adapter

def _format_srt_timestamp(seconds: float) -> str:
    # Format seconds to SRT timestamp hh:mm:ss,ms with proper rounding
    total_ms = int(round(seconds * 1000))
    ms = total_ms % 1000
    total_s = total_ms // 1000
    s = total_s % 60
    total_m = total_s // 60
    m = total_m % 60
    h = total_m // 60
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _format_vtt_timestamp(seconds: float) -> str:
    # Format seconds to VTT timestamp hh:mm:ss.mmm
    total_ms = int(round(seconds * 1000))
    ms = total_ms % 1000
    total_s = total_ms // 1000
    s = total_s % 60
    total_m = total_s // 60
    m = total_m % 60
    h = total_m // 60
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


def _generate_subtitle_entries(slides: List[Dict], wrap_width: int = 80) -> List[Dict]:
    """Generate a list of subtitle entries from slides.

    Each entry is a dict: { 'index': int, 'start': float, 'end': float, 'text': str }
    Per-slide: if `bullets` present, split into per-bullet entries evenly across slide duration.
    Otherwise create a single entry for the whole slide using `speaker_notes`.
    """
    entries: List[Dict] = []
    current_time = 0.0
    idx = 1
    for s in slides:
        duration = float(s.get("estimated_duration_sec", 5))
        bullets = s.get("bullets") or []
        if bullets:
            per = duration / max(1, len(bullets))
            for i, b in enumerate(bullets):
                start = current_time + i * per
                end = current_time + (i + 1) * per
                text = "\n".join(textwrap.wrap(str(b), width=wrap_width))
                entries.append({"index": idx, "start": start, "end": end, "text": text})
                idx += 1
        else:
            start = current_time
            end = current_time + duration
            text_raw = s.get("speaker_notes") or ""
            text = "\n".join(textwrap.wrap(str(text_raw), width=wrap_width))
            entries.append({"index": idx, "start": start, "end": end, "text": text})
            idx += 1
        current_time += duration
    return entries


def _write_subtitles(entries: List[Dict], out_path: str, fmt: str = "srt") -> str:
    """Write entries to SRT or VTT file next to out_path, return file path."""
    if fmt not in ("srt", "vtt"):
        raise ValueError("Unsupported subtitle format: %s" % fmt)
    base = os.path.splitext(out_path)[0]
    if fmt == "srt":
        path = base + ".srt"
        with open(path, "w", encoding="utf-8") as f:
            for e in entries:
                f.write(str(e["index"]) + "\n")
                f.write(f"{_format_srt_timestamp(e['start'])} --> {_format_srt_timestamp(e['end'])}\n")
                f.write(e["text"] + "\n\n")
    else:
        path = base + ".vtt"
        with open(path, "w", encoding="utf-8") as f:
            f.write("WEBVTT\n\n")
            for e in entries:
                f.write(f"{_format_vtt_timestamp(e['start'])} --> {_format_vtt_timestamp(e['end'])}\n")
                f.write(e["text"] + "\n\n")
    return path


class VideoComposer:
    """Simple MoviePy-based composer that stitches slide images and audio into an MP4.

    Each slide displays the provided image for `estimated_duration_sec` and the
    corresponding audio is mixed/concatenated. The composer also writes a simple
    .srt subtitle file with the slide's speaker notes timed to the slide.
    """

    def __init__(self, fps: int = 24):
        self.fps = fps

    def compose_chapter(self, slides: List[Dict], out_path: str, include_subtitles: bool = True) -> str:
        """Compose a chapter video from slides.

        slides: list of { 'image_path'|'image_url', 'audio_path'|'audio_url', 'estimated_duration_sec', 'speaker_notes' }
        out_path: output mp4 path
        include_subtitles: whether to write a .srt file next to the output

        Returns path to generated mp4
        """
        try:
            from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips
        except Exception:
            raise ImportError("moviepy is required for VideoComposer. Install with: pip install moviepy")

        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)

        clips = []
        srt_entries = []
        current_time = 0.0
        audio_segments = []

        for idx, s in enumerate(slides, start=1):
            image_path = s.get("image_path") or s.get("image_url") or s.get("image")
            audio_path = s.get("audio_path") or s.get("audio_url") or s.get("audio")
            duration = float(s.get("estimated_duration_sec", 5))

            # Create an image clip of the given duration
            # If audio file exists, use its duration for the slide duration (prefer audio length)
            if audio_path and os.path.exists(audio_path.replace("file://", "")):
                audio_file = audio_path.replace("file://", "")
                audio_clip = AudioFileClip(audio_file)
                audio_duration = audio_clip.duration
                # prefer audio duration unless estimated is longer
                duration = max(duration, audio_duration)
            clip = ImageClip(image_path).set_duration(duration)
            clips.append(clip)

            # Load audio if exists (we'll concatenate later)
            if audio_path and os.path.exists(audio_path.replace("file://", "")):
                audio_file = audio_path.replace("file://", "")
                audio_segments.append(AudioFileClip(audio_file))

            # subtitle entry
            if include_subtitles:
                start = current_time
                end = current_time + duration
                srt_entries.append({"index": idx, "start": start, "end": end, "text": s.get("speaker_notes", "")})
            current_time += duration

        # Concatenate image clips
        video = concatenate_videoclips(clips, method="compose") if clips else None

        # Concatenate audio segments if present
        final_audio = None
        if audio_segments:
            try:
                from moviepy.editor import concatenate_audioclips

                final_audio = concatenate_audioclips(audio_segments)
            except Exception:
                final_audio = None

        if video and final_audio:
            video = video.set_audio(final_audio)

        # Write video
        if video:
            video.write_videofile(out_path, fps=self.fps, verbose=False, logger=None)

        # Write subtitles
        if include_subtitles and srt_entries:
            _write_subtitles(srt_entries, out_path, fmt="srt")

        return out_path

    def compose_and_upload_chapter_video(self, slides: List[Dict], run_id: str, chapter_id: str, upload_path: Optional[str] = None) -> Dict[str, str]:
        """Compose a chapter video from slides, upload to storage, and return URLs.

        Returns a dict with keys: {'video_url': <str>, 'srt_url': <str>|None}
        """
        storage = get_storage_adapter()
        # create a local staging directory
        out_dir = os.getenv("LLM_OUT_DIR") or "workspace/out"
        os.makedirs(out_dir, exist_ok=True)
        local_video = os.path.join(out_dir, f"{run_id}_{chapter_id}.mp4")

        # Try cache to avoid recomposing videos with same inputs
        try:
            from .cache import FileCache, compute_cache_key
            cache = FileCache()
            # Build a cache key from slide assets and durations
            cache_key_data = [
                {
                    "image": s.get("image_url") or s.get("image_path"),
                    "audio": s.get("audio_url") or s.get("audio_path"),
                    "duration": s.get("estimated_duration_sec"),
                }
                for s in slides
            ]
            cache_key = compute_cache_key(cache_key_data)
            cached = cache.get(cache_key, extension=".mp4")
            if cached:
                local_video = cached
        except Exception:
            cache = None
            cache_key = None
        # ensure local asset paths are present: if slides have file:// URLs, use them; otherwise download
        local_slides = []
        for s in slides:
            s_local = s.copy()
            for key in ("image_url", "audio_url"):
                url = s.get(key)
                if not url:
                    continue
                if url.startswith("file://"):
                    s_local[key.replace("image_url", "image_path").replace("audio_url", "audio_path")] = url[len("file://"):]
                elif storage:
                    # download to local staging
                    local_target = os.path.join(out_dir, os.path.basename(url))
                    try:
                        storage.download_file(url, local_target)
                        s_local[key.replace("image_url", "image_path").replace("audio_url", "audio_path")] = local_target
                    except Exception:
                        # fallback: set to original url (may be a http URL)
                        s_local[key.replace("image_url", "image_path").replace("audio_url", "audio_path")] = url
                else:
                    s_local[key.replace("image_url", "image_path").replace("audio_url", "audio_path")] = url
            local_slides.append(s_local)

        # Compose the video locally if not cached
        if not (cache and cached):
            self.compose_chapter(local_slides, local_video)
            # Store in cache
            if cache and cache_key:
                cache.put(cache_key, local_video, extension=".mp4", metadata={"chapter_id": chapter_id})

        result = {"video_url": local_video, "srt_url": None}
        # Upload to storage if available
        if storage:
            dest_video_path = upload_path or f"videos/{run_id}/{chapter_id}.mp4"
            try:
                video_url = storage.upload_file(local_video, dest_path=dest_video_path)
                result["video_url"] = video_url
                # record in run metadata for discoverability
                try:
                    from .runs import add_run_artifact

                    add_run_artifact(run_id, "video", video_url, metadata={"chapter_id": chapter_id})
                except Exception:
                    pass
            except Exception:
                pass
            # Upload srt if exists
            srt_local = os.path.splitext(local_video)[0] + ".srt"
            if os.path.exists(srt_local):
                dest_srt_path = upload_path.replace('.mp4', '.srt') if upload_path and upload_path.endswith('.mp4') else f"videos/{run_id}/{chapter_id}.srt"
                try:
                    srt_url = storage.upload_file(srt_local, dest_path=dest_srt_path)
                    result["srt_url"] = srt_url
                    try:
                        from .runs import add_run_artifact

                        add_run_artifact(run_id, "subtitle", srt_url, metadata={"chapter_id": chapter_id})
                    except Exception:
                        pass
                except Exception:
                    result["srt_url"] = srt_local

        return result

    def merge_videos(self, video_urls: List[str], out_path: str, transition_sec: float = 0.0) -> str:
        """Merge multiple videos into a single output video.

        video_urls: list of file:// or remote URLs
        out_path: local destination path for merged video
        transition_sec: crossfade duration in seconds between clips
        Returns local path or uploaded URL (if storage adapter used by caller)
        """
        try:
            from moviepy.editor import VideoFileClip, concatenate_videoclips
        except Exception:
            raise ImportError("moviepy is required for merging videos. Install with: pip install moviepy")

        storage = get_storage_adapter()
        local_files = []
        for url in video_urls:
            if url.startswith("file://"):
                local_files.append(url[len("file://"):])
            elif storage:
                # download to staging
                out_dir = os.path.dirname(out_path) or "."
                os.makedirs(out_dir, exist_ok=True)
                local_target = os.path.join(out_dir, os.path.basename(url))
                try:
                    storage.download_file(url, local_target)
                    local_files.append(local_target)
                except Exception:
                    # fallback to the original URL (may be remote) — VideoFileClip may handle HTTP
                    local_files.append(url)
            else:
                local_files.append(url)

        clips = []
        for f in local_files:
            clips.append(VideoFileClip(f))

        # Apply crossfade if requested
        processed = []
        for i, c in enumerate(clips):
            if i > 0 and transition_sec > 0:
                # crossfade-in the current clip
                c = c.crossfadein(transition_sec)
            processed.append(c)

        final = concatenate_videoclips(processed, method="compose") if processed else None
        if final:
            final.write_videofile(out_path, fps=self.fps, verbose=False, logger=None)
            # Close clips
            final.close()
            for c in clips:
                try:
                    c.close()
                except Exception:
                    pass
        return out_path
