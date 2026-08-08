# Phase 1 Step 11: Desktop Execution Contract Ratification

## 1. Status and Scope

Phase 1 Step 11 is a documentation-only architecture ratification for Issue #12.

The existing `run_curation(request)` boundary remains synchronous and framework-neutral. This step introduces no application thread, asynchronous runtime abstraction, production Python change, test change, dependency change, PySide6 dependency, or GUI implementation.

This document defines the desktop execution contract that Phase 2A will consume. It does not imply that background execution or a Qt execution controller already exists.

## 2. Repository Evidence

The verified Step 11 baseline is `main` at commit `19c040c122e169bfa06ea16798244f7268065b0b`, synchronized with `origin/main` and with a clean working tree.

Current repository evidence establishes that:

- the CLI constructs `CurationRunRequest` and calls `run_curation(request)`;
- `run_curation()` delegates synchronously to `CurationRunService.run()`;
- each run constructs a fresh `ImageCurationPipeline`;
- pipeline construction creates a fresh `VisionAnalyzer`;
- `VisionAnalyzer` initialization may initialize Torch and OpenCLIP resources;
- image discovery, fingerprinting, analysis, selection, writing, and manifest construction are synchronous;
- repeated same-process calls with unchanged input are tested for equal results and manifests;
- `CurationRunRequest`, `CurationRunResult`, and `RunManifest` are immutable application contracts;
- PySide6 is not a current dependency.

These facts support retaining the existing synchronous application boundary and assigning desktop execution ownership to the future presentation adapter.

## 3. Existing Canonical Execution Path

The canonical execution path is:

```text
Presentation layer
    -> CurationRunRequest
    -> run_curation(request)
    -> CurationRunService.run(request)
    -> CurationRunResult

```

The CLI already uses this path. Future desktop execution must use the same path and must not duplicate discovery, analysis, duplicate detection, integrity generation, ranking, export, or manifest orchestration.

## 4. Synchronous Application Contract

`run_curation(request)` and `CurationRunService.run(request)` remain synchronous.

The contract is:

- no thread is created by the application layer;
- no executor, callback, future, queue, scheduler, task handle, or worker pool is exposed;
- the call returns only after the run reaches terminal success;
- terminal success returns `CurationRunResult`;
- run-level failure raises the original application exception;
- the caller selects and owns the execution context.

The CLI may continue calling `run_curation()` synchronously on its current thread.

## 5. Desktop UI-Thread Blocking Risk

A future desktop application must not call `run_curation()` on the Qt GUI thread.

A run may synchronously perform:

- Torch device inspection;
- OpenCLIP model and transform construction;
- pretrained model loading;
- tokenizer and prompt-feature initialization;
- recursive image discovery;
- file hashing;
- image decoding and technical analysis;
- optional model inference;
- artifact writing;
- deterministic manifest construction.

This blocking risk justifies worker execution in the future Qt presentation layer. It does not justify adding thread ownership to the application service.

## 6. Caller-Owned Execution Context

Execution-context ownership belongs to the presentation layer.

```text
CLI
    -> calls run_curation() synchronously on the CLI thread

Future Qt presentation adapter
    -> owns worker execution
    -> calls run_curation() from a non-GUI thread
    -> returns completion through Qt-native queued delivery

```

Thread ownership must remain outside `CurationRunService`, `run_curation`, `ImageCurationPipeline`, and `VisionAnalyzer`.

## 7. CurationRunRequest Boundary

The future Qt controller must transfer the existing immutable `CurationRunRequest` unchanged across the worker boundary.

```text
Qt GUI thread
    -> constructs CurationRunRequest

Qt-owned worker thread
    -> receives the same request object
    -> passes it to run_curation(request)

```

The contract does not approve:

- a GUI-specific request DTO;
- a second configuration model;
- same-process request serialization;
- mutable shared request state;
- reconstruction of application orchestration in the GUI.

## 8. CurationRunResult and RunManifest Boundary

Successful execution returns the existing immutable `CurationRunResult` unchanged.

The attached deterministic `RunManifest` remains part of that result. The future Qt controller must not introduce a GUI-specific result DTO, a separate manifest transport, or a second result-retrieval path.

```text
Success
    -> CurationRunResult
        -> attached RunManifest

```

## 9. Exception Preservation and Factual Failure Presentation

The future Qt controller may retain and emit the original exception object for same-process technical handling.

The technical contract preserves:

- the exception type;
- the exception message;
- exception chaining and cause;
- diagnostic value;
- technical logging and inspection capability.

The GUI may derive concise, factual user-facing text from that exception. It must not replace the underlying exception with an untyped generic error solely for transport or presentation.

```text
Technical handling
    -> original exception object

User-facing presentation
    -> factual text derived from the same failure

```

For example, a `NotADirectoryError` may be presented as an unavailable input directory while the original exception remains available for logging and technical inspection.

## 10. Structured Analysis, Fingerprint, Duplicate, and Integrity Outcomes

Not every unsuccessful asset operation is a failed run. Image-analysis failures remain available through the `failed_analysis_paths` field on `CurationRunResult`. Existing distinctions remain authoritative:

```text
Run-level operational failure
    -> original exception

Image-analysis failure
    -> CurationRunResult.failed_analysis_paths

Fingerprint failure
    -> ExactDuplicateReport.failed_paths

Exact duplicate facts
    -> ExactDuplicateReport

Integrity facts
    -> IntegrityReport

```

The future GUI must preserve these structured outcomes. It must not reinterpret factual duplicate or integrity reporting as editorial judgment, critique, gating, or generic execution failure.

## 11. One-Active-Run Policy

GUI v1 supports exactly zero or one active run.

The future Qt controller enforces this presentation policy by rejecting or disabling a second start while one run is active. The application service must not gain a busy flag, global lock, scheduler, run registry, worker pool, or concurrent-run coordinator.

A new run may begin only after terminal completion and deterministic cleanup of the previous worker.

## 12. Logging Ownership

Logging configuration remains presentation-owned.

Application, pipeline, analysis, duplicate-detection, and manifest modules may emit log records. The CLI retains its current logging configuration behavior. A future GUI may configure its own handlers and factual presentation without changing application execution.

Step 11 introduces no GUI logging view or application-level logging reconfiguration.

## 13. Rejected Generic Background-Adapter Alternative

A GUI-neutral background adapter was considered and rejected.

Such an adapter would require speculative decisions about:

- thread or executor ownership;
- persistent versus per-run lifetime;
- executor shutdown;
- callbacks, futures, queues, polling, or task handles;
- one-active-run synchronization;
- callback execution context;
- active-presentation shutdown;
- abandoned result delivery.

Most importantly, generic asynchronous completion would not automatically arrive on the Qt GUI thread. PySide6 would still require another asynchronous translation layer:

```text
Generic asynchronous completion
    -> Qt translation layer
    -> Qt queued delivery
    -> GUI-thread receiver
    -> widget update

```

Because the proposed adapter could not be consumed directly by PySide6 without that translation layer, it is not approved.

## 14. Accepted Qt-Owned Execution-Controller Decision

Actual asynchronous ownership first appears in the concrete Qt execution controller in Phase 2A.

That controller will own and test the Qt-specific concerns together:

- worker-thread ownership;
- Qt object affinity;
- Qt-native queued completion delivery;
- GUI-thread presentation updates;
- one-active-run state;
- deterministic worker cleanup;
- active-run window-close handling.

The controller must call the existing `run_curation(request)` boundary and must not create a second orchestration path.

## 15. Deterministic Worker-Cleanup Requirements

The future Phase 2A Qt controller must satisfy all of the following requirements:

1. The controller explicitly owns its worker thread or Qt-native worker mechanism.
2. Terminal success is delivered exactly once.
3. Terminal failure is delivered exactly once.
4. Terminal completion is marshalled to the Qt GUI thread.
5. The original result or exception remains available through completion handling.
6. Worker cleanup follows terminal delivery.
7. The controller returns to idle only after cleanup completes.
8. A new run cannot begin before cleanup completes.
9. Thread-owned objects are not destroyed while execution or queued completion remains possible.
10. Forced thread termination is prohibited.

## 16. Active-Run Window-Close Requirements

Cancellation is deferred, so GUI v1 must use a conservative close policy:

- closing proceeds normally when no run is active;
- final close is rejected or deferred when a run is active;
- the active run is allowed to complete;
- completion receivers remain alive;
- terminal completion is delivered safely;
- the worker is cleaned up deterministically;
- closing may proceed after cleanup;
- forced worker-thread termination is prohibited.

This section defines a Phase 2A requirement and does not implement window behavior in Step 11.

## 17. Phase 2A Entry Gate

Phase 2A may begin only after this contract is accepted and merged through the normal project process.

The concrete Qt controller must:

1. invoke `run_curation()` outside the Qt GUI thread;
2. use Qt-native queued completion delivery;
3. preserve the unchanged `CurationRunRequest`;
4. preserve the unchanged `CurationRunResult` and attached `RunManifest`;
5. retain and emit the original exception object for technical handling;
6. support factual user-facing failure presentation without erasing the underlying exception;
7. enforce one active run;
8. emit terminal success or failure exactly once;
9. clean up its worker deterministically;
10. return to idle only after cleanup;
11. reject or defer active-run close until cleanup is safe;
12. preserve existing CLI behavior;
13. introduce no second orchestration path.

PySide6 may first appear when Phase 2A implements and tests that concrete Qt consumer.

## 18. Deferred Work

The following are explicitly deferred:

- PySide6;
- GUI shell implementation;
- widgets and layouts;
- Qt execution-controller implementation;
- thumbnails and image previews;
- progress reporting and percentages;
- progress callbacks or event contracts;
- cancellation and cancellation tokens;
- forced thread termination;
- concurrent runs;
- worker pools;
- generic executors;
- callback frameworks;
- future wrappers;
- queues and schedulers;
- persistent model lifecycle;
- model reuse;
- cache integration;
- packaging and installers;
- signing and notarization;
- Windows packaging;
- GUI artifact navigation;
- GUI log views;
- rubric integration;
- critique integration;
- gating;
- editorial decisions.

## 19. Acceptance Criteria

Step 11 is accepted only when all of the following are true:

- [ ] This document exists at `docs/architecture/desktop-execution-contract.md`.
- [ ] No other repository file changes.
- [ ] `run_curation()` is documented as synchronous and framework-neutral.
- [ ] `CurationRunService.run()` remains synchronous.
- [ ] Caller-owned execution context is explicit.
- [ ] Future worker ownership is assigned to the Qt controller.
- [ ] `CurationRunRequest` crosses the worker boundary unchanged.
- [ ] `CurationRunResult` returns unchanged on success.
- [ ] `RunManifest` remains attached to the result.
- [ ] The original exception object remains available for same-process technical handling.
- [ ] User-facing failure text is factual and derived from the underlying exception.
- [ ] No untyped generic error replaces the original exception.
- [ ] Structured analysis and fingerprint failures remain result facts.
- [ ] Duplicate and integrity reporting remains factual.
- [ ] GUI v1 permits at most one active run.
- [ ] Deterministic cleanup requirements are documented.
- [ ] Active-run window-close requirements are documented.
- [ ] Progress and cancellation remain deferred.
- [ ] Logging configuration remains presentation-owned.
- [ ] No generic asynchronous adapter is introduced.
- [ ] No production Python code changes.
- [ ] No test-code changes.
- [ ] No dependency changes.
- [ ] No PySide6 dependency.
- [ ] No GUI or Qt controller implementation.
- [ ] No executor, callback framework, future wrapper, queue, scheduler, or worker pool.
- [ ] No CLI behavior or manifest schema change.
- [ ] The existing test suite passes unchanged.

## 20. Validation Requirements

When this documentation-only change is implemented in the repository, run:

```bash
git status --short --branch
git diff --name-only
git diff --stat
git diff --check
git diff -- docs/architecture/desktop-execution-contract.md
python -m pytest -q tests

```

Verify that no Qt dependency was introduced:

```bash
grep -nE 'PySide6|PyQt|QtPy|qasync' \
  requirements.txt requirements-dev.txt setup.py

```

No matches are expected. A nonzero `grep` exit status caused solely by no matches is acceptable.

Verify that protected files remain unchanged:

```bash
git diff -- \
  eas/application.py \
  eas/eas_curate.py \
  eas/pipeline.py \
  eas/vision.py \
  eas/run_manifest.py \
  eas/cache.py \
  eas/extractor.py \
  eas/clustering.py \
  requirements.txt \
  requirements-dev.txt \
  setup.py \
  tests \
  docs/magnum_informed_rubric.yaml \
  docs/rubric_schema.md \
  docs/rubric_versioning.md

```

The expected output is empty. The only changed path must be:

```text
docs/architecture/desktop-execution-contract.md

```

### Final Ratification

The existing synchronous `run_curation(request)` boundary is already the correct framework-neutral desktop execution contract.

A generic background adapter would introduce speculative executor lifecycle and completion semantics, while still requiring a separate Qt-specific translation layer for GUI-thread delivery, object affinity, deterministic cleanup, and window-close behavior. It is therefore not approved.

No production Python change is justified for Step 11.

Actual asynchronous ownership should first appear in the Qt execution controller in Phase 2A, where thread affinity, queued completion delivery, one-active-run enforcement, deterministic cleanup, and window-close behavior can be implemented and tested together against the real consuming framework.
