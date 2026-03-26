# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## Project

Python script that automates footage import and proxy generation in DaVinci Resolve. The project is under active refactoring — avoid cementing implementation details; prefer configurable/extensible patterns.

## Requirements

- Python 3 >=3.6, **64-bit only** (DaVinci Resolve scripting API requires 64-bit Python)
- DaVinci Resolve >=19.1.4 must be running before executing the script
- Required environment variables (platform-specific paths — see README):
  - `RESOLVE_SCRIPT_API`
  - `RESOLVE_SCRIPT_LIB`
  - `PYTHONPATH`

## Commit Style

Use [Conventional Commits](https://www.conventionalcommits.org/): `type(scope): description`
Common types: `feat`, `fix`, `chore`, `refactor`, `test`, `docs`

## Commit Workflow

- After each completed, verified modification batch, create a git commit by default without waiting for an extra user reminder.
- Use small, reversible commits so problematic changes can be reverted cleanly.
- Only hold off on committing when the user explicitly asks not to commit yet, or when the work is still in a broken/unverified intermediate state.
- Do not push unless the user asks for a push.

## Releases

- Use semantic versioning: `vX.Y.Z`
- Tag each release: `git tag vX.Y.Z && git push origin vX.Y.Z`
- Update the version constant in the script before tagging
