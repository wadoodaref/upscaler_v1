# General Rules — Read First (v7)

These rules apply to any project that contains this file. This is the rules
file: it is complete and self-contained, and is the same file in every project
that carries it. Read it in full.

**§8, locating an external source on a machine that doesn't have it where the
docs say**, exists because a session on a second PC found the recorded source
path pointing at a drive that no longer existed, and, separately, because a
project memory in a *different* project was found still directing sessions to a
specific drive letter months after that drive was gone — while the real,
updated source sat unnoticed on another drive on the same machine. Both
incidents are one instance of the same general failure mode that section
addresses, not evidence specific to either project; see §8 itself for the rule
in project-agnostic form.

---

## 0. Pull before touching anything

**At the very start of every session, before reading code or making any
edit:** run `git fetch origin` and bring the local branch fully up to date
with the remote (`git pull`, or the merge/rebase the repo's history already
uses) — not just once, but again immediately before every `git push`, since
more than one session/AI instance may be working in this same working
directory across the session's lifetime.

- **Why:** this repo has been worked on by more than one AI session in the
  same physical folder at overlapping times. A session that reads `chat.md`
  or `git log` once at startup and then trusts that view for the rest of a
  long session can silently drift behind — new commits land from elsewhere,
  session numbering in `chat.md`/`HANDOFF_CONTINUATION_PROMPT.md` moves on,
  and a stale local view risks either a lost/overwritten fix or a confusing
  merge conflict at push time.
- **How to apply:** treat `git log --oneline -5` / `git fetch && git status`
  as a cheap, routine check — run it again before every commit+push, not
  only at session start, especially in a long session. If the remote has
  moved, re-read the new tail of `chat.md` before appending your own entry,
  and pick the next session number after whatever is actually on disk now,
  not whatever number you last remembered.

## 1. Logging rules

Maintain a **sequential, append-only chat log** (e.g. `chat.md`).

- Each entry records: the user's request, what was changed (files), decisions/rationale, verification result, and the git commit hash.
- Newest entries are appended at the **bottom** (not top).
- One coherent change = one article + one commit + one push. **Do not batch** multiple changes into one log entry.

## 2. Commit & push rules

After **each** meaningful change:

1. Append a dated article to the log file.
2. Run `git diff --check` (no whitespace errors).
3. Review `git status` and the final diff.
4. **Fetch/pull first** (see §0) — confirm the local branch is still even with `origin` before committing on top of it.
5. **Regenerate this machine's `GITIGNORED_FILES_<MACHINE_ID>.md`** (see §9) — create it if it does not exist yet on this machine, overwrite it if it does. Every push is the trigger; do not defer this to "whenever it's needed" or skip it because the change felt small — a gitignored file changed by definition every time a build ran or a fetch wrote data, whether or not this push's own diff shows it.
6. Create **one focused commit** — do not combine unrelated work.
7. Push that commit to the remote (`git push origin main`) and confirm it succeeded.
7. Do **not** leave completed changes undocumented or uncommitted.

## 3. Development workflow sequence

Before starting any change:

1. **Pull first** (§0).
2. Read the latest entries in the chat log and any handoff/continuation document.
3. Consult the schema/documentation before changing data models.
4. Choose the target explicitly (e.g. front-end, back-end, shared core).
5. Implement and verify the **smallest relevant target** first.
6. When shared code changes, build the **entire solution** before committing.
7. Each phase must build cleanly, validate on disposable copies, update the log, commit, and push **before the next phase begins**.

## 4. Build & verify

- Build must pass with **zero warnings and zero errors** before committing.
- Run integration or smoke tests where applicable.
- For database migrations: test on a **disposable copy first** before applying to the real database.
- Keep a verified backup before destructive operations.
- Prefer `run.ps1` (see §6) over ad-hoc `dotnet build`/`dotnet run` invocations when verifying a change end-to-end — it is the one script proven to reproduce the project's actual startup path.

## 5. Code conventions

- Mimic existing code style, libraries, and patterns.
- Never assume a library is available — check `package.json`, `.csproj`, or equivalent first.
- Follow security best practices.

## 6. Starting a new project — required files

When beginning any new coding project, **immediately create** these files in the repo root:

| File | Purpose |
|---|---|
| This rules file (whichever version is current) | The AI reads this first before any work |
| `chat.md` | Sequential, append-only session log (one article per change) |
| `PROJECT_PLAN.md` or `ROADMAP.md` | Phases, status, acceptance criteria |
| `HANDOFF_CONTINUATION_PROMPT.md` | Authoritative current state summary — updated after each session so another AI can continue seamlessly |
| `run.ps1` | **The project's single start point.** One PowerShell command that takes a clean checkout to a running app — see rules below. |

### `run.ps1` rules

- `run.ps1` is created **at project start**, before or alongside the first real feature — not deferred to a "packaging" phase. It is the start point of the project, not a distribution afterthought.
- It must, with no required arguments: build the project (skippable via a `-NoBuild` switch) and then launch it (the app, the dev server, or the test suite, whichever "running the project" means for that project type), auto-detecting the toolchain it needs rather than assuming the operator has it configured.
- It is the **canonical** way to build and run the project. `README.md`/`HANDOFF_CONTINUATION_PROMPT.md` build/run instructions should point to it first, with raw `dotnet`/`npm`/etc. commands kept only as the detail it wraps.
- When project structure changes in a way that breaks it (renamed project, new startup argument, new required dependency), fixing `run.ps1` is part of that same change, not a follow-up — a stale start point is worse than none, because it fails silently trusted.
- Keep it idempotent and safe to re-run: re-running on an already-set-up machine should just build and launch, not repeat expensive first-time setup.

Rules:
- The AI **must read this file** (whichever version is current) immediately when added to a project.
- `chat.md` entries are appended at the **bottom** (newest last).
- One coherent change = one `chat.md` entry + one commit + one push — never batch unrelated work.
- Before each session, the AI pulls (§0), then reads `chat.md` (tail) and `HANDOFF_CONTINUATION_PROMPT.md` to learn current state.
- After each session, update `HANDOFF_CONTINUATION_PROMPT.md` with the authoritative status so the next AI can pick up without re-reading the entire chat log.

## 7. `interrupted.md` — mid-conversation handoff

`interrupted.md` is a special-purpose file, distinct from `chat.md` and
`HANDOFF_CONTINUATION_PROMPT.md`:

- **It is written only by the user**, never by an AI. The user pastes in the raw
  tail of a conversation that got cut off mid-task (e.g. a coding assistant hit a
  usage limit, crashed, or was otherwise interrupted before finishing and logging
  its work) — typically a request statement followed by a raw tool-call/action
  transcript, ending wherever the interruption happened. It is not curated or
  reformatted; treat it as a rough, literal snapshot, not a polished handoff doc.
- **Any AI starting work in this repo must check `interrupted.md` first**, before
  or alongside the normal `chat.md`-tail / `HANDOFF_CONTINUATION_PROMPT.md` read in
  §3 — if it has content, that content describes the most recent, possibly
  incomplete, in-progress state, more current than `chat.md`'s last entry. Read it
  to understand exactly what was being attempted and how far it got (which files
  were touched, what was mid-edit, where the transcript stops) before writing any
  new code.
- **Finish what it describes** — reconcile the working tree against what the
  transcript claims was done (e.g. new files that exist but aren't yet wired up,
  a half-applied diff, missing handler methods a XAML edit expects to find),
  verify the result actually builds/works, and only then treat that thread of
  work as closed.
- **Once those actions are completed and verified, erase the file's *content*
  but do not delete the file itself.** Leave `interrupted.md` present but empty,
  ready for the user to paste the next interrupted transcript into. Deleting the
  file (as happened once in this repo's history, before this rule existed, on the
  mistaken belief it was leftover debris from a different project) removes the
  handoff channel entirely; erasing-in-place preserves it for reuse.
- Log the fact that `interrupted.md` was read and acted on in the normal
  `chat.md` entry for that change, the same as any other change — `interrupted.md`
  being emptied afterward means the log entry is the only surviving record of
  what it contained.

## 8. Source / reference material — locate it per machine, never assume a path

*(Added 2026-09-07 at the user's direct instruction: "in each PC attached to
repo, if source cannot be found search for it at main drives or ask user."
Two sessions implemented this independently on the same day, in different
repos; this section is the merge of both.)*

Some projects are built *against* something that is not in the repo — a
reference application to decompile or diff, an SDK, a bundled data root, a large
asset tree, a database dump. A path to that material is a fact about **the
machine you are on right now**, never a fact about the repo. The same repository
is worked on from more than one PC, drive letters differ between them and get
re-lettered or removed, and installs get moved. A path written in a doc, a plan,
a code constant, a previous session's summary, `chat.md`, or your own memory is
a hint about one machine at one moment — it is evidence only when you have just
checked it.

**Before using source material, in this order:**

1. **Verify it is actually there.** Test the specific file, not the folder.
2. **If it is missing, try the other recorded paths** — this project's docs, the
   tool's own constants, any per-machine list it keeps.
3. **Then search this machine's drives before concluding anything is missing.**
   Look for the thing by its recognisable shape — the install folder name, a
   known inner file. **Bound the search**: a shallow, targeted scan of the fixed
   drives takes a second or two, while a full recursive walk from every drive
   root takes minutes and has timed out sessions before. Widen it only if the
   bounded scan fails. For example, scanning for an install root rather than
   recursing blindly:

   ```powershell
   Get-PSDrive -PSProvider FileSystem | ForEach-Object {
       Get-ChildItem -Path $_.Root -Directory -Filter 'shamela*' -ErrorAction SilentlyContinue
   } | ForEach-Object { Join-Path $_.FullName 'app\win\64\bin' }
   ```

   Substitute the folder/file that actually identifies the thing you need.
4. **If the search finds nothing, ask the user directly.** Say what you looked
   for and where. Do **not** infer a location from history, do **not** substitute
   a different install or an older copy, and do **not** proceed by guessing.
   Never carry on against a stale local copy — work diffed against the wrong
   source is worse than no work, because it looks finished. Above all, **never
   produce a result presented as coming from source material you could not
   actually read.**
5. **If the search finds more than one candidate, ask — do not auto-pick.**
   Report each with whatever really distinguishes them: the version read *out of
   the artifact itself*, not the folder name; modification date; bitness. Paths
   and timestamps are not evidence of which is current.

**Beware copies belonging to other projects.** Sibling projects on the same box
vendor their own inventory of the same application, often at an *older* version.
Those are read-only context for their own project and are **never** this
project's source; exclude them explicitly by path, never write into them, and do
not even open them once identified.

**When you do locate it:**

- Record it as *"on this machine, as of `<date>`"* — never as "the project's
  path". A bare drive letter identifies nothing on its own. Put it in the
  project's handoff document and in the locating tool's known-paths list,
  labelled with which PC it belongs to.
- **Correct the stale entry that sent you looking**, in the same change, so the
  next session on this PC does not repeat the search.
- **Never hardcode it in shipped code.** Parameterize it — an environment
  variable with a documented, explicitly machine-specific default — per §5 and
  the standing "never depend on the reference install at runtime" rule.

**Prefer a tool over prose.** The locating logic belongs in the script that
needs the source, runnable with no arguments, so every entry point resolves it
the same way and the rule cannot be forgotten. Where a project has one, use it
rather than typing a path. (In `shamela4_rebuild_v1` that is
`build_scripts/extract_source_pyc.py`, which implements exactly the order above,
reads the version out of each candidate, and refuses to choose between
ambiguous ones.)

**Why this is a rule and not a note:** it has already gone wrong. A standing
instruction named one drive as "the source of truth on this machine"; by
2026-09-07 that exact path did not exist on the machine reading it, while a
perfectly good install sat on another drive. Separately, a drive scan on that
machine turned up four installs of the same app — two of them belonging to a
different project and pinned at the *previous* version, i.e. exactly the
baseline being diffed against. A recorded path silently became misinformation,
and an unchecked "newest looking" pick would have produced a confident, empty,
wrong result.

## 9. Per-machine local-state manifests

*(Added 2026-09-07 at the user's direct instruction, immediately after §8:
"another file .md, gitignored with the pc id (for each pc) with gitignored
files and their size should be created".)*

Some facts about a repo's working tree are real, useful, and **genuinely
per-machine** — they should not be forced into a single shared file that two
clones would just fight over. **This is not a one-time, one-machine task**:
every PC this repo is cloned on generates and maintains its *own* copy of
this file, independently, under its own hostname. A session on PC A does not
create PC B's file, and finding only PC A's file present is not evidence
PC B is done or current — it means PC B's own session hasn't (yet) run this
on PC B.

**What large/gitignored content actually exists on this machine, and how big
it is.** Build output, downloaded/generated data files, caches, backups —
anything gitignored on purpose (large, regenerable) is also, by that same
fact, invisible to another clone without asking. Generate
`GITIGNORED_FILES_<MACHINE_ID>.md` (machine id = hostname, e.g.
`$env:COMPUTERNAME` on Windows) listing every gitignored path with its size
(directories as one aggregated row, not file-by-file). This file is itself
gitignored (see `.gitignore`'s `GITIGNORED_FILES_*.md` pattern) — never
hand-edit or commit it. Per §2 step 5, regenerate (or create, if this
machine has never had one) this file with **every** push, not just when the
gap is noticed.

**A committed, cross-machine-comparable completeness snapshot is a separate,
project-specific idea, not part of this generic rule.** Whether such a file
makes sense — and what it should be named/shaped — depends entirely on
whether *the project you're in* has its own gitignored source-of-truth data
worth comparing across clones. If it does, that convention belongs in that
project's own `PROJECT_PLAN.md`/`HANDOFF_CONTINUATION_PROMPT.md`, not in
this file. Do not assume a project using this same rules file has an
equivalent, and do not invent one unprompted — check that project's own
docs first.

**How to apply:** when a fact is genuinely local to the machine you're on
(what's actually on disk, not what the repo's history says should be),
prefer a small generated file over trying to encode it in `chat.md` or
`HANDOFF_CONTINUATION_PROMPT.md` prose — and decide deliberately whether that
file should be gitignored (pure local trivia) or committed (meant to be
diffed across clones), rather than defaulting to one or the other.

---

## Additions only - they do not replace the rules above

This section is additive documentation. It does not change, override, weaken, or
remove any rule in §0-§9 above, which remain authoritative.

### Framework and source-path inventory

At the start of work, record verified paths in the PC-specific ignored manifest,
not in shared project rules. Identify the project's framework and source files from
the files that actually exist in that project:

- .NET: `*.sln`, `*.csproj`, `global.json`, `Directory.Build.*`
- Node.js: `package.json`, workspace configuration, and lockfile
- Python: `pyproject.toml`, `requirements*.txt`, and lockfile
- Java: `pom.xml` or `build.gradle*`
- Flutter/Dart: `pubspec.yaml` and `pubspec.lock`
- Rust: `Cargo.toml` and `Cargo.lock`

Common source locations are `src/`, `app/`, or the repository root. Common test
locations are `tests/`, `test/`, and `spec/`. Common utility and documentation
locations are `tools/`, `scripts/`, `build/`, `docs/`, `assets/`, `resources/`,
and `public/`. These are conventions only; verify the actual project structure.

Record installed SDK/compiler/interpreter paths, model paths, caches, and generated
output in `GITIGNORED_FILES_<MACHINE_ID>.md` for that PC. Do not hardcode a path from
one PC into shared source or assume that a framework installed for another project is
available here.
