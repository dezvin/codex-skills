#!/usr/bin/env python3
"""Retrieve exact public Telegram posts and download attached images."""

from __future__ import annotations

import argparse
import html as html_module
import json
import re
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urljoin, urlsplit
from urllib.request import Request, urlopen

try:
    from bs4 import BeautifulSoup
except ImportError:  # Cleanup must remain available even if the dependency is missing.
    BeautifulSoup = None


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)
ALLOWED_POST_HOSTS = {"t.me", "www.t.me", "telegram.me", "www.telegram.me"}
USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{4,32}$")
MESSAGE_ID_RE = re.compile(r"^[0-9]+$")
BACKGROUND_URL_RE = re.compile(r"url\(\s*(['\"]?)(.*?)\1\s*\)", re.IGNORECASE)

HTML_TIMEOUT_SECONDS = 20
IMAGE_TIMEOUT_SECONDS = 20
MAX_HTML_BYTES = 2 * 1024 * 1024
MAX_IMAGE_BYTES = 20 * 1024 * 1024
MAX_BATCH_IMAGE_BYTES = 100 * 1024 * 1024

TEMP_PREFIX = "telegram-post-reader-"
MARKER_NAME = ".telegram-post-reader"
MARKER_CONTENT = "telegram-post-reader-v1\n"

IMAGE_TYPES = {
    "image/jpeg": (".jpg", (b"\xff\xd8\xff",)),
    "image/png": (".png", (b"\x89PNG\r\n\x1a\n",)),
    "image/webp": (".webp", (b"RIFF",)),
    "image/gif": (".gif", (b"GIF87a", b"GIF89a")),
}


class ItemFailure(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class Target:
    source_url: str
    username: str
    message_id: int
    retrieval_url: str


class ArtifactStore:
    def __init__(self) -> None:
        self.directory: Path | None = None
        self.total_bytes = 0

    def ensure(self) -> Path:
        if self.directory is None:
            path = Path(tempfile.mkdtemp(prefix=TEMP_PREFIX)).resolve()
            (path / MARKER_NAME).write_text(MARKER_CONTENT, encoding="utf-8")
            self.directory = path
        return self.directory

    def discard(self) -> None:
        if self.directory is not None:
            shutil.rmtree(self.directory, ignore_errors=True)
            self.directory = None


def write_json_stdout(value: dict) -> None:
    """Write JSON as UTF-8 bytes, independent of the Windows console code page."""
    payload = (json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
    binary_stdout = getattr(sys.stdout, "buffer", None)
    if binary_stdout is not None:
        binary_stdout.write(payload)
        binary_stdout.flush()
        return
    sys.stdout.write(payload.decode("utf-8"))
    sys.stdout.flush()


def compact_text(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.replace("\r\n", "\n").replace("\r", "\n").replace("\xa0", " ")
    value = re.sub(r"[ \t]+\n", "\n", value)
    value = re.sub(r"\n[ \t]+", "\n", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    value = value.strip()
    return value or None


def inline_text(node) -> str | None:
    if node is None:
        return None
    value = re.sub(r"\s+", " ", node.get_text(" ", strip=True)).strip()
    return value or None


def normalize_candidate(raw: str) -> Target:
    source_url = raw.strip()
    if not source_url:
        raise ItemFailure("unsupported_url", "Empty URL is not supported.")

    candidate = source_url
    if "://" not in candidate:
        if not re.match(r"^(?:www\.)?(?:t\.me|telegram\.me)/", candidate, re.IGNORECASE):
            raise ItemFailure("unsupported_url", "Expected a direct t.me or telegram.me post URL.")
        candidate = f"https://{candidate}"

    try:
        parsed = urlsplit(candidate)
        host = (parsed.hostname or "").lower()
        port = parsed.port
    except ValueError as exc:
        raise ItemFailure("unsupported_url", f"Malformed Telegram URL: {exc}") from exc

    if parsed.scheme.lower() not in {"http", "https"} or host not in ALLOWED_POST_HOSTS:
        raise ItemFailure("unsupported_url", "Expected an http(s) t.me or telegram.me URL.")
    if parsed.username or parsed.password or port not in {None, 80, 443}:
        raise ItemFailure("unsupported_url", "Credentials and custom ports are not supported.")
    if parsed.fragment:
        raise ItemFailure("unsupported_url", "URL fragments are not supported.")

    query = parse_qsl(parsed.query, keep_blank_values=True)
    if len(query) > 1 or any(key.lower() != "single" or value not in {"", "1"} for key, value in query):
        raise ItemFailure("unsupported_query", "Only an optional ?single or ?single=1 query is supported.")

    segments = [segment for segment in parsed.path.split("/") if segment]
    if segments and (segments[0].lower() == "joinchat" or segments[0].startswith("+")):
        raise ItemFailure("invite_url", "Telegram invite links are not supported.")
    if segments and segments[0].lower() == "c":
        raise ItemFailure("private_url", "Private /c/ links are not supported.")

    if segments and segments[0].lower() == "s":
        if len(segments) == 2:
            raise ItemFailure("missing_message_id", "An /s/ history URL needs a numeric post ID.")
        if len(segments) != 3:
            raise ItemFailure("unsupported_url", "Expected /s/<username>/<numeric_message_id>.")
        username, message_text = segments[1], segments[2]
    else:
        if len(segments) == 1:
            raise ItemFailure("missing_message_id", "A direct post URL needs a numeric message ID.")
        if len(segments) != 2:
            raise ItemFailure("unsupported_url", "Expected /<username>/<numeric_message_id>.")
        username, message_text = segments

    if not USERNAME_RE.fullmatch(username):
        raise ItemFailure("unsupported_url", "The public Telegram username has an unsupported form.")
    if not MESSAGE_ID_RE.fullmatch(message_text) or int(message_text) <= 0:
        raise ItemFailure("unsupported_url", "The Telegram message ID must be a positive integer.")

    username = username.lower()
    message_id = int(message_text)
    retrieval_url = f"https://t.me/{username}/{message_id}?embed=1&single"
    return Target(source_url, username, message_id, retrieval_url)


def read_limited(response, limit: int) -> bytes:
    chunks: list[bytes] = []
    size = 0
    while True:
        chunk = response.read(min(65536, limit + 1 - size))
        if not chunk:
            return b"".join(chunks)
        chunks.append(chunk)
        size += len(chunk)
        if size > limit:
            raise ItemFailure("response_too_large", f"Response exceeded the {limit}-byte safety limit.")


def http_failure(exc: HTTPError, unavailable: bool = False) -> ItemFailure:
    if exc.code == 429:
        return ItemFailure("rate_limited", "Telegram rate-limited the request.")
    if unavailable or exc.code in {404, 410}:
        return ItemFailure("post_unavailable", f"Telegram returned HTTP {exc.code} for the post.")
    return ItemFailure("http_error", f"Telegram returned HTTP {exc.code}.")


def fetch_post_html(target: Target) -> str:
    request = Request(
        target.retrieval_url,
        headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"},
    )
    try:
        with urlopen(request, timeout=HTML_TIMEOUT_SECONDS) as response:
            final = urlsplit(response.geturl())
            if final.scheme.lower() != "https" or (final.hostname or "").lower() not in ALLOWED_POST_HOSTS:
                raise ItemFailure("unexpected_redirect", "Telegram redirected the post request outside the supported host.")
            content_type = response.headers.get_content_type().lower()
            if content_type not in {"text/html", "application/xhtml+xml"}:
                raise ItemFailure("unexpected_response", f"Expected HTML, received {content_type}.")
            data = read_limited(response, MAX_HTML_BYTES)
            encoding = response.headers.get_content_charset() or "utf-8"
            return data.decode(encoding, errors="replace")
    except HTTPError as exc:
        raise http_failure(exc) from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise ItemFailure("network_error", f"Could not retrieve the Telegram post: {exc}") from exc


def safe_link(base_url: str, raw: str | None) -> str | None:
    if not raw:
        return None
    value = urljoin(base_url, html_module.unescape(raw.strip()))
    if urlsplit(value).scheme.lower() not in {"http", "https", "tg"}:
        return None
    return value


def extract_photo_urls(root, retrieval_url: str) -> tuple[list[str], bool]:
    nodes = root.select(".tgme_widget_message_photo_wrap, .tgme_widget_message_photo")
    found: list[str] = []
    seen: set[str] = set()

    def add(raw: str | None) -> None:
        value = safe_link(retrieval_url, raw)
        if value and urlsplit(value).scheme.lower() == "https" and value not in seen:
            seen.add(value)
            found.append(value)

    for node in nodes:
        style = node.get("style") or ""
        for match in BACKGROUND_URL_RE.finditer(style):
            add(match.group(2))
        add(node.get("src"))
        add(node.get("data-src"))
        for image in node.select("img[src], img[data-src]"):
            add(image.get("src") or image.get("data-src"))

    return found, bool(nodes)


def extract_post(target: Target, html: str) -> tuple[dict, list[str], bool, list[str]]:
    soup = BeautifulSoup(html, "html.parser")
    error_node = soup.select_one(".tgme_widget_message_error")
    if error_node is not None:
        message = inline_text(error_node) or "Telegram reported that the post is unavailable."
        raise ItemFailure("post_unavailable", message)

    exact_root = None
    seen_posts: list[str] = []
    for root in soup.select(".tgme_widget_message[data-post]"):
        data_post = str(root.get("data-post") or "")
        seen_posts.append(data_post)
        username, separator, message_text = data_post.rpartition("/")
        if (
            separator
            and message_text.isdigit()
            and username.casefold() == target.username.casefold()
            and int(message_text) == target.message_id
        ):
            exact_root = root
            break

    if exact_root is None:
        if seen_posts:
            raise ItemFailure("exact_message_mismatch", "Telegram returned a different message than the requested post.")
        raise ItemFailure(
            "markup_changed_or_unexpected_response",
            "The expected Telegram message root was not found in the HTML response.",
        )

    text_node = exact_root.select_one(".tgme_widget_message_text")
    links: list[dict] = []
    seen_links: set[tuple[str, str]] = set()
    if text_node is not None:
        for anchor in text_node.select("a[href]"):
            href = safe_link(target.retrieval_url, anchor.get("href"))
            label = inline_text(anchor) or ""
            if href and (label, href) not in seen_links:
                seen_links.add((label, href))
                links.append({"text": label, "url": href})
        for break_tag in text_node.find_all("br"):
            break_tag.replace_with("\n")
    text = compact_text(text_node.get_text("", strip=False) if text_node is not None else None)

    result = {
        "source_url": target.source_url,
        "username": target.username,
        "message_id": target.message_id,
        "text": text,
    }

    author = inline_text(
        exact_root.select_one(".tgme_widget_message_owner_name")
        or exact_root.select_one(".tgme_widget_message_author")
    )
    if author:
        result["author"] = author

    time_node = exact_root.select_one(".tgme_widget_message_date time[datetime]")
    if time_node and time_node.get("datetime"):
        result["datetime"] = str(time_node.get("datetime"))

    views = inline_text(exact_root.select_one(".tgme_widget_message_views"))
    if views:
        result["views"] = views
    if links:
        result["links"] = links

    forward = exact_root.select_one(".tgme_widget_message_forwarded_from_name")
    if forward is not None:
        origin = {}
        name = inline_text(forward)
        href = safe_link(target.retrieval_url, forward.get("href"))
        if name:
            origin["name"] = name
        if href:
            origin["source_url"] = href
        if origin:
            result["forward_origin"] = origin

    photo_urls, has_photo_node = extract_photo_urls(exact_root, target.retrieval_url)
    unprocessed: list[str] = []
    if exact_root.select_one(
        ".tgme_widget_message_audio, .tgme_widget_message_voice"
    ):
        unprocessed.append("audio")
    if exact_root.select_one(
        ".tgme_widget_message_video, .tgme_widget_message_video_player, "
        ".tgme_widget_message_roundvideo"
    ):
        unprocessed.append("video")

    generic_unsupported = exact_root.select_one(".message_media_not_supported") is not None
    if not text and not has_photo_node and not unprocessed:
        if generic_unsupported:
            raise ItemFailure(
                "content_not_exposed",
                "Telegram found the exact post but its public HTML does not expose the post content.",
            )
        raise ItemFailure("no_meaningful_content", "The exact post has no readable text or supported media.")
    return result, photo_urls, has_photo_node, unprocessed


def valid_image_signature(mime_type: str, head: bytes) -> bool:
    signatures = IMAGE_TYPES[mime_type][1]
    if mime_type == "image/webp":
        return head.startswith(b"RIFF") and head[8:12] == b"WEBP"
    return any(head.startswith(signature) for signature in signatures)


def download_image(url: str, store: ArtifactStore, post_index: int, image_index: int) -> dict:
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "image/*"})
    part_path: Path | None = None
    try:
        with urlopen(request, timeout=IMAGE_TIMEOUT_SECONDS) as response:
            final = urlsplit(response.geturl())
            if final.scheme.lower() != "https":
                raise ItemFailure("image_redirect_rejected", "The image redirected to a non-HTTPS URL.")

            mime_type = response.headers.get_content_type().lower()
            if mime_type not in IMAGE_TYPES:
                raise ItemFailure("unsupported_image_type", f"Unsupported image content type: {mime_type}.")

            declared_length = response.headers.get("Content-Length")
            if declared_length and int(declared_length) > MAX_IMAGE_BYTES:
                raise ItemFailure("image_too_large", "The image exceeds the per-image safety limit.")

            directory = store.ensure()
            extension = IMAGE_TYPES[mime_type][0]
            final_path = directory / f"post-{post_index}-image-{image_index}{extension}"
            part_path = final_path.with_suffix(f"{extension}.part")
            size = 0
            head = b""
            with part_path.open("xb") as output:
                while True:
                    chunk = response.read(65536)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > MAX_IMAGE_BYTES:
                        raise ItemFailure("image_too_large", "The image exceeds the per-image safety limit.")
                    if store.total_bytes + size > MAX_BATCH_IMAGE_BYTES:
                        raise ItemFailure("image_batch_too_large", "Downloaded images exceed the batch safety limit.")
                    if len(head) < 16:
                        head += chunk[: 16 - len(head)]
                    output.write(chunk)

            if not valid_image_signature(mime_type, head):
                raise ItemFailure("invalid_image", "The downloaded file does not match its declared image type.")
            part_path.replace(final_path)
            part_path = None
            store.total_bytes += size
            return {"index": image_index, "status": "downloaded", "local_path": str(final_path.resolve())}
    except HTTPError as exc:
        if exc.code == 429:
            raise ItemFailure("image_rate_limited", "Telegram rate-limited the image request.") from exc
        raise ItemFailure("image_http_error", f"The attached image returned HTTP {exc.code}.") from exc
    except (URLError, TimeoutError, OSError) as exc:
        if isinstance(exc, ItemFailure):
            raise
        raise ItemFailure("image_network_error", f"Could not download the attached image: {exc}") from exc
    finally:
        if part_path is not None:
            part_path.unlink(missing_ok=True)


def item_error(raw: str, failure: ItemFailure, target: Target | None = None) -> dict:
    result = {
        "status": "error",
        "source_url": raw.strip(),
        "error": {"code": failure.code, "message": failure.message},
    }
    if target is not None:
        result["username"] = target.username
        result["message_id"] = target.message_id
    return result


def process_target(target: Target, store: ArtifactStore, post_index: int) -> dict:
    html = fetch_post_html(target)
    result, photo_urls, has_photo_node, unprocessed = extract_post(target, html)

    image_results: list[dict] = []
    for image_index, url in enumerate(photo_urls, start=1):
        try:
            image_results.append(download_image(url, store, post_index, image_index))
        except ItemFailure as failure:
            image_results.append(
                {
                    "index": image_index,
                    "status": "error",
                    "error": {"code": failure.code, "message": failure.message},
                }
            )

    if has_photo_node and not photo_urls:
        image_results.append(
            {
                "index": 1,
                "status": "error",
                "error": {
                    "code": "image_url_not_found",
                    "message": "Telegram exposed an attached image but no downloadable image URL.",
                },
            }
        )

    media = {}
    if image_results:
        media["images"] = image_results
    if unprocessed:
        media["unprocessed_types"] = unprocessed
    if media:
        result["media"] = media

    image_failed = any(item["status"] != "downloaded" for item in image_results)
    result["status"] = "partial" if image_failed or unprocessed else "complete"
    return result


def cleanup_artifacts(raw_path: str) -> dict:
    temp_root = Path(tempfile.gettempdir()).resolve()
    candidate = Path(raw_path)
    if not candidate.is_absolute() or candidate.is_symlink():
        raise ItemFailure("unsafe_cleanup_path", "Cleanup requires an absolute non-symlink helper path.")
    try:
        resolved = candidate.resolve(strict=True)
    except FileNotFoundError as exc:
        raise ItemFailure("cleanup_not_found", "The temporary artifact directory does not exist.") from exc
    if resolved.parent != temp_root or not resolved.name.startswith(TEMP_PREFIX):
        raise ItemFailure("unsafe_cleanup_path", "Cleanup path is outside the helper's temporary directory boundary.")
    marker = resolved / MARKER_NAME
    if not marker.is_file() or marker.read_text(encoding="utf-8") != MARKER_CONTENT:
        raise ItemFailure("unsafe_cleanup_path", "Cleanup marker is missing or invalid.")
    shutil.rmtree(resolved)
    return {"cleaned": True, "artifact_dir": str(resolved)}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Retrieve exact public Telegram posts and attached images."
    )
    parser.add_argument("--cleanup", metavar="ARTIFACT_DIR")
    parser.add_argument("urls", nargs="*")
    return parser


def main() -> int:
    args = build_parser().parse_args()

    if args.cleanup is not None:
        if args.urls:
            print("--cleanup cannot be combined with post URLs.", file=sys.stderr)
            return 2
        try:
            write_json_stdout(cleanup_artifacts(args.cleanup))
            return 0
        except ItemFailure as failure:
            print(f"{failure.code}: {failure.message}", file=sys.stderr)
            return 2

    if not args.urls:
        print("At least one Telegram post URL is required.", file=sys.stderr)
        return 2
    if BeautifulSoup is None:
        print("dependency_missing: install beautifulsoup4 from requirements.txt", file=sys.stderr)
        return 2

    store = ArtifactStore()
    artifacts_handed_off = False
    try:
        results: list[dict] = []
        for index, raw in enumerate(args.urls, start=1):
            target = None
            try:
                target = normalize_candidate(raw)
                results.append(process_target(target, store, index))
            except ItemFailure as failure:
                results.append(item_error(raw, failure, target))
            except Exception as exc:  # Preserve a valid batch envelope for an unexpected item failure.
                results.append(
                    item_error(
                        raw,
                        ItemFailure("internal_error", f"Unexpected helper failure: {type(exc).__name__}"),
                        target,
                    )
                )

        envelope = {"schema_version": "1", "results": results}
        if store.directory is not None:
            envelope["artifact_dir"] = str(store.directory)
        write_json_stdout(envelope)
        artifacts_handed_off = True
        return 0 if all(item["status"] == "complete" for item in results) else 1
    finally:
        if not artifacts_handed_off:
            store.discard()


if __name__ == "__main__":
    raise SystemExit(main())
