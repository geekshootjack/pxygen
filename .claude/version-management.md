# Version Management — Mental Model

## What is a version number, really?

A version number is a **promise to your users**, not a counter for your commits.

`v2.0.0` means: "this is a stable, intentional snapshot of the project that I'm
willing to stand behind." It's a contract. Commits are drafts; a version is a
published chapter.

---

## Semantic Versioning (semver)

Format: `vMAJOR.MINOR.PATCH`

| Part    | Bump when…                                              | Example trigger                        |
|---------|---------------------------------------------------------|----------------------------------------|
| `PATCH` | you fixed something, nothing new                        | bug fix, typo, internal refactor       |
| `MINOR` | you added something, existing usage still works         | new flag, new feature, new auto-detect |
| `MAJOR` | you broke something that worked before                  | renamed/removed CLI flag, changed output format |

Read it from left to right: "how surprised will my users be when they upgrade?"
- PATCH → not at all
- MINOR → pleasantly
- MAJOR → they need to read the changelog

**The key insight:** MAJOR doesn't mean "big" or "important." It means *breaking*.
A tiny one-line change that removes a flag is MAJOR. A month of work that only
adds new features is MINOR.

---

## Git tags

A git tag is just a **named pointer to a specific commit** — like a bookmark.

```
commit a1b2c3  ← v1.5.2 points here
commit d4e5f6
commit 789abc  ← v2.0.0 points here  ← HEAD
```

Unlike branch names (which move forward with every commit), a tag is frozen.
`v2.0.0` will always mean that exact commit, forever.

### Common commands

```sh
git tag v2.0.0               # tag current commit
git tag v2.0.0 abc1234       # tag a specific past commit
git push origin v2.0.0       # push a single tag to remote
git push origin --tags       # push all local tags to remote
git tag                      # list all tags
git show v2.0.0              # inspect what a tag points to
git tag -d v2.0.0            # delete tag locally
git push origin :v2.0.0      # delete tag from remote (careful)
```

**Important:** `git push` does NOT push tags. You must push them explicitly.
Forgetting this is the #1 gotcha.

---

## How hatch-vcs fits in

Without hatch-vcs: version lives in `pyproject.toml`. You must edit the file,
commit, *then* tag. Two steps, easy to get out of sync.

With hatch-vcs: version is derived from the nearest git tag at build/install
time. `pyproject.toml` just says `dynamic = ["version"]`. You only tag — no
file to edit.

```
git tag v2.1.0
git push origin v2.1.0
# done — pip install will now report 2.1.0
```

Between tags, hatch-vcs generates a dev version automatically:
`2.1.0.dev3+gabc1234` (3 commits after v2.1.0, at commit abc1234).
This is useful: you can always tell whether a running install is a clean release
or a in-between snapshot.

---

## The release workflow (for this project)

1. Work normally — commit to main as usual
2. When you have something worth shipping, decide the version bump
3. Tag and push:
   ```sh
   git tag v2.1.0
   git push && git push origin v2.1.0
   ```
4. On the production machine, pin to the tag:
   ```sh
   pip install git+https://github.com/geekshootjack/pxygen.git@v2.1.0
   ```

---

## When to actually bump

Not every commit. Not even every feature. Ask yourself:

> "If a user re-installs right now, would I want them to get this?"

Yes → release. No → keep going.

Rough heuristics:
- Fixed something that was actively breaking users → PATCH, release soon
- Finished a feature you've been working on → MINOR, release when stable
- Accumulating small stuff → batch them into one MINOR every few weeks
- Just refactoring internals → no release needed, users won't notice

---

## Tips and tricks

**Don't overthink v0 vs v1.**
Some projects stay on `v0.x` to signal "unstable API." Once you're comfortable
that the CLI won't change drastically, go to `v1.0.0`. You crossed that line
already — hence `v2.0.0`.

**Annotated vs lightweight tags.**
`git tag v2.0.0` creates a lightweight tag (just a pointer).
`git tag -a v2.0.0 -m "Initial stable release"` creates an annotated tag (has
its own metadata, author, date, message). GitHub uses annotated tags for
Releases. For a small tool, lightweight is fine until you start writing
changelogs.

**GitHub Releases.**
A git tag + a GitHub Release are two different things. A tag is a git concept.
A GitHub Release is a UI layer on top of a tag — lets you write release notes
and attach binaries. You don't need Releases; they're optional presentation.
`gh release create v2.0.0 --generate-notes` auto-generates notes from commits.

**Changelog discipline (optional but nice).**
If you want users to know what changed, keep a `CHANGELOG.md` updated before
tagging. Format: https://keepachangelog.com. Not required for an internal tool,
but good habit if the project becomes public-facing.

**Never retag.**
If you tag `v2.0.0` and then push more commits to fix something you forgot,
don't delete and re-create the tag. Release `v2.0.1` instead. Retagging breaks
anyone who already pinned to that version.
