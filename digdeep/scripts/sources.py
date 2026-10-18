"""Fetch community threads that plain web tools cannot read.

Read public sources through APIs, feeds and HTML where available.
Availability depends on the host and execution environment. Discovery also
uses the caller's web search or search MCPs; these helpers are not exhaustive.

All commands print UTF-8 text to stdout and exit non-zero on failure.

    python sources.py reddit-search "<query>" [--sub NAME] [--limit N]
    python sources.py reddit-thread <permalink-url> [--limit N]
    python sources.py hn-search "<query>" [--limit N]
    python sources.py hn-thread <story-id>
    python sources.py gh-search "<query>" [--limit N]
    python sources.py gh-thread <issue-url | owner/repo#123> [--limit N] [--pages N]
    python sources.py gh-repos "<query>" [--limit N]
    python sources.py hf-search "<query>" [--limit N]
    python sources.py habr-search "<query>" [--order rating|relevance] [--limit N]
    python sources.py so-search "<query>" [--site ru.stackoverflow] [--limit N]
    python sources.py so-thread <question-id> [--site NAME] [--limit N]
    python sources.py tg-channel <channel> [--q "<query>"] [--limit N]
    python sources.py yt-transcript <youtube-url | video-id> [--lang auto|ru|en|CODE]

The endpoints used are public and require no token, subject to access and
rate limits. GitHub keyword search combines terms restrictively: start with
two or three words and use repo:owner/name when narrowing to a known project.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import functools
import gzip
import html
import importlib.util
import json
import os
import re
import shutil
# Subprocess calls only invoke resolved Python/yt-dlp binaries, without a shell.
import subprocess  # nosec B404
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
# Public TLS feeds only; ElementTree does not resolve external entities.
import xml.etree.ElementTree as ET  # nosec B405
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

# Reddit rejects the default urllib agent; old.reddit needs a browser-shaped one.
UA_FEED = "digdeep/1.0 (personal research)"
UA_HTML = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
           "(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36")
ATOM = {"a": "http://www.w3.org/2005/Atom"}
DEFAULT_TIMEOUT = 30
DEFAULT_RETRIES = 3
DEFAULT_MAX_BODY_CHARS = 4000


def clip_text(text: str, ref_url: str = "", limit: int | None = None) -> str:
    """Bound one long comment/answer body while keeping both opening and conclusion."""
    actual = DEFAULT_MAX_BODY_CHARS if limit is None else limit
    if actual <= 0 or len(text) <= actual:
        return text
    head_len, tail_len = int(actual * 0.65), max(1, actual - int(actual * 0.65))
    where = f" or inspect {ref_url}" if ref_url else ""
    return (f"{text[:head_len]}\n... [truncated {len(text) - head_len - tail_len} chars of "
            f"comment body; pass --max-body-chars 0 for full text{where}] ...\n{text[-tail_len:]}")


def looks_like_captcha(body: str) -> bool:
    """Recognize a likely HTML challenge, not discussions containing its name."""
    head = body[:8000].lower()
    if len(body) >= 40_000 or not re.match(r"\s*(?:<!doctype html|<html)", head):
        return False
    title = re.search(r"<title[^>]*>(.*?)</title>", head, re.S)
    if not title:
        return False
    name = strip_tags(title.group(1)).strip(" .…")
    return name in {"just a moment", "checking your browser", "are you a robot",
                    "captcha", "ddos-guard", "подтвердите, что вы не робот"}


def wall_error(url: str) -> SystemExit:
    """Explain the observed challenge without claiming it was read."""
    return SystemExit(
        f"Possible CAPTCHA/anti-bot wall at {urllib.parse.urlsplit(url).netloc}: {url}\n"
        "Content was not read. Use an authorized API/feed or another accessible "
        "copy, label its provenance, or ask the user to complete login/CAPTCHA "
        "in their browser. Resume after confirmation. Do not bypass access controls.")


def http_error_detail(exc: urllib.error.HTTPError, url: str) -> tuple[str, float | None]:
    """Classify an HTTP failure and return (status_detail, retry_delay_or_none)."""
    if looks_like_captcha(exc.read(40_000).decode("utf-8", "replace")):
        exc.close()
        raise wall_error(url) from exc
    exc.close()
    detail = f"HTTP {exc.code}"
    if exc.code in (403, 429) and (
            exc.headers.get("X-RateLimit-Remaining") if exc.headers else "") == "0":
        reset = (exc.headers.get("X-RateLimit-Reset") if exc.headers else None) or "unknown"
        return f"{detail}; rate limit exhausted (X-RateLimit-Reset={reset})", None
    retry_after = exc.headers.get("Retry-After", "") if exc.headers else ""
    if retry_after:
        detail += f"; Retry-After={retry_after}"
        return (detail, float(retry_after)) if (
            retry_after.isdigit() and int(retry_after) <= 30) else (detail, None)
    return (detail, 0.0) if exc.code in (429, 500, 502, 503) else (detail, None)


class HTTPSRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Keep redirects on HTTPS and authenticated requests at their original origin."""

    # The override must retain urllib's six-argument callback interface.
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # pylint: disable=too-many-arguments,too-many-positional-arguments
        before, after = urllib.parse.urlsplit(req.full_url), urllib.parse.urlsplit(newurl)
        if after.scheme != "https":
            fp.close()
            raise SystemExit("refusing non-https redirect")
        try:
            before_port, after_port = before.port, after.port
        except ValueError as exc:
            fp.close()
            raise SystemExit("refusing redirect with invalid port") from exc
        if req.has_header("Authorization") and (
                before.hostname, 443 if before_port is None else before_port) != (
                after.hostname, 443 if after_port is None else after_port):
            fp.close()
            raise SystemExit("refusing cross-origin redirect for an authenticated request")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch(url: str, agent: str, timeout: int | None = None,
          retries: int | None = None) -> str:
    """GET with backoff. Reddit answers 429 readily, so retry rather than fail.

    Only https is accepted: a thread URL reaches this function from the caller,
    and file:/ or custom schemes would otherwise turn a fetch into a local read.

    Anti-bot walls are named, never solved: the caller is told which host put up
    a challenge so it can take the legitimate path (API, RSS, a search MCP's
    extract, the archive) or hand the URL to the human.
    """
    if not url.startswith("https://"):
        raise SystemExit(f"refusing non-https url: {url}")
    actual_timeout = DEFAULT_TIMEOUT if timeout is None else timeout
    attempts = DEFAULT_RETRIES if retries is None else retries
    delay, last = 4.0, ""
    headers = {"User-Agent": agent, "Accept-Encoding": "gzip"}
    gh_token = ((os.environ.get("GITHUB_TOKEN") or "").strip()
                or (os.environ.get("GH_TOKEN") or "").strip())
    if url.startswith("https://api.github.com/") and gh_token:
        headers["Authorization"] = f"Bearer {gh_token}"
    opener = urllib.request.build_opener(HTTPSRedirectHandler())
    for attempt in range(attempts):
        req = urllib.request.Request(url, headers=headers)
        try:
            with opener.open(req, timeout=actual_timeout) as resp:  # nosec B310
                raw = resp.read()
                if resp.headers.get("Content-Encoding") == "gzip":
                    raw = gzip.decompress(raw)
                body = raw.decode("utf-8", "replace")
                if looks_like_captcha(body):
                    raise wall_error(url)
                return body
        except urllib.error.HTTPError as exc:
            last, retry_delay = http_error_detail(exc, url)
            if retry_delay is None or attempt == attempts - 1:
                break
            delay = max(delay, retry_delay)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last = f"{type(exc).__name__}: {exc}"
            if attempt == attempts - 1:
                break
        time.sleep(delay)
        delay *= 2
    raise SystemExit(f"fetch failed after {attempt + 1} attempt(s): {url} ({last})")


HEALTH_ENDPOINTS = (
    ("Reddit discovery RSS",
     "https://www.reddit.com/search.rss?q=digdeep&sort=relevance&t=all", UA_FEED),
    ("Reddit thread HTML", "https://old.reddit.com/", UA_HTML),
    ("Hacker News API",
     "https://hn.algolia.com/api/v1/search?query=digdeep&tags=story&hitsPerPage=1", UA_FEED),
    ("GitHub public API", "https://api.github.com/rate_limit", UA_FEED),
    ("Hugging Face API", "https://huggingface.co/api/models?limit=1", UA_FEED),
    ("Stack Exchange API", "https://api.stackexchange.com/2.3/info?site=stackoverflow", UA_FEED),
    ("Habr RSS",
     "https://habr.com/ru/rss/search/?q=python&target_type=posts&order=rating", UA_HTML),
    ("Telegram public preview", "https://t.me/s/telegram", UA_HTML),
)


def health(timeout: int) -> None:
    """Check helper dependencies and public route reachability without scraping content."""
    def probe(entry: tuple[str, str, str]) -> tuple[str, str]:
        label, url, agent = entry
        try:
            fetch(url, agent, timeout=timeout, retries=1)
        except SystemExit as exc:
            detail = " ".join(str(exc).splitlines())
            return label, f"UNAVAILABLE: {detail}"
        return label, "OK"

    print("# digdeep health\n")
    print("# Reachability only: OK does not validate search, parsing or thread access.\n")
    ytdlp_cmd = resolve_ytdlp()
    ytdlp_status = ("available" if ytdlp_cmd == [sys.executable, "-m", "yt_dlp"] else
                    f"available (via {' '.join(ytdlp_cmd)})" if ytdlp_cmd else
                    "not installed (YouTube transcripts unavailable)")
    print(f"Python: {sys.version.split()[0]}")
    print(f"yt-dlp: {ytdlp_status}")
    print(f"Per-route timeout: {timeout}s; total attempts: 1\n")
    with ThreadPoolExecutor(max_workers=len(HEALTH_ENDPOINTS)) as pool:
        results = list(pool.map(probe, HEALTH_ENDPOINTS))
    for label, result in results:
        print(f"{label}: {result}")
    if any("timed out" in result or "TimeoutError" in result for _, result in results):
        print("\n# Note: timeout(s) detected; slow TLS or IPv6->IPv4 fallback can exceed "
              "short probe timeouts. Re-run with --timeout 20 before treating timed-out "
              "routes as blocked.")


class TextParser(HTMLParser):
    """Render source HTML without losing code indentation or link destinations."""

    BLOCKS = {"p", "div", "pre", "li", "blockquote", "tr", "h1", "h2", "h3", "h4"}

    def __init__(self, base_url: str = "") -> None:
        super().__init__()
        self.base_url = base_url
        self.parts: list[str] = []
        self.verbatim = 0
        self.hidden = 0
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style"}:
            self.hidden += 1
        if self.hidden:
            return
        if tag in self.BLOCKS or tag == "br":
            self.parts.append("\n")
        # Cell-start separators also handle omitted </td> and </th> tags.
        if tag in {"td", "th"}:
            self.parts.append("\t")
        if tag in {"pre", "code"}:
            self.verbatim += 1
        if tag == "a":
            href = dict(attrs).get("href") or ""
            try:
                href = urllib.parse.urljoin(self.base_url, href) if href else ""
                if urllib.parse.urlsplit(href).scheme not in {"http", "https"}:
                    href = ""
            except ValueError:
                href = ""
            self.links.append(href)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"}:
            self.hidden = max(0, self.hidden - 1)
            return
        if self.hidden:
            return
        if tag == "a" and self.links:
            href = self.links.pop()
            if href:
                self.parts.append(f" <{href}>")
        if tag in {"pre", "code"}:
            self.verbatim = max(0, self.verbatim - 1)
        if tag in self.BLOCKS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.hidden:
            self.parts.append(data if self.verbatim else re.sub(r"\s+", " ", data))

    def text(self) -> str:
        """Keep whitespace inside source code intact."""
        return "".join(self.parts).strip("\n")


def strip_tags(fragment: str, base_url: str = "") -> str:
    """Render an HTML fragment, resolving relative links against its source URL."""
    parser = TextParser(base_url)
    parser.feed(fragment)
    parser.close()
    return parser.text()


def fetch_feed(url: str, agent: str, root_tag: str) -> ET.Element:
    """Reject access pages and malformed feeds instead of reporting zero hits."""
    body = fetch(url, agent)
    try:
        # Public TLS feeds only; ElementTree does not resolve external entities.
        root = ET.fromstring(body)  # nosec B314
    except ET.ParseError as exc:
        raise SystemExit(f"Invalid feed at {url}: {exc}. Content was not read.") from exc
    if root.tag != root_tag or (root_tag == "rss" and root.find("channel") is None):
        raise SystemExit(f"Expected a feed at {url}, got {root.tag!r}. "
                         "Possible access page or changed format; content was not read.")
    return root


def reddit_search(query: str, sub: str | None, limit: int) -> None:
    """Relevance-ranked, all-time discovery through the public RSS feed."""
    q = urllib.parse.quote_plus(query)
    if sub:
        url = (f"https://www.reddit.com/r/{sub}/search.rss"
               f"?q={q}&restrict_sr=on&sort=relevance&t=all")
    else:
        url = f"https://www.reddit.com/search.rss?q={q}&sort=relevance&t=all"
    # The feed is Reddit-generated and served over TLS, and stdlib ElementTree
    # resolves no external entities. Revisit if ever fetched from a mirror.
    root = fetch_feed(url, UA_FEED, "{http://www.w3.org/2005/Atom}feed")

    def href(entry: ET.Element) -> str:
        link = entry.find("a:link", ATOM)
        return (link.get("href") or "") if link is not None else ""

    # The feed mixes matching subreddits in with posts; only posts have /comments/.
    entries = [e for e in root.findall("a:entry", ATOM) if "/comments/" in href(e)]
    print(f"# reddit search: {query!r} sub={sub or 'all'} -> {len(entries)} posts\n")
    for entry in entries[:limit]:
        title = (entry.findtext("a:title", "", ATOM) or "").strip()
        when = (entry.findtext("a:updated", "", ATOM) or "")[:10]
        print(f"{when}  {title}\n          {href(entry)}")


def reddit_thread_rss(base_path: str, limit: int, html_reason: str) -> None:
    """Read a verified, explicitly partial thread feed after an HTML failure."""
    rss_url = f"https://www.reddit.com{base_path}/.rss?limit=500"
    canonical = f"https://www.reddit.com{base_path}"
    try:
        root = fetch_feed(rss_url, UA_FEED, "{http://www.w3.org/2005/Atom}feed")
    except SystemExit as exc:
        if "429" in str(exc):
            raise SystemExit(
                f"{html_reason}\nFallback .rss rate-limited ({exc}).\n"
                "Respect server backoff; retry later or search lawful mirrors/archives."
            ) from exc
        raise SystemExit(
            f"{html_reason}\nFallback .rss also failed ({exc}).\n"
            "Try searching the exact thread title or ID for lawful mirrors/archives, "
            "or warn the user and offer to search for current Reddit access methods."
        ) from exc
    entries = root.findall("a:entry", ATOM)
    if not entries:
        raise SystemExit(f"{html_reason}\nFallback .rss returned zero entries: {rss_url}")
    post_entry = entries[0]
    expected = "t3_" + base_path.split("/comments/", 1)[1].split("/", 1)[0]
    if post_entry.findtext("a:id", "", ATOM) != expected:
        raise SystemExit(f"{html_reason}\nRSS post identity does not match {expected}: {rss_url}. "
                         "Requested thread was not read.")
    readable = [(entry, strip_tags(entry.findtext("a:content", "", ATOM) or "", canonical))
                for entry in entries[1:]]
    readable = [(entry, text) for entry, text in readable
                if text.strip() and text.strip() not in ("[removed]", "[deleted]")][:limit]
    print(f"# {(root.findtext('a:title', '', ATOM) or canonical).strip()}\n"
          f"# {canonical} (read via .rss fallback; scores omitted by feed)")
    print("# HTML route: " + " ".join(html_reason.splitlines()))
    print(f"# RSS comment entries: {len(entries) - 1}, shown: {len(readable)}")
    print("# PARTIAL: a feed is not a guaranteed full thread; omitted branches remain unread.\n")
    print("## post\n")
    print(clip_text(strip_tags(post_entry.findtext("a:content", "", ATOM) or "", canonical)
                    or "(empty — link post)", ref_url=canonical), "\n")
    print("## comments (from RSS feed)\n")
    for entry, body in readable:
        author = (entry.findtext("a:author/a:name", "", ATOM) or "?").lstrip("/")
        link = entry.find("a:link", ATOM)
        print(f"[rss] {author}: {clip_text(body, ref_url=canonical)}\n")
        if link is not None and link.get("href"):
            print(f"  {link.get('href')}\n")


def reddit_thread(url: str, limit: int) -> None:  # pylint: disable=too-many-locals
    """Read comments returned by old.reddit, falling back to thread .rss if blocked."""
    parts = urllib.parse.urlsplit(url)
    if parts.hostname not in {"reddit.com", "www.reddit.com", "new.reddit.com",
                              "old.reddit.com"} or "/comments/" not in parts.path:
        raise SystemExit(f"not a reddit permalink: {url}")
    # Remove .rss/.json suffixes to avoid duplication when agent passes them
    base_path = "/".join(re.sub(
        r"(?:/\.(?:rss|json)|\.(?:rss|json))$", "", parts.path.rstrip("/")).split("/")[:6])
    permalink = "https://old.reddit.com" + base_path
    try:
        page = fetch(f"{permalink}/?sort=top&limit=500", UA_HTML)
    except SystemExit as exc:
        if "HTTP 429" in str(exc):
            raise SystemExit(
                f"{exc}\nReddit rate limit: respect server backoff before another Reddit request; "
                "other independent sources may continue."
            ) from exc
        reddit_thread_rss(base_path, limit, f"old.reddit fetch failed ({exc}).")
        return

    head = re.search(r"<title>(.*?)</title>", page, re.S)
    title = strip_tags(head.group(1)) if head else permalink
    # Each comment is its own t1_ container; the submission sits in a t3_ one.
    # Scores are not on the container as attributes, only in the vote widget.
    chunks = re.split(r'<div class=" thing id-t1_', page)[1:]
    post = re.search(r'<div class=" thing id-t3_.*?<div class="md">(.*?)</div>', page, re.S)
    if not chunks and "id-t3_" not in page:
        reddit_thread_rss(
            base_path, limit,
            f"old.reddit returned no recognizable thread content (title: {title})."
        )
        return

    print(f"# {title}\n# {permalink}\n# parsed comment containers: {len(chunks)}")
    print(f"# Showing up to {limit}; this is not a guaranteed full thread.\n")
    print("## post\n")
    post_text = strip_tags(post.group(1), permalink) if post else "(none)"
    print(clip_text(post_text or "(empty — link post)", permalink), "\n")

    print("## comments (top-sorted)\n")
    shown = 0
    for chunk in chunks:
        if shown >= limit:
            break
        body = re.search(r'<div class="md">(.*?)</div>', chunk, re.S)
        if not body:
            continue
        text = strip_tags(body.group(1), permalink)
        if not text or text in ("[removed]", "[deleted]"):
            continue
        author = re.search(r'data-author="([^"]*)"', chunk)
        # The submission carries the score as a title attribute, comments as
        # span text ("47 points"). Try both rather than assume one shape.
        score = (re.search(r'class="score unvoted"[^>]*title="(-?\d+)"', chunk)
                 or re.search(r'class="score unvoted"[^>]*>\s*([^<]+?)\s*<', chunk))
        comment_id = re.match(r"([a-zA-Z0-9]+)", chunk)
        comment_url = f"{permalink}/{comment_id.group(1)}/" if comment_id else permalink
        print(f"[{score.group(1) if score else '?'}] "
              f"{author.group(1) if author else '?'}: "
              f"{clip_text(text, ref_url=comment_url)}\n")
        if comment_id:
            print(f"  {comment_url}\n")
        shown += 1


def hn_search(query: str, limit: int) -> None:
    """Algolia ANDs every token, so a themed query matches nothing.

    Marking all but the first token optional makes it rank by how many tokens
    match instead of requiring all of them.
    """
    tokens = re.sub(r"[-,]+", " ", query).split()
    params = {"query": " ".join(tokens), "tags": "story", "hitsPerPage": str(limit)}
    if len(tokens) > 1:
        params["optionalWords"] = " ".join(tokens[1:])
    url = "https://hn.algolia.com/api/v1/search?" + urllib.parse.urlencode(params)
    data = json.loads(fetch(url, UA_FEED))
    hits = data.get("hits", [])
    print(f"# hn search: {query!r} -> {data.get('nbHits')} hits\n")
    for hit in hits:
        print(f"{(hit.get('created_at') or '')[:10]}  {hit.get('points')}pts "
              f"{hit.get('num_comments')}c  {hit.get('title')}")
        print(f"          id={hit.get('objectID')}  {hit.get('url') or ''}")


def hn_thread(story_id: str, limit: int) -> None:
    """Print a bounded story comment tree, indented by reply depth."""
    data = json.loads(fetch(f"https://hn.algolia.com/api/v1/items/{story_id}", UA_FEED))

    def walk(node: dict, depth: int = 0) -> list[tuple[int, dict]]:
        out: list[tuple[int, dict]] = []
        for child in node.get("children") or []:
            if child.get("text"):
                out.append((depth, child))
            out.extend(walk(child, depth + 1))
        return out

    rows = walk(data)
    print(f"# {data.get('title')}\n# https://news.ycombinator.com/item?id={story_id}")
    print(f"# comments returned by API: {len(rows)}, shown: {min(len(rows), limit)}\n")
    if len(rows) > limit:
        print("# PARTIAL: use --limit to expand; "
              "omitted comments are not absent from the thread.\n")
    source_url = f"https://news.ycombinator.com/item?id={story_id}"
    print("## post\n", clip_text(strip_tags(data.get("text") or "(link post)", source_url),
                                 ref_url=source_url), "\n")
    for depth, node in rows[:limit]:
        item_url = f"https://news.ycombinator.com/item?id={node.get('id')}"
        rendered = clip_text(strip_tags(node["text"], source_url), ref_url=item_url)
        print(f"{'  ' * depth}[{node.get('author') or '?'}] {rendered}")
        print(f"{'  ' * depth}{item_url}\n")


def gh_get(url: str, shape: type) -> Any:
    """Read a public GitHub endpoint, validating the expected response shape."""
    data = json.loads(fetch(url, UA_FEED))
    if not isinstance(data, shape):
        raise SystemExit(f"unexpected GitHub response: got {type(data).__name__}, "
                         f"expected {shape.__name__} — {url}")
    return data


def gh_search(query: str, limit: int) -> None:
    """Search issues and PRs, most-reacted first."""
    params = {"q": query, "sort": "reactions", "order": "desc",
              "per_page": str(limit)}
    data = gh_get("https://api.github.com/search/issues?"
                  + urllib.parse.urlencode(params), dict)
    print(f"# github search: {query!r} -> {data.get('total_count')} hits\n")
    for item in data.get("items", []):
        print(f"{(item.get('created_at') or '')[:10]}  "
              f"{item.get('comments')}c  {item.get('title', '')[:66]}")
        print(f"          {item.get('html_url')}")


def gh_thread(ref: str, limit: int, pages: int = 3) -> None:
    """Read bounded pages, retain recent/maintainer replies and label omissions.

    ``ref`` is a full issue URL or ``owner/repo#123``.
    """
    m = re.search(r"(?:github\.com/)?([\w.-]+/[\w.-]+?)(?:/issues/|/pull/|#)(\d+)", ref)
    if not m:
        raise SystemExit(f"expected an issue URL or owner/repo#123, got: {ref}")
    base_url = f"https://api.github.com/repos/{m.group(1)}/issues/{m.group(2)}"
    issue = gh_get(base_url, dict)
    total = issue.get("comments", 0)
    last_page = max(1, (total + 99) // 100)
    page_numbers = list(range(1, min(last_page, pages) + 1)) if total else []
    if last_page > pages:
        page_numbers[-1] = last_page
    raw = [c for p in page_numbers
           for c in gh_get(f"{base_url}/comments?per_page=100&page={p}", list)]
    shown = select_gh_comments(raw, limit, (issue.get("user") or {}).get("login") or "")
    print(f"# {issue.get('title')}\n# {issue.get('html_url')}")
    print(f"# state={issue.get('state')} reason={issue.get('state_reason') or '?'} "
          f"updated={issue.get('updated_at') or '?'}")
    print(f"# comments: reported={total}, fetched={len(raw)}, shown={len(shown)}; "
          f"pages={page_numbers}")
    if len(raw) < total or len(shown) < len(raw):
        omitted = [len((c.get("body") or "").strip()) for c in raw if c not in shown]
        print(f"# PARTIAL (not_fetched={max(0, total - len(raw))}, "
              f"fetched_but_unshown={len(omitted)}, max_chars={max(omitted, default=0)}): "
              "use --pages/--limit to expand; absence here is not absence in the thread.")
    print("## issue\n\n" + clip_text(issue.get("body") or "(empty)",
                                     issue.get("html_url", "")) + "\n")
    print("## selected comments (chronological; latest/maintainers/author prioritized)\n")
    for comment in shown:
        reactions = comment.get("reactions", {})
        print(f"[+{reactions.get('+1', 0)} / -{reactions.get('-1', 0)}; "
              f"{reactions.get('total_count', 0)} reactions] "
              f"{(comment.get('user') or {}).get('login', '?')} "
              f"({comment.get('author_association', '?')}, {comment.get('created_at', '?')}):\n"
              f"{clip_text(comment.get('body') or '(empty)', comment.get('html_url', ''))}\n"
              f"{comment.get('html_url') or '(comment URL unavailable)'}\n")


def select_gh_comments(comments: list[dict], limit: int, issue_author: str = "") -> list[dict]:
    """Prioritize chronology, one substantive author reply, and one supported reply."""
    def is_sub(comment: dict) -> bool:
        body = (comment.get("body") or "").strip()
        return len(body) >= 80 or bool(re.search(r"`|https?://|\d", body))

    by_time = sorted(comments, key=lambda c: (c.get("created_at", ""), c.get("id", 0)))
    roles = {"OWNER", "MEMBER", "COLLABORATOR"}
    maint = [c for c in reversed(by_time) if c.get("author_association") in roles]
    ranked = sorted(by_time, key=lambda c: (
        c.get("reactions", {}).get("+1", 0), is_sub(c),
        len((c.get("body") or "").strip())), reverse=True)
    author = [c for c in reversed(by_time) if issue_author
              and (c.get("user") or {}).get("login") == issue_author and is_sub(c)]
    positive = [c for c in ranked if c.get("reactions", {}).get("+1", 0) > 0]
    selected: dict[Any, dict] = {}
    for comment in [*by_time[-1:], *by_time[:1], *author[:1], *positive[:1],
                    *[c for c in maint if is_sub(c)], *author, *positive, *ranked, *maint]:
        selected.setdefault(comment.get("id", comment.get("html_url")), comment)
    return sorted(list(selected.values())[:limit],
                  key=lambda c: (c.get("created_at", ""), c.get("id", 0)))


def translated_track(entries: list[dict]) -> bool:
    """A tlang query parameter identifies YouTube's automatic translation."""
    return any("tlang" in urllib.parse.parse_qs(
        urllib.parse.urlsplit(entry.get("url", "")).query) for entry in entries)


def youtube_id(ref: str) -> str:
    """Accept one video ID or an ordinary YouTube video URL."""
    ref = ref.strip()
    if re.fullmatch(r"[a-zA-Z0-9_-]{11}", ref):
        return ref
    parts = urllib.parse.urlsplit(ref)
    if parts.hostname in {"youtu.be", "www.youtu.be"}:
        candidate = parts.path.strip("/")
    elif parts.hostname in {"youtube.com", "www.youtube.com", "m.youtube.com"}:
        candidate = (urllib.parse.parse_qs(parts.query).get("v") or [""])[0]
        if parts.path.startswith(("/shorts/", "/embed/", "/live/")):
            candidate = parts.path.split("/")[2]
    else:
        candidate = ""
    if not re.fullmatch(r"[a-zA-Z0-9_-]{11}", candidate):
        raise SystemExit(f"expected a YouTube URL or 11-char video id, got: {ref}")
    return candidate


def language_matches(track: str, requested: str) -> bool:
    """A bare language accepts variants; an explicit region must match exactly."""
    language = track.casefold().removesuffix("-orig")
    requested = requested.casefold()
    return language == requested or (
        "-" not in requested and language.split("-")[0] == requested)


def caption_track(info: dict, requested: str) -> tuple[str, str, str]:
    """Choose one track, preferring original language and then manual captions."""
    manual = info.get("subtitles") or {}
    automatic = info.get("automatic_captions") or {}
    tracks = {key: ("manual", value) for key, value in manual.items() if key != "live_chat"}
    for key, value in automatic.items():
        if key != "live_chat":
            tracks.setdefault(key, ("automatic", value))
    if not tracks:
        raise SystemExit("Metadata lists no subtitle tracks; speech content is unverified.")
    original = info.get("language") or next(
        (key.removesuffix("-orig") for key in automatic if key.endswith("-orig")), "")
    wanted = original if requested == "auto" else requested
    matching = [key for key in tracks
                if wanted and language_matches(key, wanted)]
    if requested != "auto" and not matching:
        raise SystemExit(f"No {requested!r} subtitle track. Available: {', '.join(tracks)}")
    candidates = matching or list(tracks)

    chosen = min(candidates, key=lambda key: (
        translated_track(tracks[key][1]),
        key.removesuffix("-orig").casefold() != wanted.casefold(),
        tracks[key][0] != "manual", not key.endswith("-orig"), key))
    origin = ("auto-translated" if translated_track(tracks[chosen][1]) else
              "original" if original and language_matches(chosen, original) else "unknown")
    return chosen, tracks[chosen][0], origin


@functools.lru_cache(maxsize=1)
def resolve_ytdlp() -> list[str] | None:
    """Find a working yt-dlp through bounded, local version probes."""
    candidates = []
    if importlib.util.find_spec("yt_dlp") is not None:
        candidates.append([sys.executable, "-m", "yt_dlp"])
    binary = shutil.which("yt-dlp")
    if binary:
        candidates.append([binary])
    for name in ("py", "python3", "python"):
        launcher = shutil.which(name)
        if launcher:
            candidates.append([launcher, "-m", "yt_dlp"])
    seen: set[tuple[str, ...]] = set()
    for candidate in candidates:
        if tuple(candidate) in seen:
            continue
        seen.add(tuple(candidate))
        try:
            probe = subprocess.run(
                [*candidate, "--version"], capture_output=True,
                timeout=3, check=False  # nosec B603
            )
        except (OSError, subprocess.SubprocessError):
            continue
        if probe.returncode == 0:
            return candidate
    return None


def run_ytdlp(arguments: list[str], folder: str) -> subprocess.CompletedProcess:
    """Bounded caption-only invocation; errors retain their actual cause."""
    base_cmd = resolve_ytdlp()
    if base_cmd is None:
        raise SystemExit("yt-dlp is not available in current Python, PATH, or launchers.")
    # The helper counts total attempts; yt-dlp counts retries after the first attempt.
    retries = str(DEFAULT_RETRIES - 1)
    command = [*base_cmd, "--ignore-config", "--no-cache-dir",
               "--no-playlist", "--skip-download", "--socket-timeout", str(DEFAULT_TIMEOUT),
               "--retries", retries, "--extractor-retries", retries, *arguments]
    try:
        done = subprocess.run(command, cwd=folder, capture_output=True,  # nosec B603
                              encoding="utf-8", errors="replace",
                              timeout=DEFAULT_TIMEOUT * DEFAULT_RETRIES, check=False)
    except subprocess.TimeoutExpired as exc:
        raise SystemExit("yt-dlp exceeded the per-stage timeout/retry budget; "
                         "subtitle availability is unknown. Try another authorized route.") from exc
    except OSError as exc:
        raise SystemExit(f"yt-dlp could not start: {exc}. "
                         "Subtitle availability is unknown; try another authorized route.") from exc
    if done.returncode:
        tail = (done.stderr or done.stdout or "").strip().splitlines()
        raise SystemExit("yt-dlp failed; this does not establish absent subtitles:\n"
                         + "\n".join(tail[-5:]))
    return done


def print_captions(events: list[dict], block_seconds: int) -> None:
    """Keep the existing timestamped-block presentation for json3 captions."""
    bucket_start = 0
    chunk: list[str] = []
    words_seen = False
    for event in events:
        text = "".join(s.get("utf8", "") for s in event.get("segs") or []).strip()
        if not text:
            continue
        words_seen = True
        start = int(event.get("tStartMs", 0)) // 1000
        if chunk and start - bucket_start >= block_seconds:
            print(f"[{bucket_start // 60:02d}:{bucket_start % 60:02d}] "
                  f"{' '.join(chunk)}\n")
            bucket_start, chunk = start, []
        if not chunk:
            bucket_start = start
        chunk.append(text)
    if not words_seen:
        raise SystemExit("Subtitle track is empty; speech content is unverified.")
    print(f"[{bucket_start // 60:02d}:{bucket_start % 60:02d}] {' '.join(chunk)}")


def yt_transcript(ref: str, block_seconds: int = 30, lang: str = "auto") -> None:
    """Download one subtitle track via yt-dlp, never the audio or video."""
    if resolve_ytdlp() is None:
        raise SystemExit(
            "yt-dlp is not installed in current Python, PATH, or standard launchers, "
            "so helper YouTube transcripts are unavailable.\n"
            "Install it with:  python -m pip install --user yt-dlp\n"
            "Alternatively use the video's browser transcript or an authorized caption source; "
            "identify the source and request user help for login/CAPTCHA if needed.")

    video_id = youtube_id(ref)
    url = f"https://www.youtube.com/watch?v={video_id}"
    with tempfile.TemporaryDirectory() as tmp:
        metadata = run_ytdlp(["--dump-single-json", url], tmp)
        info = json.loads(metadata.stdout)
        language, kind, origin = caption_track(info, lang)
        info_file = Path(tmp) / "video.info.json"
        info_file.write_text(json.dumps(info), encoding="utf-8")
        run_ytdlp(["--load-info-json", str(info_file), "--write-auto-subs",
                   "--write-subs", "--sub-langs", re.escape(language),
                   "--sub-format", "json3", "-o", "%(id)s"], tmp)
        pick = Path(tmp) / f"{video_id}.{language}.json3"
        if not pick.exists():
            raise SystemExit("Selected track was not saved as json3; content is unverified.")
        events = json.loads(pick.read_text(encoding="utf-8")).get("events", [])
    print(f"# {info.get('title') or '(title unavailable)'}\n# {url}\n"
          f"# language={language}; captions={kind}; origin={origin}\n")
    print_captions(events, block_seconds)


def gh_repos(query: str, limit: int) -> None:
    """Search repositories, most-starred first — issue search does not find them.

    `gh-search` looks inside issues and PRs only, so a tool that has never been
    argued about in an issue is invisible to it. Keep the query short: GitHub
    ANDs every term.
    """
    params = {"q": query, "sort": "stars", "order": "desc", "per_page": str(limit)}
    data = gh_get("https://api.github.com/search/repositories?"
                  + urllib.parse.urlencode(params), dict)
    print(f"# github repos: {query!r} -> {data.get('total_count')} hits\n")
    for item in data.get("items", []):
        print(f"{item.get('stargazers_count'):>6}★  {item.get('full_name')}"
              f"  [{item.get('language') or '—'}]"
              f"  upd {(item.get('pushed_at') or '')[:10]}")
        print(f"          {' '.join((item.get('description') or '').split())[:120]}")
        print(f"          {item.get('html_url')}")


def hf_search(query: str, limit: int) -> None:
    """Search public Hugging Face models, most-downloaded first."""
    params = {"search": query, "limit": str(limit), "sort": "downloads",
              "direction": "-1", "full": "false"}
    url = "https://huggingface.co/api/models?" + urllib.parse.urlencode(params)
    data = json.loads(fetch(url, UA_FEED))
    print(f"# huggingface: {query!r} -> {len(data)} models\n")
    for model in data:
        print(f"{model.get('downloads', 0):>8} ↓  {model.get('modelId')}"
              f"  [{model.get('pipeline_tag') or '—'}]"
              f"  {model.get('likes', 0)}♥")
        print(f"          https://huggingface.co/{model.get('modelId')}")


def habr_search(query: str, order: str, limit: int) -> None:
    """Habr search over its RSS feed: the RuNet source with real write-ups.

    `order=rating` is the endorsement signal here, the same role Reddit score
    plays. `relevance` is the fallback when a themed query drifts.
    """
    url = ("https://habr.com/ru/rss/search/?q=" + urllib.parse.quote(query)
           + f"&target_type=posts&order={order}")
    root = fetch_feed(url, UA_HTML, "rss")
    items = root.findall(".//item")
    print(f"# habr: {query!r} order={order} -> {len(items)} posts\n")
    for item in items[:limit]:
        body = strip_tags(item.findtext("description") or "", item.findtext("link") or url)
        print(f"{(item.findtext('pubDate') or '')[5:16]}  "
              f"{(item.findtext('title') or '').strip()}")
        print(f"          {(item.findtext('link') or '').split('?')[0]}")
        print(f"          {' '.join(body.split())[:150]}")


def so_search(query: str, site: str, limit: int) -> None:
    """Stack Exchange search, relevance-ranked. `--site ru.stackoverflow` for RuNet."""
    data = se_get("search/advanced", site, order="desc", sort="relevance",
                  q=query, pagesize=str(limit), filter="default")
    items = data.get("items", [])
    print(f"# {site}: {query!r} -> {len(items)} questions"
          f"  (quota left {data.get('quota_remaining')})\n")
    for item in items:
        print(f"[{item.get('score'):>3} pts, {item.get('answer_count')} ans"
              f"{', accepted' if item.get('accepted_answer_id') else ''}]  "
              f"{html.unescape(item.get('title', ''))}")
        print(f"          id={item.get('question_id')}  {item.get('link')}")


def se_get(path: str, site: str, **params: str) -> dict:
    """Read Stack Exchange and honor its requested backoff before another call."""
    query = urllib.parse.urlencode({"site": site, "filter": "withbody", **params})
    data = json.loads(fetch(f"https://api.stackexchange.com/2.3/{path}?{query}", UA_FEED))
    backoff = int(data.get("backoff", 0))
    if backoff > 30:
        raise SystemExit(f"Stack Exchange requests {backoff}s backoff; retry later.")
    if backoff:
        time.sleep(backoff)
    return data


def so_thread(qid: str, site: str, limit: int) -> None:
    """Question, selected answers, and a bounded page of their comments."""
    questions = se_get(f"questions/{qid}", site).get("items", [])
    if not questions:
        raise SystemExit(f"Question {qid} not found on {site}.")
    question = questions[0]
    answers = se_get(f"questions/{qid}/answers", site, order="desc", sort="votes",
                     pagesize=str(limit))
    items = answers.get("items", [])
    accepted = question.get("accepted_answer_id")
    if accepted and not any(a.get("answer_id") == accepted for a in items):
        items = se_get(f"answers/{accepted}", site).get("items", []) + items
        items = items[:limit]
    ids = [qid, *(str(a["answer_id"]) for a in items)]
    comments = se_get(f"posts/{';'.join(ids[:100])}/comments", site,
                      order="desc", sort="creation", pagesize="100")
    link = question.get("link", "")
    print(f"# {html.unescape(question.get('title', qid))}\n# {link}\n"
          f"# answers: reported={question.get('answer_count', '?')}, shown={len(items)}\n")
    if answers.get("has_more") or comments.get("has_more"):
        print("# PARTIAL: more answers/comments exist; inspect the original discussion.")
    if len(ids) > 100:
        print("# PARTIAL: comment lookup covers the question and first 99 selected answers.")
    print("## question\n")
    print(clip_text(strip_tags(question.get("body", ""), link), ref_url=link), "\n")
    print("## selected answers (accepted retained; otherwise most-voted)\n")
    for ans in items:
        mark = " ✓accepted" if ans.get("is_accepted") else ""
        print(f"[{ans.get('score')} pts{mark}] "
              f"{clip_text(strip_tags(ans.get('body', ''), link), ref_url=link)}\n")
        print(f"{link}#answer-{ans['answer_id']}\n")
    print("## comments on the question and selected answers (up to 100 recent)\n")
    for comment in reversed(comments.get("items", [])):
        print(f"[{comment.get('score', 0)} pts] "
              f"{clip_text(strip_tags(comment.get('body', ''), link), ref_url=link)}\n"
              f"{link}#comment{comment['comment_id']}_{comment['post_id']}\n")


class TelegramParser(HTMLParser):
    """Keep text, timestamp and permalink attached to the same message div."""

    def __init__(self) -> None:
        super().__init__()
        self.posts: list[dict[str, str]] = []
        self.current: dict[str, str] | None = None
        self.depth = 0
        self.text_depth = 0
        self.text_parser: TextParser | None = None
        self.preview = False
        self.empty = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        classes = (values.get("class") or "").split()
        self.preview |= "tgme_channel_history" in classes
        self.empty |= "tme_no_messages_found" in classes
        if tag == "div" and values.get("data-post"):
            self.current = {"id": values["data-post"] or "", "time": "?", "text": ""}
            self.depth = 0
        if self.current is None:
            return
        if tag == "div":
            self.depth += 1
            if "tgme_widget_message_text" in classes:
                self.text_depth = self.depth
                self.text_parser = TextParser("https://t.me/")
        if self.text_parser is not None:
            self.text_parser.feed(self.get_starttag_text() or "")
        if tag == "time":
            self.current["time"] = values.get("datetime") or "?"

    def handle_endtag(self, tag: str) -> None:
        if self.text_parser is not None:
            self.text_parser.handle_endtag(tag)
        if self.current is None or tag != "div":
            return
        if self.depth == self.text_depth:
            if self.text_parser is not None:
                self.current["text"] = self.text_parser.text()
            self.text_depth = 0
            self.text_parser = None
        self.depth -= 1
        if self.depth == 0:
            self.posts.append(self.current)
            self.current = None

    def handle_data(self, data: str) -> None:
        if self.text_parser is not None:
            self.text_parser.handle_data(data)


def telegram_name(channel: str) -> str:
    """Accept a public channel name or channel URL, including a trailing slash."""
    name = channel.strip().lstrip("@")
    if name.startswith(("t.me/", "www.t.me/")):
        name = "https://" + name
    if "://" in name:
        parsed = urllib.parse.urlsplit(name)
        parts = parsed.path.strip("/").split("/")
        if parts[:1] == ["s"]:
            parts = parts[1:]
        if parsed.hostname not in {"t.me", "www.t.me"} or len(parts) != 1:
            raise SystemExit("Expected a public Telegram channel URL, not a post or invitation.")
        name = parts[0]
    if not re.fullmatch(r"[a-zA-Z0-9_]{1,32}", name):
        raise SystemExit(f"Invalid public Telegram channel: {channel!r}")
    return name


def tg_channel(channel: str, query: str | None, limit: int) -> None:
    """Read a public Telegram channel through its web preview, or search inside it.

    `t.me/s/<channel>` renders posts server-side; `?q=` searches within the
    channel. There is no keyless cross-channel search — for that, use a web
    search restricted to `t.me`.
    """
    name = telegram_name(channel)
    url = f"https://t.me/s/{name}" + (f"?q={urllib.parse.quote(query)}" if query else "")
    page = fetch(url, UA_HTML)
    parser = TelegramParser()
    parser.feed(page)
    parser.close()
    if parser.current is not None or (not parser.posts and not (parser.preview and parser.empty)):
        raise SystemExit(f"No readable public channel preview at {url}. "
                         "The channel may be unavailable, require access, or use changed markup; "
                         "this is not evidence of zero posts. Try a browser or request user help.")
    print(f"# t.me/{name}  q={query or '—'}  -> {len(parser.posts)} preview posts")
    print("# Partial web preview; media and private/group chat content were not read.\n")
    for post in parser.posts[:limit]:
        text = post["text"] if post["text"].strip() else "(no text; media content unverified)"
        when = post["time"][:16].replace("T", " ")
        print(f"[{when}] {text}\nhttps://t.me/{post['id']}\n")


def main() -> None:
    """Dispatch one subcommand."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("command", choices=["reddit-search", "reddit-thread", "hn-search", "hn-thread",
                                        "gh-search", "gh-thread", "gh-repos", "hf-search",
                                        "habr-search", "so-search", "so-thread", "tg-channel",
                                        "yt-transcript", "health"])
    ap.add_argument("target", nargs="?", help="query, URL, ID, channel, or omitted for health")
    ap.add_argument("--sub", default=None)
    ap.add_argument("--limit", type=int, default=25)
    ap.add_argument("--order", default="rating", choices=["rating", "relevance"])
    ap.add_argument("--site", default="ru.stackoverflow", help="Stack Exchange site")
    ap.add_argument("--q", default=None, help="tg-channel: search inside the channel")
    ap.add_argument("--pages", type=int, default=3, help="gh-thread: page budget (1-10)")
    ap.add_argument("--lang", default="auto", help="yt-transcript: auto, ru, en, or language code")
    ap.add_argument("--max-body-chars", type=int, default=4000, help="max chars per comment body")
    ap.add_argument("--timeout", type=int, default=None, help="timeout in seconds (5-60)")
    ap.add_argument("--retries", type=int, default=None, help="total attempts (1-3)")
    args = ap.parse_args()
    if not 1 <= args.limit <= 100 or not 1 <= args.pages <= 10:
        ap.error("--limit must be 1-100 and --pages must be 1-10")
    if (args.timeout is not None and not 5 <= args.timeout <= 60) or (
            args.retries is not None and not 1 <= args.retries <= 3):
        ap.error("--timeout must be 5-60 seconds and --retries must be 1-3")
    if args.max_body_chars != 0 and not 500 <= args.max_body_chars <= 100_000:
        ap.error("--max-body-chars must be 0 (unlimited) or 500-100000")
    if not re.fullmatch(r"auto|[a-zA-Z]{2,3}(?:-[a-zA-Z0-9]+)*", args.lang):
        ap.error("--lang must be auto or a language code such as ru, en, en-US")
    args.target = (args.target or "").strip()
    if args.command != "health" and not args.target:
        ap.error("a non-blank target is required unless command is health")
    global DEFAULT_TIMEOUT, DEFAULT_RETRIES, DEFAULT_MAX_BODY_CHARS
    DEFAULT_TIMEOUT = DEFAULT_TIMEOUT if args.timeout is None else args.timeout
    DEFAULT_RETRIES = DEFAULT_RETRIES if args.retries is None else args.retries
    DEFAULT_MAX_BODY_CHARS = args.max_body_chars
    # Keep the existing command names stable.
    run = {
        "reddit-search": lambda: reddit_search(args.target, args.sub, args.limit),
        "reddit-thread": lambda: reddit_thread(args.target, args.limit),
        "hn-search": lambda: hn_search(args.target, args.limit),
        "hn-thread": lambda: hn_thread(args.target, args.limit),
        "gh-search": lambda: gh_search(args.target, args.limit),
        "gh-thread": lambda: gh_thread(args.target, args.limit, args.pages),
        "gh-repos": lambda: gh_repos(args.target, args.limit),
        "hf-search": lambda: hf_search(args.target, args.limit),
        "habr-search": lambda: habr_search(args.target, args.order, args.limit),
        "so-search": lambda: so_search(args.target, args.site, args.limit),
        "so-thread": lambda: so_thread(args.target, args.site, args.limit),
        "tg-channel": lambda: tg_channel(args.target, args.q, args.limit),
        "yt-transcript": lambda: yt_transcript(args.target, lang=args.lang),
        "health": lambda: health(args.timeout or 12),
    }
    run[args.command]()


if __name__ == "__main__":
    main()
