# Memory promotion workflow

Shared knowledge follows an explicit path:

```text
Task memory -> proposed lesson -> independent review -> department/organization memory
```

Only task memory can enter this workflow. A worker cannot directly create verified department or organization knowledge through `PromotionService`. Promotion requires explicit approval by a reviewer other than the source creator, confidence of at least 0.7, non-expired retention, usable provenance and non-sensitive classification. Restricted/confidential content is denied, and constitution-bypass language fails closed.

Exact hashes detect duplicates and return the existing shared record. A different verified record with the same owner, kind and overlapping tags creates a conflict rather than an overwrite. Both sources remain available for review; conflict resolution may select only one of the preserved record IDs as active.

Production adapters should persist proposals, reviews and conflict decisions with audit events and apply organization-specific confidence, sensitivity and constitution rules without weakening these defaults.
