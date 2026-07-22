# software_feature_delivery_v1

The MVP workflow contains eight dependency-ordered stages: intake, product specification, technical design, implementation, code review, QA, security/release review, and final approval/delivery. QA and security both depend on the stable code-review candidate and converge at final delivery.

Revision limits are product specification 2, technical design 2, code review 3 and QA defect repair 3. Critical security findings block release until resolved or a governed human exception exists. Production-like external actions remain simulated.

The deterministic offline scenario adds a health-check command to a sample project. It creates the prescribed product, architecture, implementation, review, QA, security, release and delivery artifacts. The first patch deliberately lacks an exit-code test, causing one structured changes-requested outcome. Developer produces version 2 of the same patch artifact; review, QA and security reference that exact hash.

Without simulated human approval, final delivery is blocked and no final-report artifact is emitted. With approval, the Chief of Staff creates `delivery/final-report.md` containing delivery summary, candidate hash, revision count, zero-provider-cost usage, trace and approval summary. No external service or real project is touched.
