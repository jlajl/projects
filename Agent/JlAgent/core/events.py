from dataclasses import dataclass


@dataclass(frozen=True)
class Thinking:
    content: str


@dataclass(frozen=True)
class AssistantMessage:
    content: str
    final: bool = True


@dataclass(frozen=True)
class ToolCallStarted:
    name: str
    arguments: str


@dataclass(frozen=True)
class ToolCallFinished:
    name: str
    result: str


@dataclass(frozen=True)
class AgentError:
    message: str


AgentEvent = (
    Thinking | AssistantMessage | ToolCallStarted | ToolCallFinished | AgentError
)
