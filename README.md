# DigDeep — 2026.10.17-r5

English | [Русский](README.ru.md)

## What it is for

DigDeep is a skill for AI assistants that helps find how others solved a comparable problem, check what their experience actually supports, and choose a sensible next step. It is useful in software, engineering and other fields where you need to understand existing methods, their limits and failed attempts.

It is a set of instructions plus an optional helper script. The assistant searches with the tools of its own host: web search, browser, connected apps and accessible public sources.

Version r5 was tested in Claude Code (Opus 5.5), Codex (Sol), Gemini (Argon 4.6) and Devin (SWE). These were tests on specific tasks, not a guarantee of behavior in every host.

## How it works

1. Clarifies the desired outcome, constraints and what has already been tried.
2. Looks for different ways to solve the problem, similar cases and practical experience.
3. Reads originals, useful links from discussions, objections, corrections and later outcomes.
4. Checks whether the findings are current and under which conditions they apply to your case.
5. Returns a conclusion with links, the uncertainties that matter and a next action or test.

If one tool cannot read a source, the assistant tries another permitted route. Research ends when the agreed task is done or further progress needs a practical test, access or a decision from the user. Complete coverage of the internet is not promised.

Before a new research task the skill notes that it will use the reasoning effort currently selected in the host and waits for a reply such as "continue". Higher settings can increase token use. The skill does not change the setting itself. Additional research agents run only when the user asks for them.

## When it helps and when it is overkill

**Useful** when you need to:

- find existing approaches and the experience of similar projects;
- understand a tool's limits, a defect or why a method was abandoned;
- compare solutions with their versions, conditions and real results;
- break down a talk or lecture, separating supported conclusions from proposals;
- find the next testable step when ordinary search keeps returning the same answers.

**Overkill** for translation, rewording, a simple fact, a known command or a small edit that needs no outside research. For news digests and trend tracking, ordinary search is a better fit.

## Installation

You need a host that supports skills and has tools for reading sources. No particular search service is required.

1. Download `digdeep-2026.10.17-r5.zip` from this repository's **Releases** page and unpack it, or take the `digdeep` folder from the repository itself.
2. When updating, keep the previous `digdeep` folder so you can roll back.
3. Copy the **whole `digdeep` folder** to the chosen location; there must be no extra `digdeep/digdeep` level. To upload through the Claude interface, use the ZIP as is (see below). The README, TODO and `tests` folder are not part of the installed skill.
4. Open a new session and check that the assistant sees the skill and reads version `2026.10.17-r5` from `SKILL.md`.

### Codex, Antigravity App/IDE and Claude Code

| Host | All your projects | One project |
|---|---|---|
| Codex | `~/.agents/skills/digdeep` | `<project>/.agents/skills/digdeep` |
| Antigravity App/IDE | `~/.gemini/config/skills/digdeep` | `<project>/.agents/skills/digdeep` |
| Claude Code | `~/.claude/skills/digdeep` | `<project>/.claude/skills/digdeep` |

On Windows, `~` is `%USERPROFILE%`. Explicit invocation: `$digdeep` in Codex, `/digdeep` in Claude Code and the Antigravity App. The skill can also be selected automatically from its description or when a request mentions `digdeep`. If it does not appear, check the path to `digdeep/SKILL.md` and restart the host or open a new session.

For the Antigravity CLI the user-level path is `~/.gemini/antigravity-cli/skills/digdeep`; the project path is the same, `.agents/skills/digdeep`.

### Claude on the web or Desktop

Under **Customize → Skills** choose **+ → Create skill → Upload a skill**, upload `digdeep-2026.10.17-r5.zip` as is and enable the skill. Skills require **Code execution and file creation** to be enabled; managed accounts follow their organization's settings.

The archive already contains a single `digdeep` folder with `SKILL.md` inside, so there is no need to repack it. Attaching the archive to a chat message does not install the skill. See [Use skills in Claude](https://support.claude.com/en/articles/12512180-use-skills-in-claude) and [How to create custom skills](https://support.claude.com/en/articles/12512198-how-to-create-custom-skills).

### Devin

Add the `digdeep` folder to `.agents/skills/` in a repository Devin can access and commit it. The resulting path is `.agents/skills/digdeep/SKILL.md`. Start the session on the current version of the repository. Explicit invocation: `@skills:digdeep`.

Installation docs: [Codex](https://learn.chatgpt.com/docs/build-skills#where-codex-loads-local-skills), [Antigravity](https://antigravity.google/docs/skills), [Claude Code](https://code.claude.com/docs/en/skills), [Devin](https://docs.devin.ai/product-guides/skills). Checked against the documentation on 17–18 October 2026; a documented installation method does not by itself confirm the skill's behavior in every host.

### Optional helper script

`scripts/sources.py` needs Python 3.12+. It reads some public APIs, feeds and pages; without it the assistant can use its other tools. The skill is not tied to any operating system.

Fetching YouTube captions with the script also needs `yt-dlp`. If you want it, install it into the Python environment of your choice:

```text
python -m pip install --user yt-dlp
```

Nothing is installed automatically. Without `yt-dlp` the assistant can still read captions through a browser or the author's own text.

Without a token, the script's GitHub API calls are limited to 60 per hour per IP address. If you use the [GitHub CLI](https://cli.github.com/) and are signed in, you can set a token for the session and start the assistant from the same terminal:

```bash
export GITHUB_TOKEN="$(gh auth token)"
```

In PowerShell: `$env:GITHUB_TOKEN = (gh auth token)`. The script reads `GITHUB_TOKEN` or `GH_TOKEN` from the environment and sends it only to `api.github.com`. The skill never asks for or stores a token; whether to set one is the user's choice.

## Usage

State the desired outcome, the constraints and what you have already tried. For example:

> Use DigDeep: find practical ways to reduce echo in a small room without major renovation. Compare where each works and its limits. Suggest the next testable step.

To check the installation without starting research:

> Read the installed DigDeep and confirm the version in SKILL.md. Do not start any research yet.

## Limitations

- Results depend on the model, the available tools and access rights. The skill does not guarantee finding an answer, complete coverage or freedom from errors.
- Public APIs, feeds and pages change, rate-limit requests and may return only part of a discussion. Reddit and YouTube caption availability is checked for each item.
- Reddit announced that it will retire RSS feeds on 13 November 2026. The script's `reddit-search` relies on RSS, and `reddit-thread` currently reads threads only through its RSS fallback, so both will probably stop working after that date. The assistant chooses other routes to Reddit on its own.
- In a restricted environment the networked script may need the host's normal access permission. One failed route does not prove a source is unreachable by every route.
- Logins, paywalls, CAPTCHAs and host restrictions are never bypassed. When needed, the assistant asks you to perform a permitted step; it never needs your passwords or exported cookies.
- Someone else's experience or a claimed capability is not a test on your data. Before significant spending or a workflow change, run a suitable practical test.

## For developers

- `tests/test_sources.py` checks the helper script without network access: `python tests/test_sources.py`.
- [TODO.md](TODO.md) lists directions for future versions with their rationale and acceptance criteria (in Russian).

## License

[MIT](LICENSE).
