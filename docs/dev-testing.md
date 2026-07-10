# Real-World Test Deployment

Unit tests mock the Resolve API, so every change that touches Resolve
interaction needs a real-world test before merging: temporarily deploy the
feature branch to a PC or Mac that has DaVinci Resolve installed and footage
drives attached, and run an actual proxy generation job there.

## 1. Install the feature branch on the test machine

```sh
uv tool install --no-managed-python git+https://github.com/geekshootjack/pxygen@<branch>
pxygen --help   # banner should show a 2.x.y.devN+g... version derived from the branch
```

`--no-managed-python` is required: the repo's `python-preference =
"only-system"` only applies inside the project checkout — `uv tool install`
on another machine does not read it and may download a uv-managed Python,
which Resolve's `fusionscript` binding silently fails to connect to (the run
aborts right after "Total folders to process" with no error). The test
machine must have an official python.org build installed; to be explicit,
pass `--python "C:\path\to\python.exe"` instead.

## 2. Pull new commits pushed to the same branch

```sh
uv tool upgrade pxygen   # follows the installed ref (the branch)
```

## 3. Run the test

DaVinci Resolve must be running. For large batches, keep a log to review
afterwards:

```sh
pxygen -i <footage> -o <proxy> --log-level info --log-file pxygen-run.log
```

## 4. After testing: switch back to main, or uninstall

`uv tool upgrade` never switches refs — force-reinstall to change branch:

```sh
uv tool install --force --no-managed-python git+https://github.com/geekshootjack/pxygen
```

Or remove the tool (and its `pxygen` shim) entirely:

```sh
uv tool uninstall pxygen
```
