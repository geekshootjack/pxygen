---
name: test
description: Run the proxy generator against a test folder. Launches DaVinci Resolve if needed, then invokes the script with test data to verify end-to-end behavior.
disable-model-invocation: true
---

The user wants to run an end-to-end test of the proxy generator.

If a test runner script exists (e.g., `test_run.py`, `run_test.sh`, or similar in the repo root or a `tests/` directory), run it.

Otherwise, guide the user through the manual test flow:

1. Ensure DaVinci Resolve is running (or help the user launch it — on macOS: `open -a "DaVinci Resolve"`).
2. Ensure the required environment variables are set (`RESOLVE_SCRIPT_API`, `RESOLVE_SCRIPT_LIB`, `PYTHONPATH` — see README for platform-specific values).
3. Run the script against a test footage folder:
   ```
   python Proxy_generator.py -f <test_footage_folder> -p <test_proxy_output_folder>
   ```
4. Observe the output and verify that:
   - DaVinci Resolve creates the expected bin structure
   - Footage is imported correctly
   - Render jobs are queued with the correct preset
   - Proxy files are generated in the output folder

If $ARGUMENTS specifies a footage folder or proxy folder, use those paths. Otherwise ask the user.

Suggest creating a dedicated test script (`test_run.py`) that automates steps 1–4 so future tests are one command.
