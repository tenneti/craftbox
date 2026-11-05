"""Optional AI adapter interface for future use (ChatGPT, Gemini, Venice). CB1 makes NO network calls.

Design rules the future implementations must follow:
- Adapters are OFF by default and cannot be enabled by CB1 code; they raise ``AdapterDisabled``.
- An adapter returns a *proposal* in an existing versioned schema. Proposals are validated like any
  manual input and are never applied automatically: they enter the normal experiment lifecycle as a new
  draft that a person reviews, and approved work is never rewritten.
- Credentials come from environment variables only and are never stored, logged or put in the database.
- Paid or network use needs an estimate and an explicit confirmation step in the UI before anything is sent.
The always-available ``local-rules`` adapter wraps the deterministic planner so the same interface works today.
"""


class AdapterDisabled(RuntimeError):
    pass


class Adapter:
    name = "adapter"
    label = "Adapter"
    network = False
    enabled = False
    tasks = ("screenplay.suggest_beats", "direction.suggest_shots")
    env_key = None

    def status(self):
        return {"name": self.name, "label": self.label, "enabled": self.enabled, "network_calls": self.network,
                "tasks": list(self.tasks), "credential_env_var": self.env_key,
                "state": "available" if self.enabled else "disabled in CB1: no calls are made"}

    def suggest(self, task, payload):
        if not self.enabled:
            raise AdapterDisabled(f"{self.label} is not enabled in CB1; no network call was made")
        raise NotImplementedError


class RemoteAdapterStub(Adapter):
    network = True

    def __init__(self, name, label, env_key):
        self.name, self.label, self.env_key = name, label, env_key


class LocalRulesAdapter(Adapter):
    name, label, enabled = "local-rules", "Local rules (deterministic planner)", True
    tasks = ("direction.draft_plan",)

    def suggest(self, task, payload):
        if task != "direction.draft_plan":
            raise ValueError(f"local-rules does not handle {task}")
        from app.core import execute
        return execute("direction", payload)["artifact"]   # a proposal: validated and reviewed like any other input


REGISTRY = {a.name: a for a in (
    LocalRulesAdapter(),
    RemoteAdapterStub("chatgpt", "ChatGPT (OpenAI)", "OPENAI_API_KEY"),
    RemoteAdapterStub("gemini", "Gemini (Google)", "GEMINI_API_KEY"),
    RemoteAdapterStub("venice", "Venice", "VENICE_API_KEY"),
)}


def statuses():
    return [a.status() for a in REGISTRY.values()]


def get(name):
    try:
        return REGISTRY[name]
    except KeyError:
        raise KeyError(f"unknown adapter {name}") from None
