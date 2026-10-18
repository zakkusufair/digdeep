# Source routes and helper commands

This is an extensible map, not a mandatory call to every host. Select routes by
the question, then explain material gaps. Include all user-requested routes.
No service's search index is complete; use a complementary query/source when
the answer depends on absence.

## Route by question

| Need | Primary evidence | Experience and counterevidence |
|---|---|---|
| Similar complete projects | Repository/code, documentation, runnable examples, architecture write-ups, conference talks/slides | Issues, migrations, postmortems, author channels/blogs, abandoned alternatives with an explicit reason |
| Library/tool choice or defect | Official docs, tests, release notes, issue/PR resolution | Stack Exchange, domain forums, GitHub Discussions, Reddit, HN |
| Model or data choice | Author model/data cards, paper, evaluation code/data; HF when hosted there or useful for alternatives | Model discussions, independent reproductions, inference-engine issues |
| Method/benchmark quality | Original paper/protocol, dataset, baseline and evaluation code | Replications, ablations, peer critique, conference reports, domain expert channels/blogs |
| Russian data or regional practice | Relevant Russian datasets/docs and implementation | Habr/Q&A, ru.stackoverflow, author Telegram channels, vc.ru; also English sources and cross-language results |
| Talk/lecture content | Actual transcript with timestamp; author slides when needed | Related paper/repo, Q&A or follow-up; verify automatic-caption artifacts |
| Non-software question | Original study, standard, official record or domain reference appropriate to the claim | Relevant professional communities and primary accounts, not irrelevant ML/tooling sites |

For high-stakes claims, community anecdotes are leads, not authoritative advice.
Use the relevant primary/official domain evidence.

For an open solution search, compare mechanisms or workflows before brands.
Native features, combinations, manual steps and adjacent disciplines can be
useful directions when relevant; these are examples, not required categories.
An implementation proves only the part and conditions it actually demonstrates.
For a selected tool or a specific lecture, choose routes that answer that narrower
question rather than expanding into an unrelated alternatives catalog.

## Source map

- **GitHub / other forges:** search repositories separately from issues, then
  read code/examples, releases, open and closed issues, Discussions, PRs and
  maintainer replies. Search GitLab, Codeberg, GitFlic or a project's own tracker
  when the project actually lives there. Stars/reaction totals are not approval.
- **Reddit:** original post, relevant replies, objections and later edits.
  Discovery through web/MCP search or RSS; the helper tries old.reddit HTML first
  and automatically falls back to the thread `.rss` feed when HTML returns an
  access/welcome page. The fallback verifies the post ID, keeps the HTML failure
  reason and reports actual displayed comments. A Reddit HTTP 429 pauses further
  Reddit requests rather than immediately switching endpoints. Returned comments
  may omit hidden branches or scores; a feed is explicitly partial coverage.
  Consult the dated access notes below: RSS and Old Reddit are fragile routes.
- **HN / hn.algolia.com:** Ask HN, Show HN and discussions of original work.
  Read the story text as well as comments. HN points do not establish correctness.
- **Stack Exchange:** choose the relevant site, including ru.stackoverflow,
  stackoverflow, stats, datascience, dsp, etc. Read question constraints,
  answers and correction comments. Accepted means selected by the asker, not
  universally correct; an answered question need not have an accepted answer.
- **Hugging Face:** models, datasets, Spaces and discussions. The helper searches
  models only; search the other collections separately when needed. Check
  license, task/language, model revision, evaluation conditions and hardware.
  A library without models does not require an HF search.
- **Papers / original benchmarks:** author sites, arXiv, relevant venue archives
  (ACL Anthology, OpenReview, CVF, etc.), linked data and code. Distinguish
  preprint/peer review and author benchmark/independent reproduction.
- **Habr / qna.habr.com:** technical write-ups and concrete failure reports.
  Read article comments and follow-up links; assess evidence individually.
- **vc.ru / dev.to / engineering blogs:** useful for project accounts and
  architecture; separate advertising and tool lists from work actually done.
  Find exact articles through available web/Tavily/Exa search; do not assume a
  proprietary or undocumented search endpoint exists.
- **Telegram:** discover public channels through web search, project docs or
  author links. The helper reads one public channel preview/search, not private
  groups, full history or media. Cite post permalinks. An invitation is not
  evidence that the chat was read. Do not join/post/contact people automatically.
- **YouTube:** find relevant talks in any useful language, including Russian.
  Match video identity/author, retrieve captions and cite timestamped video URLs.
  Check author slides/repo if the claim depends on visual material.
- **Other domain sources:** Discourse forums, mailing-list archives, specialist
  communities, vendor issue trackers, original incident reports, standards and
  documentation. Follow useful citations outward; do not limit research to the
  hosts for which this helper happens to have a command.

## Search capabilities

Use available search/extraction tools for discovery and relevant domain filters
when helpful; inspect their actual tool schemas, not hardcoded tool names.
Use another index to resolve a gap, not to duplicate every request.
The fallback is available web search + direct official pages/APIs/helper.
Quoted snippets, AI search summaries and partial extracts remain discovery
leads until checked against source content. Never invent successful tool calls.

Some tools accept an information objective separately from keyword queries.
Where supported, a concrete question and varied short queries can guide retrieval
or extraction without forcing all task details into one keyword string. The
objective describes what to find out, including relevant constraints, rather
than assuming the conclusion. Focused extracts can omit context or return only
file metadata; check the actual content needed for the claim.

**Optional service, checked 2026-10-04:**
[Parallel Search MCP](https://docs.parallel.ai/integrations/mcp/search-mcp)
offers search and page extraction at `https://search.parallel.ai/mcp`. The
anonymous endpoint needs no account; rate limits apply and search overrides are
ignored. Its schema separates `objective` and `search_queries`; full-content
extraction can still miss rendered tabs or other representations. Queries and
URLs go to the provider. Use it when available and useful for a gap, preserving
host permissions; availability is not a requirement to install or use it.
Recheck the actual schema and terms when needed. This is one possible route,
not a limit on other tools or methods.

Useful query families, adapted to the topic and language:

- mechanism / task synonyms / adjacent use cases / different workflow;
- a newly found term, author, reference, or the method used after a failure;
- candidate + limitation / bug / failed / rejected / migration / benchmark;
- candidate + current version / release / issue resolution;
- candidate + "не работает" / "отказались" / "ограничения" / "сравнение".

Use short terms for restrictive keyword indexes; broaden to natural-language
queries where supported. Historical failures remain useful but require a current
status check. Count independent origins, not the number of matching domains.

### Conditional ways to widen discovery

Use a route when it addresses a material gap, not as a required checklist.

- **An unexpectedly empty or repetitive query:** if a relevant known example is
  available, check whether the query/index retrieves it. Inspect missing terms,
  metadata coverage and result limits; repair the query or try the relevant
  original corpus. A successful probe does not prove completeness. Avoid tuning
  only to that example. A hard eligibility condition can remain in full-text
  screening even when it is omitted from a query because metadata do not carry it.
- **Unfamiliar terminology:** consult a source's glossary, thesaurus or a useful
  record. Separate synonyms/entry terms from broader, narrower and related terms,
  read their scope, and try the relevant terms in that index's actual syntax.
  Broader terms may expose another method; a shared word can also mean something
  irrelevant. Keep the user's outcome and constraints when screening the findings.
- **A useful seed:** follow its references backward and later citations, forks,
  replies or follow-up work forward as relevant. Choose seeds from different
  mechanisms where possible. Read the linked work; a citation is not replication.
  A connected neighborhood and one citation index do not cover the whole topic.
- **A poorly indexed original corpus:** use its native search or categories before
  another general-index repetition. If an important gap remains in a bounded
  archive/venue/forum, inspect the relevant issue/session/thread list. Record the
  boundaries; manual browsing of the entire internet is not a recovery strategy.
- **An adjacent field with no exact analogue:** identify an intermediate function
  or mechanism B needed for outcome C, then look for a method A that supplies B.
  Check both A -> B and B -> C, including inputs, conditions and failure modes.
  Label the untested connection as a transfer hypothesis; shared terminology or
  a successful component does not establish an end-to-end solution. Compare a
  different intermediate route when the current one keeps repeating itself.

These operations adapt ideas from [search-strategy testing and citation routes,
Cochrane chapter 4](https://www.cochrane.org/authors/handbooks-and-manuals/handbook/current/chapter-04),
[Engineering Village term relations](https://www.elsevier.support/engineering-village/answer/how-can-i-improve-my-thesaurus-search),
[an original-corpus search case](https://discovery.ucl.ac.uk/id/eprint/10094620/1/1-s2.0-S0895435619310637-main.pdf)
and [literature-based discovery](https://pmc.ncbi.nlm.nih.gov/articles/PMC5771422/).
Their domain-specific findings do not measure the benefit of these routes in
DigDeep or guarantee complete coverage.

For evidence with multiple reports, retain additions, corrections and unresolved
conflicts while counting the original experience once; do not discard useful
documents as mere duplicates ([Cochrane chapter 5](https://www.cochrane.org/authors/handbooks-and-manuals/handbook/current/chapter-05)).
For a consequential compound claim, identify which passage supports which part;
combined citations may support it jointly. Textual support still does not prove
truth or local applicability ([ALCE, sections 3.3 and Appendix E](https://aclanthology.org/2023.emnlp-main.398.pdf)).

## Effort notice: dated provider guidance

Checked 2026-10-16: OpenAI lists `medium` as the API default for GPT-6.1 Sol and
as a balanced research starting point. `high` is intended for harder reasoning;
`xhigh` should earn its additional cost through task-relevant evaluations.
This is model-specific orientation, not a minimum, a setting observed in the
current host, or a guarantee of equal research quality. Other models and hosts
can differ. Recheck the provider guidance before presenting it as current:
[GPT-6.1 Sol](https://developers.openai.com/api/docs/models/gpt-6.1-sol) and
[reasoning effort](https://developers.openai.com/api/docs/guides/reasoning#reasoning-effort).
The user chooses the host setting and authorizes continuation as described in
SKILL.md; the skill does not silently change it.

## Known access restrictions

Checked 2026-10-03. These notes describe observed routes and announced changes,
not permanent guarantees. Recheck the relevant official notice and actual content
when using a route in another project, especially after the dates below.

### Execution environment versus source policy

- **Windows permission failure:** `WinError 10013` means a socket operation was
  denied; the message alone does not identify the responsible sandbox, firewall
  or other local policy. In the checked Codex environment, the same read-only
  helper requests failed inside the restricted process but worked in ordinary
  PowerShell and with a host-approved scoped network execution. Diagnose the
  environment before declaring several independent sites blocked. Use the host's
  supported permission mechanism for the exact read-only request when available;
  do not change global sandbox, firewall, VPN or DNS settings as a shortcut.
  A denial must be respected. Claude Code has its own permission mechanisms;
  this symptom does not establish the same cause in a different host.
- **Separate representations:** a browser/app permission error can differ from
  shell restrictions. Test an independently permitted representation, verify
  page identity and needed content, and record which route worked. A signed-in
  session is not automatically available to the helper.
- **HTTP and parsing:** 401/403, 429, timeout/DNS, login content and an empty
  parser are different observations. Respect retry/backoff limits; inspect the
  returned page or another representation before diagnosing a parser defect.
  Neither an HTTP success nor `health: OK` proves the thread was read. Health
  also exits zero when it completes with unavailable routes; read its per-route
  status, then check the actual search or thread required by the task.

### Reddit changes and helper implications

- Reddit announced RSS retirement on **2026-11-13**. For feeds outside communities
  the user moderates, the announcement offers no replacement. The helper's
  `reddit-search` relies on RSS, so treat it as a temporary discovery route and
  recheck after that date. Supported moderation replacements do not establish
  general research access.
- Reddit states that Old Reddit already requires login and plans to restrict
  logged-in access further to users with Old Reddit use in the preceding six
  months; logged-in moderators are exempt from that usage requirement. From
  r3.2, the helper's `reddit-thread` automatically falls back to the thread
  `.rss` feed when old.reddit HTML is blocked or returns a welcome page.
  RSS is a temporary route, not guaranteed access until the announced retirement
  on 2026-11-13. Recheck the notice and the actual route; the date alone does not
  establish whether this helper can read a particular thread.
  Source: [Reddit infrastructure update](https://www.reddit.com/r/modnews/comments/1wubgvt/continuing_our_infrastructure_updates_whats/).
- For the public Data API, Reddit announced no new access requests after
  **2026-10-31**, access removals beginning **2027-01-12** for apps/users that
  have not registered or engaged, and closure of remaining public access in
  **March 2027**. The helper currently uses RSS and HTML, not an authenticated
  Reddit Data API client. Source: [Data API migration timeline](https://www.reddit.com/r/redditdev/comments/1wubcvf/moving_data_api_apps_to_the_developer_platform/).
- Checked 2026-10-13 from Claude Code: the desktop app's built-in browser refuses
  reddit.com ("not allowed due to safety restrictions"), WebFetch and Exa fetch do
  not return Reddit pages, `.json` endpoints returned 403. The helper's RSS
  fallback read both announcements. Search RSS worked intermittently and
  returned 429 under repetition. RSS retirement was announced for November 13;
  this dated observation does not guarantee later access. Other leads seen that day: the
  Arctic Shift archive API (search timed out repeatedly) and third-party snapshot
  pages found by exact title; label such copies and their capture dates.

These changes do not prove that all Reddit material is already unreadable by
every search, browser or authorized connector. Try an applicable permitted route
to the original post, clearly label partial comments or an alternate copy, and
keep unread branches in coverage. Do not auto-register apps, export cookies,
purchase access or change identities to bypass restrictions. Do not disable a
helper command solely by calendar date; verify the current route and notice.

## Helper commands

Prepend python "/absolute/path/to/digdeep/scripts/sources.py" to each command.
Preserve argument quoting, especially paths with spaces and owner/repo#123.
Content commands print UTF-8 and return non-zero on detected failure. A failed
helper command may leave independently permitted browser/API/app/user-assisted
routes available; follow
the access-recovery procedure in SKILL.md. `health` reports each route separately
and exits successfully when the diagnostic completes, even with unavailable routes.

~~~text
reddit-search "<query>" [--sub NAME] [--limit N]
reddit-thread "<permalink>" [--limit N] [--max-body-chars N]
hn-search "<query>" [--limit N]
hn-thread <story-id> [--limit N] [--max-body-chars N]
gh-search "<query>" [--limit N]
gh-thread "<issue-url or owner/repo#123>" [--limit N] [--pages N] [--max-body-chars N]
gh-repos "<query>" [--limit N]
hf-search "<query>" [--limit N]
habr-search "<query>" [--order rating|relevance] [--limit N]
so-search "<query>" [--site NAME] [--limit N]
so-thread <question-id> [--site NAME] [--limit N] [--max-body-chars N]
tg-channel <channel> [--q "<query>"] [--limit N]
yt-transcript "<video-url or id>" [--lang auto|ru|en|CODE]
health [--timeout N]
~~~

--limit: 1-100 (default 25). Stack Exchange defaults to ru.stackoverflow;
choose another site explicitly. gh-thread --pages: 1-10 (default 3), 100
comments/page. If the budget cannot cover a thread, it includes the last page
to retain recent replies. Within fetched comments, selection reserves the latest,
then first reply, the most recent substantive issue-author reply and the most
positively rated reply, in that order when the limit is tight. Remaining slots
prefer substantive maintainer replies, then other ranked replies. Output returns
to chronological order. PARTIAL distinguishes not-fetched comments from fetched
but unshown comments and gives the maximum size of the latter; missing pages
and omitted bodies may still hold deciding evidence. --max-body-chars defaults
to 4000 retained characters per root post, comment or answer (opening 65% and
closing 35%, plus an explicit truncation marker). This limits one oversized body,
not total stdout; host truncation can still occur. Pass `--max-body-chars 0` for
unclipped bodies or read the linked item directly. Avoid chaining multiple thread
commands in one shell call. If `GITHUB_TOKEN` or `GH_TOKEN` is already set in the host environment,
GitHub API calls include it automatically. Authenticated redirects stay at their
original HTTPS origin; all redirects retain HTTPS. Otherwise unauthenticated calls share
GitHub's 60 req/hr IP quota and report `X-RateLimit-Reset` when exhausted.
PR review comments and GitHub Discussions are separate resources, not included.
HTML readers preserve code indentation and HTTP(S) link destinations; relative
links are resolved against the source. They are text views, not full DOM/media
captures. Habr/Reddit search reject non-feed responses. Telegram accepts names,
@names and channel URLs with or without a trailing slash; a post/invite URL is
not a channel. An unrecognized preview fails; an explicit empty-search page may
return zero posts. Use browser/app routes for content the helper cannot read.
HN thread output is also bounded by --limit and labels omitted comments. The SO
reader keeps the accepted answer in its answer budget and retrieves up to 100
recent comments across the question and selected answers, not every comment in
a large discussion. Public endpoints have quotas and can change.

--timeout sets each helper request to 5-60 seconds (default 30); --retries sets
1-3 total attempts, including the first (default 3). YouTube forwards these
settings to yt-dlp (retries = attempts minus one); each of its two subprocess
stages also has a total wall-clock budget of timeout times attempts. Thus
--timeout 5 --retries 1 allows at most 5 seconds per YouTube stage. `health`
needs no target, uses one attempt per route and a 12-second timeout by default.
It tests reachability only: OK does not validate parsing or full source access.
An unavailable helper route should trigger another applicable route, not gate
all research on health. No diagnostic establishes source completeness.

--lang auto prefers the video's original language when metadata identifies it;
otherwise it chooses a non-translated track when available and labels origin
unknown. Explicit ru/en requests may select an available automatic translation,
which is labeled; a missing language is an error, not an English substitution.
A bare language code such as en accepts regional variants. An explicit tag such
as en-US requires that variant (case-insensitive); en-GB cannot replace it.
The helper downloads one subtitle track, no media, and ignores ambient yt-dlp
configuration. Cookies/proxy settings in that configuration are therefore not
inherited. yt-dlp is optional. The helper tries the current Python environment,
`yt-dlp` on PATH and the default interpreter selected by each available standard
launcher (`py`, `python3`, `python`). It does not enumerate every Python or virtual
environment. Each candidate must pass a local `--version` probe (up to 3 seconds);
a failed launch or probe continues to the next candidate. At most five candidate
probes add up to 15 seconds before caption stages; the selected command is cached
within the process. If none works, install only with user permission:
python -m pip install --user yt-dlp.
If the helper fails, use the browser transcript, author-provided text/captions,
or another lawfully accessible caption source, identifying provenance and gaps.
Let the user complete a required login/CAPTCHA in their browser, then reread.
Do not export credentials or treat a search snippet/description as the transcript.
Consult [yt-dlp subtitle options](https://github.com/yt-dlp/yt-dlp#subtitle-options)
and [EJS requirements](https://github.com/yt-dlp/yt-dlp/wiki/EJS) when a concrete
error points there. Do not promise access to restricted/private videos.
