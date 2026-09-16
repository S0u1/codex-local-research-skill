#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Public-share-page approach: Copyright 2025 yzfly, douyin-mcp-server.
# Adapted from douyin-favorites-sync by local-research contributors, 2026-09-16.
# Changes: portable WhisperX command, explicit output, strict identity checks,
# resumable downloads/transcripts, atomic state, source-limit stop handling.
"""Download verified Douyin video URLs from an Agent-collected manifest.

Does not log into Douyin or enumerate favorites. No cloud transcription or keys.
See references/collectors.md and licenses/Apache-2.0.txt.
"""
from __future__ import annotations
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def validate_source_url(url: str) -> None:
    parsed = urllib.parse.urlsplit(url)
    host = parsed.hostname or ""
    if (parsed.scheme != "https" or parsed.username or parsed.password
            or parsed.port not in (None, 443)
            or not any(host == d or host.endswith("." + d) for d in ("douyin.com", "iesdouyin.com"))):
        raise ValueError("Source must be a Douyin HTTPS URL")


class SourceRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_source_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
    )
}
MOBILE_API_HEADERS = {
    "User-Agent": (
        "com.ss.android.ugc.aweme/110101 (Linux; U; Android 10; zh_CN; "
        "Pixel 4; Build/QQ3A.200805.001; Cronet/58.0.2991.0)"
    )
}
MOBILE_API_URL = "https://aweme.snssdk.com/aweme/v1/feed/"
def request(url: str, headers: dict[str, str] | None = None) -> urllib.response.addinfourl:
    return urllib.request.urlopen(urllib.request.Request(url, headers=headers or HEADERS), timeout=45)


def video_id_from_url(url: str) -> str:
    match = re.search(r"/(?:video|note)/(\d+)", url)
    if not match:
        raise ValueError(f"Cannot find a video ID in {url}")
    return match.group(1)


def video_urls_from_item(item: dict[str, Any]) -> list[str]:
    video = item.get("video") if isinstance(item.get("video"), dict) else {}
    bit_rates = video.get("bit_rate") if isinstance(video.get("bit_rate"), list) else []
    ranked = sorted(
        (entry for entry in bit_rates if isinstance(entry, dict)),
        key=lambda entry: float(entry.get("bit_rate") or entry.get("data_size") or 0),
        reverse=True,
    )
    candidates: list[str] = []
    for entry in ranked:
        play_addr = entry.get("play_addr") if isinstance(entry.get("play_addr"), dict) else {}
        candidates.extend(str(url) for url in play_addr.get("url_list", []) if str(url).startswith("http"))
    play_addr = video.get("play_addr") if isinstance(video.get("play_addr"), dict) else {}
    candidates.extend(str(url) for url in play_addr.get("url_list", []) if str(url).startswith("http"))
    return list(dict.fromkeys(candidates))


def parse_mobile_feed_payload(payload: dict[str, Any], video_id: str) -> dict[str, Any]:
    items = payload.get("aweme_list") if isinstance(payload.get("aweme_list"), list) else []
    item = next(
        (candidate for candidate in items if isinstance(candidate, dict) and str(candidate.get("aweme_id")) == video_id),
        None,
    )
    if item is None:
        returned_ids = [str(candidate.get("aweme_id")) for candidate in items[:5] if isinstance(candidate, dict)]
        raise ValueError(f"Mobile API returned no exact match for {video_id}; returned IDs: {returned_ids}")
    if item.get("images"):
        raise ValueError(f"Douyin item {video_id} is an image post, not a video")
    urls = video_urls_from_item(item)
    if not urls:
        raise ValueError(f"Mobile API returned no playable video URL for {video_id}")
    return {
        "video_id": video_id,
        "title": str(item.get("desc") or "").strip(),
        "download_url": urls[0],
        "public_url": f"https://www.douyin.com/video/{video_id}",
        "resolver": "mobile_feed",
    }


def parse_mobile_video(video_id: str) -> dict[str, Any]:
    query = urllib.parse.urlencode({"aweme_id": video_id})
    with request(f"{MOBILE_API_URL}?{query}", MOBILE_API_HEADERS) as response:
        payload = json.loads(response.read().decode("utf-8", errors="replace"))
    if not isinstance(payload, dict):
        raise ValueError("Mobile API returned a non-object JSON payload")
    return parse_mobile_feed_payload(payload, video_id)


def parse_legacy_share_page(video_id: str) -> dict[str, Any]:
    page_url = f"https://www.iesdouyin.com/share/video/{video_id}"
    with request(page_url) as response:
        html = response.read().decode("utf-8", errors="replace")

    match = re.search(r"window\._ROUTER_DATA\s*=\s*(.*?)</script", html, re.DOTALL)
    if not match:
        raise ValueError("Could not find public video data in the Douyin page")
    raw = match.group(1).strip().rstrip(";")
    router_data = json.loads(raw)
    loader = router_data.get("loaderData", {})
    entry = loader.get("video_(id)/page") or loader.get("note_(id)/page")
    if not entry:
        raise ValueError("The public page does not contain a supported video entry")
    items = entry.get("videoInfoRes", {}).get("item_list", [])
    if not items:
        raise ValueError("The public page returned no downloadable video item")

    item = items[0]
    resolved_id = str(item.get("aweme_id") or "")
    if resolved_id != video_id:
        raise ValueError(f"Legacy page returned video {resolved_id}, expected {video_id}")
    urls = item.get("video", {}).get("play_addr", {}).get("url_list", [])
    if not urls:
        raise ValueError("The public page has no playable video URL")
    return {
        "video_id": video_id,
        "title": (item.get("desc") or "").strip(),
        "download_url": urls[0].replace("playwm", "play"),
        "public_url": f"https://www.douyin.com/video/{video_id}",
        "resolver": "legacy_share_page",
    }


def parse_video_page(source_url: str) -> dict[str, Any]:
    validate_source_url(source_url)
    try:
        video_id = video_id_from_url(source_url)
    except ValueError:
        opener = urllib.request.build_opener(SourceRedirectHandler())
        with opener.open(urllib.request.Request(source_url, headers=HEADERS), timeout=45) as response:
            validate_source_url(response.geturl())
            video_id = video_id_from_url(response.geturl())

    try:
        return parse_mobile_video(video_id)
    except urllib.error.HTTPError as exc:
        if exc.code in {401, 403, 429}:
            raise
        return parse_legacy_share_page(video_id)
    except Exception as mobile_error:
        try:
            return parse_legacy_share_page(video_id)
        except urllib.error.HTTPError:
            raise
        except Exception as legacy_error:
            raise RuntimeError(
                f"Douyin resolution failed for {video_id}; mobile feed: {mobile_error}; legacy share page: {legacy_error}"
            ) from legacy_error


def is_mp4_header(data: bytes) -> bool:
    return len(data) >= 12 and data[4:8] in (b"ftyp", b"styp")


def media_file_valid(path: Path) -> bool:
    if not path.is_file():
        return False
    with path.open("rb") as stream:
        return is_mp4_header(stream.read(32))


def download(url: str, destination: Path) -> None:
    temp = None
    try:
        with request(url) as response:
            first = response.read(1024 * 1024)
            if not first:
                raise ValueError("Downloaded media is empty")
            content_type = getattr(response, "headers", {}).get("Content-Type", "").lower()
            if "html" in content_type or "json" in content_type or not is_mp4_header(first):
                raise ValueError("Response is not MP4 media; possible verification/error page")
            with tempfile.NamedTemporaryFile(mode="wb", prefix=".media-", suffix=".part",
                                             dir=destination.parent, delete=False) as output:
                temp = Path(output.name)
                output.write(first)
                while chunk := response.read(1024 * 1024):
                    output.write(chunk)
        temp.replace(destination)
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)


def srt_segment_texts(srt_text: str) -> list[str]:
    """Extract per-segment text lines from an SRT document, in order."""
    texts: list[str] = []
    for block in re.split(r"\n\s*\n", srt_text.strip()):
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if len(lines) >= 2 and "-->" in lines[1]:
            texts.append(" ".join(lines[2:]))
        elif lines and "-->" in lines[0]:
            texts.append(" ".join(lines[1:]))
    return [text for text in texts if text]


def atomic_json(path: Path, value: Any) -> None:
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                     prefix=".write-", delete=False) as stream:
        temp = Path(stream.name)
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    try:
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


def has_content(path: Path) -> bool:
    return path.is_file() and path.stat().st_size > 0


def transcribe_local(video: Path, item_dir: Path, executable: str, model: str, language: str) -> Path:
    if not shutil.which(executable):
        raise RuntimeError("WhisperX executable not found; install local ASR or set --whisperx-command")
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg is required for local transcription")
    # Only a temporary output directory is handed to WhisperX; no stale SRT can pass.
    with tempfile.TemporaryDirectory(prefix=".asr-", dir=item_dir) as temporary:
        command = [executable, str(video), "--model", model, "--language", language,
                   "--device", "cpu", "--compute_type", "int8", "--vad_method", "silero",
                   "--no_align", "--output_dir", temporary, "--output_format", "srt", "--threads", "4"]
        try:
            subprocess.run(command, check=True, capture_output=True, text=True, timeout=3600)
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(f"WhisperX failed (exit {exc.returncode}); check the installation/model") from exc
        raw = Path(temporary) / (video.stem + ".srt")
        if not has_content(raw):
            raise RuntimeError("WhisperX produced no SRT")
        text = raw.read_text(encoding="utf-8")
        segments = srt_segment_texts(text)
        if not segments:
            raise RuntimeError("WhisperX SRT contains no speech segments")
        (item_dir / "transcript.srt").write_text(text, encoding="utf-8")
        transcript = item_dir / "transcript.txt"
        transcript.write_text("\n".join(segments) + "\n", encoding="utf-8")
        return transcript


def run(items: list[dict], output: Path, transcriber: str = "none",
        whisperx_command: str = "whisperx", model: str = "small", language: str = "zh") -> dict:
    output = output.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    # Atomic exclusive lock works on Windows/macOS/Linux. After a crash, verify the
    # recorded process is gone before manually removing this lock; never guess.
    lock = output / ".download.lock"
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise RuntimeError("Output is locked; check the running process before removing .download.lock") from exc
    with os.fdopen(descriptor, "w") as stream:
        stream.write(str(os.getpid()))
    try:
        return run_locked(items, output, transcriber, whisperx_command, model, language)
    finally:
        lock.unlink(missing_ok=True)


def run_locked(items, output, transcriber, whisperx_command, model, language):
    state_path = output / ".download-state.json"
    state = json.loads(state_path.read_text()) if state_path.exists() else {"version": 1, "items": {}}
    if state.get("version") != 1 or not isinstance(state.get("items"), dict):
        raise ValueError("Unsupported download state; preserve it for recovery")
    result = {"downloaded": [], "transcribed": [], "reused": [], "failed": [], "pending": []}
    seen = set()
    for index, item in enumerate(items):
        video_id = str(item.get("video_id", "")) if isinstance(item, dict) else ""
        try:
            if not re.fullmatch(r"[0-9]{1,30}", video_id):
                raise ValueError("Manifest video_id must contain digits only")
            source_url = str(item.get("url", ""))
            validate_source_url(source_url)
            if "/note/" in urllib.parse.urlsplit(source_url).path:
                raise ValueError("Image posts must be read in the browser, not downloaded as video")
            try:
                url_id = video_id_from_url(source_url)
            except ValueError:
                url_id = None  # a supported short URL must resolve before any file is used
            if url_id and url_id != video_id:
                raise ValueError("Manifest ID and URL do not match")
            if video_id in seen:
                continue
            seen.add(video_id)
            folder = output / video_id
            if folder.resolve().parent != output or folder.is_symlink():
                raise ValueError("Output item must remain inside the selected directory")
            video = folder / "video.mp4"
            metadata = folder / "metadata.json"
            for name in ("video.mp4", "metadata.json", "transcript.txt", "transcript.srt"):
                if (folder / name).is_symlink():
                    raise ValueError("Output files cannot be symbolic links")
            # Old metadata is identity evidence, not permission to skip missing files.
            cached = json.loads(metadata.read_text()) if metadata.exists() else {}
            verified = (cached.get("video_id") == video_id and cached.get("source_url") == source_url)
            if not verified and any((folder / name).exists() for name in ("video.mp4", "transcript.txt", "transcript.srt")):
                raise ValueError("Cached media identity is missing or conflicts; preserve files and resolve before reuse")
            if not verified:
                parsed = parse_video_page(source_url)
                if str(parsed.get("video_id")) != video_id:
                    raise ValueError("Resolved ID does not match manifest")
            else:
                parsed = None
            folder.mkdir(parents=True, exist_ok=True)
            if has_content(video) and not media_file_valid(video):
                raise ValueError("Cached media is not MP4; preserve it for inspection before retry")
            if not has_content(video):
                parsed = parsed or parse_video_page(source_url)
                if str(parsed.get("video_id")) != video_id:
                    raise ValueError("Resolved ID does not match manifest")
                download(parsed["download_url"], video)
                if not media_file_valid(video):
                    raise ValueError("No valid MP4 media was downloaded")
                result["downloaded"].append(video_id)
            else:
                result["reused"].append(video_id)
            atomic_json(metadata, {"video_id": video_id, "source_url": source_url,
                        "title": (parsed or cached).get("title", item.get("title", "")),
                        "collected_from_browser": item, "observed_at": datetime.now(timezone.utc).isoformat()})
            transcript = folder / "transcript.txt"
            if transcriber == "local" and not (has_content(transcript) and has_content(folder / "transcript.srt")):
                transcribe_local(video, folder, whisperx_command, model, language)
                result["transcribed"].append(video_id)
            state["items"][video_id] = {"status": "transcribed" if transcriber == "local" else "downloaded",
                                       "directory": str(folder), "source_url": source_url}
        except Exception as exc:
            # Never dump response bodies or URLs containing authentication data.
            error = f"HTTP {exc.code}" if isinstance(exc, urllib.error.HTTPError) else str(exc)
            result["failed"].append({"video_id": video_id, "error": error})
            if re.fullmatch(r"[0-9]{1,30}", video_id):
                state["items"][video_id] = {"status": "failed", "error": error}
            if isinstance(exc, urllib.error.HTTPError) and exc.code in {401, 403, 429}:
                result["blocked"] = {"reason": error, "retry_after": exc.headers.get("Retry-After") if exc.headers else None}
                result["pending"] = [str(row.get("video_id", "")) for row in items[index + 1:] if isinstance(row, dict)]
                break
        finally:
            atomic_json(state_path, state)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--items-file", required=True, type=Path, help="JSON with items: [{video_id, url, title?}]")
    parser.add_argument("--output", required=True, type=Path, help="Account-specific staging directory; no global default")
    parser.add_argument("--transcriber", choices=["none", "local"], default="none")
    parser.add_argument("--whisperx-command", default="whisperx", help="Executable path, not a shell command")
    parser.add_argument("--whisperx-model", default="small")
    parser.add_argument("--whisperx-language", default="zh")
    args = parser.parse_args()
    try:
        manifest = json.loads(args.items_file.read_text(encoding="utf-8"))
        if not isinstance(manifest, dict) or not isinstance(manifest.get("items"), list):
            raise ValueError("Manifest must contain an items array")
        result = run(manifest["items"], args.output, args.transcriber,
                     args.whisperx_command, args.whisperx_model, args.whisperx_language)
    except Exception as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
