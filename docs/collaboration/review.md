# Artifact review and governed decisions

Review is performed against an exact `ArtifactVersion` and content hash. `ArtifactReviewService` rejects self-review, versions that do not belong to the artifact, stale requested hashes, assignment mismatches and result hashes that differ from the request. An approval is current only while the artifact's current hash equals the reviewed hash; a new version therefore invalidates the old approval by default.

Review findings use bounded decisions, severities and categories. Each finding records its location, description and required action. Review records may be stored in the dedicated `review_records` repository.

`EvaluatorOptimizerLoop` constrains producer/reviewer revision with maximum rounds, a severity threshold, an escalation target and token/cost/wall-time caps. Approval completes the loop. Significant change requests permit another round only while all bounds allow it. Rejection, exhausted rounds or exceeded budget escalates. Low-severity findings below the configured threshold stop without another automatic revision.

`HighRiskCommittee` is available only for high or critical risk. Each unique member receives an independent context package and submits a sealed structured recommendation. Recommendations are revealed only after every member submits. Only the configured role or human may finalize, and recommendations disagreeing with the final decision remain in the dissent record.

These controls do not grant deployment, messaging, deletion, secret access or other external authority. Such actions still require the applicable policy and human approval.
