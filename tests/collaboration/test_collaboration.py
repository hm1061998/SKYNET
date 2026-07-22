from dataclasses import replace
from datetime import datetime, timedelta, timezone
import unittest

from core.agents import AgentRegistry
from core.collaboration import (
    ArtifactReviewService, CollaborationError, CollaborationLog, CollaborationMessage,
    CollaborationPatterns, ContentTrust, ContextPackageBuilder, DelegationService,
    EvaluatorOptimizerLoop, HandoffService, HandoffStatus, HighRiskCommittee,
    MessageFactory, MessageType, ProvenanceRecord, RevisionState, Visibility,
)
from core.domain import (
    AgentDefinition, AgentKind, Artifact, ArtifactType, ArtifactVersion, BudgetUsage,
    RiskLevel, SequenceIdGenerator,
)
from core.repositories import InMemoryRepositories


NOW = datetime(2026, 7, 22, 12, 0, tzinfo=timezone.utc)


class FixedClock:
    def now(self):
        return NOW


def agent(agent_id, kind, delegates=()):
    return AgentDefinition(agent_id, agent_id, kind, agent_id, delegates_to=delegates)


def context(ids=None, max_chars=2000, max_tokens=500):
    return ContextPackageBuilder(max_chars, max_tokens, FixedClock(), ids or SequenceIdGenerator()).build(
        organization_id="org", work_order_id="wo", task_id="task",
        goal_summary="Ship safely", current_task="Implement review",
        provenance=(ProvenanceRecord("goal", "goal-1", "sha256:goal"),),
    )


def artifact():
    version = ArtifactVersion("av-1", "artifact-1", 1, "sha256:one", "memory://one", NOW)
    return Artifact("artifact-1", "result", ArtifactType.REPORT, "author", "task",
                    "sha256:one", NOW, (version,)), version


class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.factory = MessageFactory(FixedClock(), SequenceIdGenerator())

    def test_all_message_payload_schemas_and_round_trip(self):
        payloads = {
            MessageType.DELEGATION: {"worker_definition_id": "worker", "child_task_id": "child",
                "deliverables": ["code"], "budget_allocation": {}, "deadline": NOW.isoformat(),
                "context_package_id": "ctx", "return_contract": {}},
            MessageType.HANDOFF: {"reason": "specialty", "receiving_role": "security",
                "context_package_id": "ctx", "unresolved_obligations": [], "remaining_budget": {},
                "required_approval": True, "accepted": None, "rejection_reason": None},
            MessageType.REVIEW_REQUEST: {"artifact_id": "a", "artifact_version_id": "v",
                "artifact_hash": "h", "review_checklist": ["safe"], "acceptance_criteria": ["pass"],
                "severity_model": ["high"], "required_reviewer_role": "reviewer", "author_agent": "a1"},
            MessageType.REVIEW_RESULT: {"decision": "approved", "findings": [],
                "summary": "ok", "reviewed_artifact_hash": "h"},
            MessageType.QUESTION: {"question": "Ready?"},
            MessageType.ANSWER: {"answer": "Yes"},
            MessageType.STATUS: {"status": "active", "summary": "working"},
            MessageType.ESCALATION: {"reason": "risk", "target": "human", "required_action": "decide"},
        }
        for kind, payload in payloads.items():
            message = self.factory.create(organization_id="org", work_order_id="wo", task_id="task",
                type=kind, from_agent="a", to_agent="b", payload=payload)
            self.assertEqual(CollaborationMessage.from_dict(message.to_dict()), message)

    def test_invalid_payload_and_self_message_are_rejected(self):
        with self.assertRaises(CollaborationError):
            self.factory.create(organization_id="org", work_order_id="wo", task_id="task",
                type=MessageType.QUESTION, from_agent="a", to_agent="a", payload={"question": "x"})
        with self.assertRaises(CollaborationError):
            self.factory.create(organization_id="org", work_order_id="wo", task_id="task",
                type=MessageType.STATUS, from_agent="a", to_agent="b", payload={"status": "x"})

    def test_organizational_messages_use_separate_repository_and_audit(self):
        repos = InMemoryRepositories()
        events = []
        message = self.factory.create(organization_id="org", work_order_id="wo", task_id="task",
            type=MessageType.QUESTION, from_agent="a", to_agent="b", payload={"question": "why"})
        CollaborationLog(repos.collaboration_messages, events.append, FixedClock(),
                         SequenceIdGenerator()).append(message)
        self.assertEqual(repos.collaboration_messages.get(message.id), message)
        self.assertEqual(events[0].event_type, "collaboration.message.created")
        self.assertFalse(hasattr(repos, "memory_messages"))

    def test_sequential_causation_and_parallel_isolation(self):
        patterns = CollaborationPatterns(self.factory)
        chain = patterns.sequential(organization_id="org", work_order_id="wo", task_id="task",
            agents=("a", "b", "c"), payloads=({"status": "one", "summary": "1"},
                                                {"status": "two", "summary": "2"}))
        self.assertEqual(chain[1].causation_id, chain[0].message_id)
        self.assertEqual(chain[0].correlation_id, chain[1].correlation_id)
        parallel = patterns.parallel(organization_id="org", work_order_id="wo", task_id="task",
            manager="manager", specialists=("security", "qa"), payload={"question": "assess"})
        self.assertEqual(parallel[0].correlation_id, parallel[1].correlation_id)
        self.assertNotEqual(parallel[0].to_agent, parallel[1].to_agent)
        self.assertIsNone(parallel[0].causation_id)


class CoordinationTests(unittest.TestCase):
    def setUp(self):
        self.registry = AgentRegistry((agent("manager-def", AgentKind.ROLE, ("worker-def",)),
                                       agent("worker-def", AgentKind.WORKER),
                                       agent("other-def", AgentKind.WORKER)))

    def test_authorized_delegation_keeps_manager_accountable(self):
        service = DelegationService(self.registry, clock=FixedClock(), ids=SequenceIdGenerator())
        record, message = service.delegate(organization_id="org", work_order_id="wo", task_id="task",
            child_task_id="child", delegator_definition_id="manager-def", delegator_agent_id="manager",
            worker_definition_id="worker-def", worker_agent_id="worker", deliverables=("code",),
            budget_allocation=BudgetUsage(100, 1, 10), deadline=NOW + timedelta(hours=1),
            context=context(), return_contract={"schema": "artifact"})
        self.assertEqual(record.accountable_agent_id, "manager")
        self.assertEqual(message.type, MessageType.DELEGATION)

    def test_unauthorized_delegation_is_denied(self):
        service = DelegationService(self.registry, clock=FixedClock(), ids=SequenceIdGenerator())
        with self.assertRaises(CollaborationError):
            service.delegate(organization_id="org", work_order_id="wo", task_id="task",
                child_task_id="child", delegator_definition_id="manager-def", delegator_agent_id="manager",
                worker_definition_id="other-def", worker_agent_id="other", deliverables=("code",),
                budget_allocation=BudgetUsage(), deadline=NOW + timedelta(hours=1),
                context=context(), return_contract={})

    def test_handoff_acceptance_and_rejection(self):
        service = HandoffService(FixedClock(), SequenceIdGenerator())
        pending = service.initiate("task", "manager", "specialist", "specialty")
        self.assertEqual(pending.accountable_agent_id, "manager")
        accepted = service.accept(pending, "specialist")
        self.assertEqual((accepted.status, accepted.accountable_agent_id),
                         (HandoffStatus.ACCEPTED, "specialist"))
        rejected = service.reject(service.initiate("task", "manager", "reviewer", "review"),
                                  "reviewer", "capacity")
        self.assertEqual((rejected.status, rejected.accountable_agent_id),
                         (HandoffStatus.REJECTED, "manager"))


class ContextTests(unittest.TestCase):
    def test_context_is_deterministically_bounded_and_keeps_provenance(self):
        provenance = (ProvenanceRecord("artifact", "a-1", "sha256:x"),)
        builder = ContextPackageBuilder(900, 225, FixedClock(), SequenceIdGenerator())
        kwargs = dict(organization_id="org", work_order_id="wo", task_id="task",
            goal_summary="g" * 300, current_task="t" * 300,
            memory_excerpts=("m" * 500, "n" * 500), provenance=provenance)
        first = builder.build(**kwargs)
        second = ContextPackageBuilder(900, 225, FixedClock(), SequenceIdGenerator()).build(**kwargs)
        self.assertTrue(first.truncated)
        self.assertLessEqual(first.serialized_size(), 900)
        self.assertEqual(first.provenance, provenance)
        self.assertEqual(first.to_dict(), second.to_dict())


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.service = ArtifactReviewService(FixedClock(), SequenceIdGenerator())
        self.artifact, self.version = artifact()

    def test_self_review_is_forbidden(self):
        with self.assertRaises(CollaborationError):
            self.service.request(self.artifact, self.version, author_agent_id="author",
                reviewer_agent_id="author", reviewer_role="reviewer", checklist=("safe",),
                acceptance_criteria=("pass",))

    def test_hash_mismatch_and_new_version_invalidate_approval(self):
        request = self.service.request(self.artifact, self.version, author_agent_id="author",
            reviewer_agent_id="reviewer", reviewer_role="reviewer", checklist=("safe",),
            acceptance_criteria=("pass",))
        with self.assertRaises(CollaborationError):
            self.service.submit(request, "reviewer", {"decision": "approved", "findings": [],
                "summary": "ok", "reviewed_artifact_hash": "wrong"})
        record = self.service.submit(request, "reviewer", {"decision": "approved", "findings": [],
            "summary": "ok", "reviewed_artifact_hash": "sha256:one"})
        self.assertTrue(self.service.approval_is_current(record, self.artifact))
        changed = replace(self.artifact, content_hash="sha256:two", version=2)
        self.assertFalse(self.service.approval_is_current(record, changed))

    def test_bounded_revision_and_escalation(self):
        request = self.service.request(self.artifact, self.version, author_agent_id="author",
            reviewer_agent_id="reviewer", reviewer_role="reviewer", checklist=("safe",),
            acceptance_criteria=("pass",))
        finding = {"severity": "high", "category": "security", "location": "x",
                   "description": "risk", "required_action": "fix"}
        record = self.service.submit(request, "reviewer", {"decision": "changes_requested",
            "findings": [finding], "summary": "fix", "reviewed_artifact_hash": "sha256:one"})
        loop = EvaluatorOptimizerLoop(max_rounds=2, severity_threshold="medium",
            escalation_target="human", budget_cap=BudgetUsage(100, 10, 100))
        self.assertEqual(loop.evaluate(record, BudgetUsage(10, 1, 1)).state,
                         RevisionState.REVISION_REQUIRED)
        outcome = loop.evaluate(record, BudgetUsage(10, 1, 1))
        self.assertEqual((outcome.state, outcome.escalation_target),
                         (RevisionState.ESCALATED, "human"))

    def test_committee_seals_votes_and_preserves_dissent(self):
        committee = HighRiskCommittee(RiskLevel.HIGH, ("security", "quality"), "owner")
        committee.submit("security", "reject", "unsafe")
        with self.assertRaises(CollaborationError):
            committee.reveal()
        committee.submit("quality", "approve", "tests pass")
        decision = committee.finalize("owner", "approve")
        self.assertEqual(decision.dissent[0].member_id, "security")


if __name__ == "__main__":
    unittest.main()
