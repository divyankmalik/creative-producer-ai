"""Fixed task template for a showrunner project.

`content.script.sN` is expanded at plan time into one node per script section
(e.g. `content.script.s1`, `content.script.s2`, ...) based on project params;
every expanded node inherits the `content.outline` hard dependency and feeds
`content.storyboard`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.models import DependencyKind


@dataclass(frozen=True)
class DependencyTemplate:
    node_key: str
    kind: DependencyKind = "hard"


@dataclass(frozen=True)
class NodeTemplate:
    node_key: str
    agent: str
    capability: str
    dependencies: tuple[DependencyTemplate, ...] = field(default_factory=tuple)
    expand_per_section: bool = False


NODE_TEMPLATE: list[NodeTemplate] = [
    NodeTemplate(
        node_key="research.brief",
        agent="research",
        capability="brief",
        dependencies=(),
    ),
    NodeTemplate(
        node_key="content.outline",
        agent="content",
        capability="outline",
        dependencies=(DependencyTemplate("research.brief", "hard"),),
    ),
    NodeTemplate(
        node_key="content.script.sN",
        agent="content",
        capability="script",
        dependencies=(DependencyTemplate("content.outline", "hard"),),
        expand_per_section=True,
    ),
    NodeTemplate(
        node_key="content.storyboard",
        agent="content",
        capability="storyboard",
        # NOTE: expanded content.script.s* keys are wired in by the planner at runtime.
        dependencies=(DependencyTemplate("content.script.sN", "hard"),),
    ),
    NodeTemplate(
        node_key="design.visual_language",
        agent="design",
        capability="visual_language",
        dependencies=(DependencyTemplate("content.outline", "hard"),),
    ),
    NodeTemplate(
        node_key="design.thumbnails",
        agent="design",
        capability="thumbnails",
        dependencies=(DependencyTemplate("design.visual_language", "hard"),),
    ),
    NodeTemplate(
        node_key="publishing.seo",
        agent="publishing",
        capability="seo",
        dependencies=(
            DependencyTemplate("content.outline", "hard"),
            DependencyTemplate("design.thumbnails", "soft"),
        ),
    ),
    NodeTemplate(
        node_key="publishing.package",
        agent="publishing",
        capability="package",
        dependencies=(
            DependencyTemplate("content.storyboard", "hard"),
            DependencyTemplate("publishing.seo", "hard"),
        ),
    ),
]


@dataclass(frozen=True)
class GateTemplate:
    key: str
    blocks_node_key_prefix: str


GATES: list[GateTemplate] = [
    GateTemplate(key="outline_review", blocks_node_key_prefix="content.script."),
]


def expand_template(section_count: int) -> list[NodeTemplate]:
    # TODO: replace the content.script.sN template entry with N concrete
    # content.script.s1..sN entries (and rewire content.storyboard's dependency
    # on each), returning the fully expanded node list for a project.
    raise NotImplementedError
