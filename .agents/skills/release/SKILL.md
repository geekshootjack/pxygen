---
name: release
description: Cut a new release — bump the version constant in the script, commit, tag vX.Y.Z, and push the tag.
disable-model-invocation: true
---

The user wants to cut a new release. Follow these steps:

1. Ask the user for the new version number (e.g., 1.6.0) if not provided in $ARGUMENTS.
2. Find the version constant in `Proxy_generator.py` (search for the current version string like `1.5.2` or a `VERSION` variable) and update it to the new version.
3. Stage the change: `git add Proxy_generator.py`
4. Commit: `git commit -m "X.Y.Z"`
5. Tag: `git tag vX.Y.Z`
6. Ask the user to confirm before pushing: `git push && git push origin vX.Y.Z`

Show the user what you're about to do before each step.
