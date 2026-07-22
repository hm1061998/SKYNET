# Phase 07 implementation report

## 1. Summary of implementation

Phase 07 adds layered organizational memory, explicit knowledge promotion and conflict handling, permission-aware bounded retrieval, immutable versioned artifact stores, reference-based context assembly and a read-only legacy JSONL adapter.

## 2. Architecture decisions

- New organizational knowledge is isolated in `core.knowledge`; legacy `Memory` remains unchanged.
- Every memory record requires provenance, validation, sensitivity, retention and a matching content hash.
- Workers produce task memory; shared promotion requires independent review.
- Conflicts create separate records and preserve both candidates rather than overwriting.
- Retrieval filters authorization and sensitivity before relevance scoring.
- Artifact filesystem paths are generated from IDs; display names are metadata only.
- Large artifacts enter context as bounded chunks with original hash/provenance.

## 3. Files created

- `core/knowledge/__init__.py`
- `core/knowledge/memory.py`
- `core/knowledge/retrieval.py`
- `core/knowledge/artifacts.py`
- `core/knowledge/context.py`
- `core/knowledge/legacy.py`
- `tests/knowledge/__init__.py`
- `tests/knowledge/test_knowledge.py`
- `docs/memory/memory-model.md`
- `docs/memory/promotion.md`
- `docs/artifacts/artifact-model.md`
- `docs/implementation/phase-07-report.md`

## 4. Files modified

No existing runtime or legacy memory source file was modified.

## 5. Commands executed

- `python -m unittest discover -s tests/knowledge -v`
- `python -m unittest discover -s tests -v`
- `python -m compileall -q core tests`
- `$env:PYTHONIOENCODING='utf-8'; $env:JAVIS_EXECUTION_MODE='legacy_unsafe'; python selftest.py`
- Git status, diff, staged-diff and whitespace checks before commit.

## 6. Test results

- Phase 07 knowledge/artifact suite: 8/8 passed.
- Full unit suite: 74 passed, 1 skipped. The existing Windows symlink-permission test from Phase 06 remains skipped.
- Python compilation: passed.
- Legacy self-test in explicit compatibility mode: 41 passed, 2 pre-existing failures (legacy `parameters` normalization and `cv2`/`opencv-python` expectation).

## 7. Compatibility impact

Legacy conversation and facts JSONL remain readable through the existing adapter. The compatibility test snapshots the facts file and verifies recall causes no rewrite. No old memory file is migrated or deleted. Existing domain artifacts and review APIs remain unchanged; the richer artifact store is additive.

## 8. Security impact

- Namespace, owner permission, sensitivity, confidence and retention filters run before retrieval.
- Individual workers cannot directly promote task observations into shared verified memory.
- Confidential/restricted and expired records fail shared promotion.
- Contradictions cannot silently replace validated knowledge.
- Artifact hashes are verified on every read and filesystem paths are constrained to the configured store.
- Atomic writes avoid exposing partially written artifact versions.
- Model-provided display names never become local paths.

## 9. Known limitations

- The organizational `MemoryStore` is in-memory; durable query adapters and audited promotion persistence remain future work.
- Lexical retrieval is intentionally simple; the embedding port has no default vector implementation.
- Constitution compatibility uses a conservative built-in injection/bypass check and needs a richer policy adapter later.
- Local artifact store metadata is in process memory; a restart-safe catalog/object-store adapter is not included.
- Text context assembly uses UTF-8 replacement decoding; binary-specific summarizers are future adapters.

## 10. Recommended next phase

Add durable knowledge/artifact catalogs and connect validated retrieval and promotion to the governed scheduler in the next prescribed phase. Phase 07 stops here as required.
