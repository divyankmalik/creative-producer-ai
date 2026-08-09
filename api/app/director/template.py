"""Fixed task template for a showrunner project.

`content.script.sN` is expanded at plan time into one node per script section
(e.g. `content.script.s1`, `content.script.s2`, ...) based on project params;
every expanded node inherits the `content.outline` hard dependency and feeds
`content.storyboard`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.models import DependencyKind

# Single source of truth for "how many script sections if the project didn't
# specify" -- both director/graph.py (which actually creates that many
# content.script.sN nodes) and agents/content.py (which must tell the LLM to
# produce a matching-length outline) need the same number. Used to live
# duplicated in graph.py alone, with nothing enforcing the outline's actual
# section count matched it -- see agents/content.py's outline validation.
DEFAULT_SECTION_COUNT = 3


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
    """Replace the content.script.sN placeholder with section_count concrete
    content.script.s1..sN entries, and rewire content.storyboard's dependency
    to point at all of them (instead of the placeholder). Relies on
    NODE_TEMPLATE listing content.script.sN before content.storyboard, so the
    expanded keys are known by the time storyboard's turn comes up.
    """
    if section_count < 1:
        raise ValueError(f"section_count must be >= 1, got {section_count}")

    expanded: list[NodeTemplate] = []
    script_node_keys: list[str] = []

    for template in NODE_TEMPLATE:
        if template.expand_per_section:
            for i in range(1, section_count + 1):
                node_key = f"content.script.s{i}"
                script_node_keys.append(node_key)
                expanded.append(
                    NodeTemplate(
                        node_key=node_key,
                        agent=template.agent,
                        capability=template.capability,
                        dependencies=template.dependencies,  # still [content.outline: hard]
                    )
                )
        elif template.node_key == "content.storyboard":
            expanded.append(
                NodeTemplate(
                    node_key=template.node_key,
                    agent=template.agent,
                    capability=template.capability,
                    dependencies=tuple(DependencyTemplate(key, "hard") for key in script_node_keys),
                )
            )
        else:
            expanded.append(template)

    return expanded


def slug_for_node_key(node_key: str) -> str:
    """The naming convention every agent already follows for its own output
    slugs: fully kebab-case, e.g. "content.outline" -> "content-outline",
    "content.script.s1" -> "content-script-s1", and
    "design.visual_language" -> "design-visual-language" (underscores get
    flattened too, not just dots -- DesignAgent hardcodes that slug with a
    dash, not an underscore). Used by the Director to turn a node's
    dependency edges into TaskEnvelope.input_artifact_slugs without
    hardcoding the mapping twice.
    """
    return node_key.replace(".", "-").replace("_", "-")
