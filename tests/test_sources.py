"""Offline checks of scripts/sources.py (no network). Run: python tests/test_sources.py [path/to/sources.py]

Covers comment-body clipping, GitHub comment selection, HTTP error classification,
the HTTPS/same-origin redirect guard and --max-body-chars validation.
"""
import email.message
import importlib.util
import io
import pathlib
import subprocess
import sys
import urllib.error
import urllib.request

DEFAULT = pathlib.Path(__file__).resolve().parent.parent / "digdeep" / "scripts" / "sources.py"
path = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT
spec = importlib.util.spec_from_file_location("sources", path)
src = importlib.util.module_from_spec(spec)
spec.loader.exec_module(src)
fails = []


def check(name, cond, info=""):
    print(("ok  " if cond else "FAIL") + f" {name} {info}")
    if not cond:
        fails.append(name)


# clip_text: keeps 65 % head and 35 % tail with an explicit marker
t = "A" * 3000 + "B" * 3000
c = src.clip_text(t, "https://x/1")
check("clip: short text untouched", src.clip_text("abc") == "abc")
check("clip: limit 0 means unlimited", src.clip_text(t, limit=0) == t)
check("clip: head is 2600 chars", c.startswith("A" * 2600) and not c.startswith("A" * 2601))
check("clip: tail is 1400 chars", c.endswith("B" * 1400) and not c.endswith("B" * 1401))
check("clip: marker counts 2000 omitted chars and links the item",
      "[truncated 2000 chars" in c and "inspect https://x/1" in c)
check("clip: text at exactly the limit untouched", src.clip_text("x" * 4000) == "x" * 4000)


# select_gh_comments: latest, first, substantive issue-author reply, top +1, then maintainers
def cm(i, user, assoc="NONE", plus=0, body="short"):
    return {"id": i, "created_at": f"2026-01-{i:02d}", "user": {"login": user},
            "author_association": assoc, "reactions": {"+1": plus}, "body": body}


long = "x" * 100
cs = [cm(1, "first"), cm(2, "op", body=long), cm(3, "m", "MEMBER", body=long),
      cm(4, "fan", plus=9), cm(5, "op", body="ok"), cm(6, "z"), cm(7, "last")]
sel = [x["id"] for x in src.select_gh_comments(cs, 4, "op")]
check("gh: limit 4 keeps latest, first, author, top +1", sel == [1, 2, 4, 7], str(sel))
sel = [x["id"] for x in src.select_gh_comments(cs, 5, "op")]
check("gh: limit 5 adds the substantive maintainer reply", sel == [1, 2, 3, 4, 7], str(sel))
sel = [x["id"] for x in src.select_gh_comments(cs, 100, "op")]
check("gh: output is chronological", sel == [1, 2, 3, 4, 5, 6, 7], str(sel))


# http_error_detail: (detail, retry delay or None)
def herr(code, **hdr):
    m = email.message.Message()
    for k, v in hdr.items():
        m[k.replace("_", "-")] = v
    return urllib.error.HTTPError("https://api.github.com/x", code, "m", m, io.BytesIO(b"err"))


u = "https://api.github.com/x"
r = src.http_error_detail(herr(403, X_RateLimit_Remaining="0", X_RateLimit_Reset="123"), u)
check("http: exhausted GitHub quota stops and reports reset", r[1] is None and "Reset=123" in r[0], str(r))
check("http: plain 403 is not retried", src.http_error_detail(herr(403), u)[1] is None)
check("http: 429 with Retry-After 5 waits 5 s", src.http_error_detail(herr(429, Retry_After="5"), u)[1] == 5.0)
check("http: Retry-After above 30 s stops", src.http_error_detail(herr(429, Retry_After="120"), u)[1] is None)
check("http: 503 is retried", src.http_error_detail(herr(503), u)[1] == 0.0)

# HTTPSRedirectHandler: HTTPS only; an Authorization header never leaves its origin
h = src.HTTPSRedirectHandler()


class FP:
    def close(self):
        pass


def redir(url, new, auth):
    req = urllib.request.Request(url, headers={"Authorization": "Bearer t"} if auth else {})
    try:
        h.redirect_request(req, FP(), 302, "Found", {}, new)
        return "followed"
    except SystemExit as e:
        return str(e)


check("redirect: to http is refused", "non-https" in redir("https://a.com/x", "http://a.com/y", False))
check("redirect: authenticated cross-origin is refused",
      "cross-origin" in redir("https://api.github.com/x", "https://evil.example/", True))
check("redirect: authenticated same origin is followed",
      redir("https://api.github.com/x", "https://api.github.com/y", True) == "followed")
check("redirect: explicit :443 counts as the same origin",
      redir("https://api.github.com/x", "https://api.github.com:443/y", True) == "followed")
check("redirect: unauthenticated cross-origin is followed",
      redir("https://a.com/x", "https://b.com/y", False) == "followed")

# --max-body-chars bounds. An invalid --lang is checked afterwards, so its error proves the value passed
# validation without any network call.
for val, ok in (("0", True), ("500", True), ("499", False), ("100001", False)):
    p = subprocess.run([sys.executable, "-I", str(path), "hn-thread", "1", "--max-body-chars", val, "--lang", "!"],
                       capture_output=True, text=True, encoding="utf-8")
    passed = "--lang must be" in p.stderr
    rejected = "--max-body-chars must be" in p.stderr
    check(f"args: --max-body-chars {val} {'accepted' if ok else 'rejected'}",
          passed if ok else rejected, p.stderr.strip()[-80:])

print("FAILED:", fails if fails else "none")
sys.exit(1 if fails else 0)
