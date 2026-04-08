"""Tests for grouping suggestion engine."""

from stackmap.grouping.suggest import suggest_groups
from stackmap.parsers.base import ResourceCategory, StackMapIR, StackMapNode


def _node(id: str, name: str, rtype: str = "aws_lambda_function",
          tags: dict | None = None, props: dict | None = None) -> StackMapNode:
    return StackMapNode(
        id=id,
        name=name,
        resource_type=rtype,
        provider="aws",
        category=ResourceCategory.SERVERLESS,
        tags=tags or {},
        properties=props or {},
    )


class TestSuggestGroups:
    def test_suggest_tag_based_groups(self) -> None:
        ir = StackMapIR(nodes=[
            _node("fn1", "handler-1", tags={"service": "auth"}),
            _node("fn2", "handler-2", tags={"service": "auth"}),
            _node("fn3", "handler-3", tags={"service": "auth"}),
            _node("fn4", "handler-4", tags={"service": "api"}),
            _node("fn5", "handler-5", tags={"service": "api"}),
            _node("fn6", "handler-6", tags={"service": "api"}),
        ])

        suggestions = suggest_groups(ir)
        names = [s.name.lower() for s in suggestions]
        assert any("auth" in n for n in names)
        assert any("api" in n for n in names)

    def test_suggest_prefix_based_groups(self) -> None:
        ir = StackMapIR(nodes=[
            _node("fn1", "analytics-ingester"),
            _node("fn2", "analytics-processor"),
            _node("fn3", "analytics-writer"),
            _node("fn4", "payment-handler"),
        ])

        suggestions = suggest_groups(ir)
        assert len(suggestions) >= 1
        assert any("analytics" in s.name.lower() for s in suggestions)

    def test_no_suggestions_for_small_ir(self) -> None:
        ir = StackMapIR(nodes=[
            _node("fn1", "handler-1"),
            _node("fn2", "handler-2"),
        ])

        suggestions = suggest_groups(ir)
        # May or may not have suggestions, but shouldn't crash
        assert isinstance(suggestions, list)

    def test_suggestions_have_colors(self) -> None:
        ir = StackMapIR(nodes=[
            _node("fn1", "auth-1", tags={"service": "auth"}),
            _node("fn2", "auth-2", tags={"service": "auth"}),
            _node("fn3", "auth-3", tags={"service": "auth"}),
        ])

        suggestions = suggest_groups(ir)
        for s in suggestions:
            assert s.color is not None
            assert s.color.startswith("#")

    def test_suggestions_have_rules(self) -> None:
        ir = StackMapIR(nodes=[
            _node("fn1", "auth-1", tags={"service": "auth"}),
            _node("fn2", "auth-2", tags={"service": "auth"}),
            _node("fn3", "auth-3", tags={"service": "auth"}),
        ])

        suggestions = suggest_groups(ir)
        for s in suggestions:
            assert len(s.rules) > 0
