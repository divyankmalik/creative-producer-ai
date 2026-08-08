"""Tests for director/template.py -- pure logic, no mocking needed."""

from __future__ import annotations

import pytest

from app.director.template import NODE_TEMPLATE, expand_template, slug_for_node_key


def test_expand_template_creates_one_node_per_section() -> None:
    expanded = expand_template(3)
    script_keys = [t.node_key for t in expanded if t.node_key.startswith("content.script.")]
    assert script_keys == ["content.script.s1", "content.script.s2", "content.script.s3"]


def test_expand_template_total_count_replaces_one_placeholder_with_n() -> None:
    expanded = expand_template(5)
    # original template has 8 entries, one of which (content.script.sN) is
    # the placeholder being replaced by 5 concrete entries: net +4
    assert len(expanded) == len(NODE_TEMPLATE) + 4


def test_expand_template_storyboard_depends_on_every_script_section() -> None:
    expanded = expand_template(4)
    storyboard = next(t for t in expanded if t.node_key == "content.storyboard")
    dep_keys = {dep.node_key for dep in storyboard.dependencies}
    assert dep_keys == {"content.script.s1", "content.script.s2", "content.script.s3", "content.script.s4"}
    assert all(dep.kind == "hard" for dep in storyboard.dependencies)


def test_expand_template_leaves_unrelated_nodes_untouched() -> None:
    expanded = expand_template(2)
    research_brief = next(t for t in expanded if t.node_key == "research.brief")
    assert research_brief.dependencies == ()
    outline = next(t for t in expanded if t.node_key == "content.outline")
    assert [dep.node_key for dep in outline.dependencies] == ["research.brief"]


def test_expand_template_rejects_invalid_section_count() -> None:
    with pytest.raises(ValueError):
        expand_template(0)


@pytest.mark.parametrize(
    ("node_key", "expected_slug"),
    [
        ("research.brief", "research-brief"),
        ("content.outline", "content-outline"),
        ("content.script.s1", "content-script-s1"),
        ("content.storyboard", "content-storyboard"),
        ("design.visual_language", "design-visual-language"),
        ("design.thumbnails", "design-thumbnails"),
        ("publishing.seo", "publishing-seo"),
        ("publishing.package", "publishing-package"),
    ],
)
def test_slug_for_node_key_matches_every_agent_hardcoded_slug(node_key: str, expected_slug: str) -> None:
    """Regression test for a real bug caught during Director development:
    slug_for_node_key's first draft only replaced "." and missed that
    design.visual_language's underscore also needs flattening to match
    DesignAgent's hardcoded slug="design-visual-language".
    """
    assert slug_for_node_key(node_key) == expected_slug
