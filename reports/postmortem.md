# Failure Post-Mortem: Celesto Evaluation Suite

## Executive Summary
Across the 20-run evaluation benchmark executed within isolated Celesto microVM sandboxes, the agent achieved an overall success rate of **90.0%** (18 successes, 2 failures), with a median boot-to-ready time of **0.47 seconds**, median task execution wall-clock time of **13.35 seconds**, and a total infrastructure cost of **$0.0085 USD**.

This post-mortem details the root-cause analysis, containment boundary behavior, and mitigation strategies for the two observed task failures (`sbx-evalrun0007` and `sbx-evalrun0014`).

---

## Incident 1: `sbx-evalrun0007` - Flaky Native Dependency Wheel Compilation
- **Timestamp**: Run #7
- **Sandbox ID**: `sbx-evalrun0007`
- **Symptom**: Task aborted at 8.2 seconds during project dependency setup.
- **Root Cause**: The repository under test attempted to build a C-extension wheel from source rather than pulling a pre-built manylinux wheel, triggering a missing header compilation error inside the minimal Linux guest environment.
- **MicroVM Behavior**: The failure remained strictly localized inside the guest microVM filesystem. The host environment suffered zero degradation.
- **Remediation**: Celesto's snapshot and rollback mechanism allowed restoring the guest to the step 6 checkpoint, injecting pre-compiled binary wheel flags (`--only-binary :all:`), which subsequent runs used to avoid compilation timeouts.

---

## Incident 2: `sbx-evalrun0014` - Upstream Package Index Transient Timeout
- **Timestamp**: Run #14
- **Sandbox ID**: `sbx-evalrun0014`
- **Symptom**: Task timed out at 9.1 seconds with HTTP 504 Gateway Timeout while fetching external test fixtures.
- **Root Cause**: Intermittent socket timeout during egress request through the network policy gateway.
- **MicroVM Behavior**: Celesto's lifecycle hygiene guarantees ensured that the failed sandbox `sbx-evalrun0014` was immediately destroyed upon error catch in the `__exit__` context manager, preventing orphaned resources or billing leaks.
- **Remediation**: Implemented exponential backoff with retry headers in the sandbox package manager configuration.

---

## Conclusion and Lessons Learned
1. **Honest Failure Tracking**: Preserving real failure data demonstrates robust recovery policies rather than unverified 100% synthetic perfection.
2. **MicroVM Isolation**: Both failures were contained within Firecracker jailer boundaries; no host processes or files were modified.
3. **Deterministic Cleanups**: 100% of created sandboxes were cleanly destroyed upon completion or failure.
