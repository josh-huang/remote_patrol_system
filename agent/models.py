from django.conf import settings
from django.db import models

from core.models import TimeStampedModel


class AgentConversation(TimeStampedModel):
    """A chat session between an operator and the patrol AI agent."""

    title = models.CharField(max_length=160, default="New conversation")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="agent_conversations",
    )

    def __str__(self) -> str:
        return f"#{self.pk} {self.title}"


class AgentMessage(TimeStampedModel):
    """One turn in a conversation.

    `steps` captures the agent's tool-calling trace (which tools it invoked,
    with what arguments and results) so the reasoning is fully transparent and
    auditable — a key part of making the agent the trustworthy "brain".
    """

    class Role(models.TextChoices):
        USER = "user", "User"
        ASSISTANT = "assistant", "Assistant"
        SYSTEM = "system", "System"

    conversation = models.ForeignKey(
        AgentConversation, on_delete=models.CASCADE, related_name="messages"
    )
    role = models.CharField(max_length=16, choices=Role.choices)
    content = models.TextField(blank=True)
    steps = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"{self.role}: {self.content[:50]}"


class AgentAction(TimeStampedModel):
    """A state-changing action the agent proposes.

    Write operations are never executed directly by the agent. They are queued
    here as PENDING and require an operator to confirm (human-in-the-loop
    governance). Autonomous actions (e.g. auto-dispatch on a critical incident)
    are also recorded here.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending Confirmation"
        CONFIRMED = "confirmed", "Confirmed & Executed"
        REJECTED = "rejected", "Rejected"
        FAILED = "failed", "Failed"

    class Origin(models.TextChoices):
        CHAT = "chat", "Chat request"
        AUTONOMOUS = "autonomous", "Autonomous trigger"

    conversation = models.ForeignKey(
        AgentConversation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="actions",
    )
    message = models.ForeignKey(
        AgentMessage,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="actions",
    )
    origin = models.CharField(
        max_length=16, choices=Origin.choices, default=Origin.CHAT
    )
    tool_name = models.CharField(max_length=64)
    arguments = models.JSONField(default=dict)
    summary = models.CharField(max_length=280, blank=True)
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.PENDING
    )
    result = models.JSONField(default=dict, blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="resolved_agent_actions",
    )
    resolved_at = models.DateTimeField(null=True, blank=True)

    def __str__(self) -> str:
        return f"{self.tool_name} [{self.status}]"
