# Artifact model and stores

Artifacts are immutable, versioned outputs. `ArtifactVersionRecord` captures artifact/version IDs, SHA-256, producer, source task, optional parent artifact, MIME and artifact type, storage location, review and approval states, provenance, UTC creation time, sensitivity, display metadata and byte size.

`InMemoryArtifactStore` supports deterministic offline tests. `LocalFileArtifactStore` creates storage paths only from generated artifact/version IDs; display names remain metadata and cannot influence paths. Writes use a temporary file, flush and `fsync`, then atomic `os.replace`. Reads re-hash bytes and fail if content differs from the recorded immutable hash. Resolved paths must remain under the configured store.

Corrections always create a new version. They never modify prior version metadata or bytes. Object storage can implement the `ArtifactStore` port with equivalent conditional/atomic writes and hash verification.

`ReferenceContextAssembler` accepts explicit memory and artifact references. Large artifacts are decoded into bounded chunks and marked summarized while retaining the original authoritative hash and provenance. The original artifact remains the source of truth.
