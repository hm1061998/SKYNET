"""Work Order pause, cancellation and approval application services."""
from __future__ import annotations

from core.domain import TaskStatus, WorkOrderStatus

from .states import TaskStateMachine, WorkOrderStateMachine


class CancellationService:
    """Cancel a Work Order and propagate cancellation to non-terminal Tasks."""

    def __init__(self, work_orders, tasks, task_states: TaskStateMachine | None = None,
                 work_order_states: WorkOrderStateMachine | None = None) -> None:
        self.work_orders = work_orders
        self.tasks = tasks
        self.task_states = task_states or TaskStateMachine()
        self.work_order_states = work_order_states or WorkOrderStateMachine()

    def cancel(self, work_order_id: str, actor_id: str):
        work_order = self.work_orders.get(work_order_id)
        terminal = {TaskStatus.COMPLETED, TaskStatus.CANCELLED}
        for task in self.tasks.list():
            if task.work_order_id == work_order_id and task.status not in terminal:
                changed = self.task_states.transition(task, TaskStatus.CANCELLED, actor_id)
                self.tasks.save(changed, task.version)
        changed = self.work_order_states.transition(work_order, WorkOrderStatus.CANCELLED, actor_id)
        self.work_orders.save(changed, work_order.version)
        return changed


class WorkOrderControlService:
    """Pause, resume and record approval without direct status assignment."""

    def __init__(self, work_orders, states: WorkOrderStateMachine | None = None) -> None:
        self.work_orders = work_orders
        self.states = states or WorkOrderStateMachine()

    def pause(self, work_order_id: str, actor_id: str):
        work_order = self.work_orders.get(work_order_id)
        changed = self.states.transition(work_order, WorkOrderStatus.PAUSED, actor_id)
        self.work_orders.save(changed, work_order.version)
        return changed

    def resume(self, work_order_id: str, actor_id: str):
        work_order = self.work_orders.get(work_order_id)
        changed = self.states.transition(work_order, WorkOrderStatus.IN_PROGRESS, actor_id)
        self.work_orders.save(changed, work_order.version)
        return changed

    def approve(self, work_order_id: str, actor_id: str):
        work_order = self.work_orders.get(work_order_id)
        changed = self.states.transition(work_order, WorkOrderStatus.APPROVED, actor_id,
                                         approval_granted=True)
        self.work_orders.save(changed, work_order.version)
        return changed
