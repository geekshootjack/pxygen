# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

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

## Releases

- Use semantic versioning: `vX.Y.Z`
- Tag each release: `git tag vX.Y.Z && git push origin vX.Y.Z`
- Update the version constant in the script before tagging
