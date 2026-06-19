from jailbird.types import Decision, PolicyVerdict, Event, ToolCall, ConfigArtifact, Task

def test_decision_values():
    assert Decision.ALLOW.value == "allow"
    assert Decision.DENY.value == "deny"

def test_dataclass_defaults():
    v = PolicyVerdict(Decision.DENY, reason="nope", rule="git push")
    assert v.decision is Decision.DENY and v.rule == "git push"
    assert Event(kind="text", text="hi").cost_usd == 0.0
    assert ToolCall(name="Bash", command="ls").paths == []
    assert ConfigArtifact(path="settings.json", content="{}").merge is True
    assert Task(prompt="do x").cwd == "."
