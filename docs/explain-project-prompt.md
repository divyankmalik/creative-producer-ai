# Prompt: Explain the "showrunner" / creative-producer-ai project

Paste everything below into a fresh Claude conversation.

---

I want you to study the context I'm giving you below about a codebase called
**showrunner** (repo name `creative-producer-ai`) and produce a set of
explanations for a **junior university student who is fairly new to
multi-agent systems, LLM pipelines, and backend architecture in general**.
Assume they know basic Python and can read code, but have never built
anything with LLM agents, task DAGs, or async Python before. Use plain
language and concrete analogies before diving into code-level detail.

Please produce:
1. **A flowchart or diagram** (mermaid is fine) of the task DAG — which
   pieces of work depend on which, and which dependencies are "hard"
   (blocking) vs "soft" (optional/best-effort).
2. **A flowchart of one agent's internal control loop** (generate → validate
   → repair) showing how a retry actually works.
3. **A module/import map** — which files import from which, so the student
   can see how the codebase is layered (contracts → infra → validators →
   agents).
4. **A plain-English summary** of the whole system, written the way you'd
   explain it to someone who has never seen an "agent" before.
5. **A short explanation of the test suite** — what's mocked, what's real,
   and why that split matters.

---

## 1. What this project actually is

Think of it like a TV show's **production pipeline**, not a chatbot. You
give it one idea (e.g. "why fully-async daily standups quietly kill remote
team morale"), and instead of one LLM call spitting out a script, a small
team of specialist AI agents — coordinated by a central **Director** — turns
that idea into a full, *editable* pre-production package: a researched
angle, a script, a shot-by-shot storyboard, a visual style guide, thumbnail
concepts, and publish-ready SEO metadata.

Crucially: it does **not** produce a rendered video, images, or audio. It
produces the plan a human crew (or downstream tools) would need to actually
make the video — the same way a director/showrunner doesn't personally
write, shoot, and edit, they coordinate departments and keep everything
consistent.

The core architectural principle (from the README): **workers never
communicate directly with each other.** All coordination flows through the
Director, via shared Postgres state. An agent never calls another agent. It
only ever reads/writes artifacts in the database.

## 2. The four specialist agents and what they produce

| Agent | Capabilities | Produces |
|---|---|---|
| `ResearchAgent` | `brief` | A research brief: an angle, an audience insight, 3-8 key points, and the real sources (via Tavily web search) backing them |
| `ContentAgent` | `outline`, `script`, `storyboard` | An outline (ordered sections), spoken narration text per section, and a shot-by-shot storyboard |
| `DesignAgent` | `visual_language`, `thumbnails` | A color/typography/imagery style guide, and concrete thumbnail concepts (visual + overlay text) |
| `PublishingAgent` | `seo`, `package` | Search-optimized title/description/tags, and the final assembled deliverable merging the storyboard + SEO metadata |

Each agent can have **multiple capabilities** — e.g. `ContentAgent` handles
three different jobs (`outline`/`script`/`storyboard`). It's one Python
class per agent, and every method inside it dispatches on
`env.capability` (a string like `"outline"` or `"seo"`) to decide which of
its jobs to actually do on a given call. The Director doesn't instantiate a
different class per job — it always calls e.g. `ContentAgent().run(env)`,
and the envelope tells the agent which of its jobs to perform.

## 3. The task DAG — what depends on what

This is the fixed pipeline (`director/template.py`). Each node is one unit
of work; each edge is a dependency. Two kinds of dependency:

- **HARD** — the dependency must fully succeed before this node can run.
  If a hard dependency fails, everything transitively depending on it gets
  marked `blocked` and never runs (`scheduler.block_hard_dependents`).
- **SOFT** — used if present, ignored if missing. A soft dependency being
  absent, delayed, or failed **never blocks** the node that depends on it.

```
research.brief          -> []
content.outline         -> [research.brief: HARD]
content.script.s1..sN   -> [content.outline: HARD]      (expanded into one node per script section at plan time)
content.storyboard      -> [content.script.*: HARD]
design.visual_language  -> [content.outline: HARD]
design.thumbnails       -> [design.visual_language: HARD]
publishing.seo          -> [content.outline: HARD, design.thumbnails: SOFT]
publishing.package      -> [content.storyboard: HARD, publishing.seo: HARD]
```

There's also one human approval **gate**, `outline_review`, which blocks
`content.script.*` from running until a human approves the outline — so the
system doesn't burn LLM calls writing scripts for a structure nobody's
signed off on.

Notice `publishing.seo`'s soft dependency on `design.thumbnails` is the
**only** soft edge in the whole DAG. That's deliberate: SEO metadata is
still complete and useful without a thumbnail (just less cross-referenced),
so it shouldn't be forced to wait on the entire Design branch finishing.

## 4. The shared control loop every agent runs

This is the one piece of "agent" architecture that's shared, not
duplicated per agent — it lives in `agents/base.py` as a template-method
base class:

```python
class BaseAgent(ABC):
    async def run(self, env: TaskEnvelope) -> AgentResult:
        ctx = await self.build_context(env)          # gather inputs
        for attempt in range(1, max_attempts + 1):
            generated = await self.generate(ctx)      # ask the LLM
            report = await self.validate(ctx, generated)  # check the draft
            if report.ok:
                return await self.build_output(ctx, generated)  # success
            ctx.repair_hint = report.repair_hint       # tell it what's wrong
        return AgentResult(ok=False, ...)              # gave up after 3 tries
```

Every subclass (`ResearchAgent`, `ContentAgent`, `DesignAgent`,
`PublishingAgent`) only implements four hooks: `build_context`, `generate`,
`validate`, `build_output`. None of them re-implement the retry loop. The
key idea: when validation fails, the system doesn't just try again blindly —
it tells the LLM *exactly* what was wrong (e.g. "you used 340 words, target
was 250, cut 90") and asks it to fix that specific problem.

One important nuance: this self-correction **only works when `generate()`
actually reads `ctx.repair_hint`.** `PublishingAgent`'s `package` capability
doesn't call an LLM at all — it just assembles two already-finished
artifacts together in Python. So if its validation ever failed, retrying
would produce the exact same (still-broken) output three times in a row,
because there's no randomness or feedback loop for the hint to influence.
That's a real, tested property of that one capability (see the test suite
section below) — not every "retry" in this system can self-heal.

## 5. Data contracts (what gets passed around)

Everything flows through Pydantic models in `models.py`:

- **`TaskEnvelope`** — what the Director hands an agent to run one job:
  `project_id`, `node_key`, `agent`, `capability`, `attempt`,
  `input_artifact_slugs` (references, not payloads — the agent fetches them
  itself), `params`, `word_budget`, `timeout_s`.
- **`AgentResult`** — what an agent hands back: `ok`, `artifact_type`,
  `slug`, `payload`, `summary`, or on failure `error_code`/`error_message`.
- **`ValidationReport`** — `ok`, `failures: list[str]`, and critically
  `repair_hint: str | None` — the thing that makes retries smarter than
  blind re-rolling.
- **`Project`**, **`TaskNode`**, **`Artifact`** — the actual DB row shapes
  (mirrored in `migrations/001_init.sql`).

Each agent also defines its own small schemas for what it generates — e.g.
`ContentAgent` has `Outline`, `Script`, `Storyboard`; `DesignAgent` has
`VisualLanguage`, `ThumbnailSet`; `PublishingAgent` has `SeoMetadata`,
`PublishingPackage`.

## 6. Module layout / import map

```
models.py               <- no internal imports; the shared contracts everything else depends on
db.py, config.py        <- Supabase/env plumbing
services/projects.py    <- depends on db.py, models.py
services/artifacts.py   <- depends on db.py, models.py
llm/client.py           <- depends on config.py (calls Gemini, falls back to Groq)
llm/structured.py       <- depends on llm/client.py (adds schema-constrained JSON parsing)
llm/search.py           <- depends on config.py (Tavily web search)
validators/word_budget.py   <- depends on models.py only (pure arithmetic)
validators/claims.py        <- depends on models.py only (pure text heuristics)
validators/design_rules.py  <- depends on models.py only (pure WCAG contrast math)
agents/base.py           <- depends on models.py (the shared retry-loop template)
agents/research.py       <- depends on base.py, llm/*, services/projects.py, validators/claims.py
agents/content.py        <- depends on base.py, llm/*, services/*, validators/claims.py, validators/word_budget.py
agents/design.py         <- depends on base.py, llm/structured.py, services/*, validators/design_rules.py
agents/publishing.py     <- depends on base.py, llm/structured.py, services/*, AND cross-imports Outline/Storyboard from agents/content.py
```

The layering is deliberate: pure data contracts at the bottom (`models.py`),
then infra (`db`/`config`/`llm`), then pure-logic validators (no I/O at
all), then agents at the top gluing it all together. Nothing at the bottom
ever imports from something above it.

## 7. Hard-won design decisions worth explaining, not just stating

- **Raw dict vs. re-validated typed model when reading an upstream
  artifact.** When an agent reads an artifact from a *different* agent
  (e.g. `ContentAgent` reading `research-brief`), it keeps the payload as a
  raw dict. When it reads its *own* prior capability's output (e.g.
  `PublishingAgent.package` reading `publishing-seo`, which this same agent
  produced), it re-validates into the real typed model. This is a
  convention, not a hard rule — worth asking the student why they'd choose
  differently in each case.
- **`model=None` on `PublishingPackage`'s `AgentResult`.** Every other
  artifact records which LLM produced it. `package` doesn't, because it
  genuinely wasn't LLM-generated — it's pure assembly. Setting a model name
  there would be a lie about provenance.
- **Soft dependencies use a `try_get_artifact_by_slug()` that returns
  `None` instead of raising**, while hard dependencies use
  `get_artifact_by_slug()` which raises on a missing row. Same underlying
  Supabase query, deliberately different failure behavior, because "missing"
  means something different for each.
- **Staleness only propagates over hard edges** (see
  `mark_dependents_stale` in the SQL migration — explicitly hard-edges-only,
  depth-limited recursive CTE). This means if `design.thumbnails` gets
  created *after* `publishing.seo` already ran without it, nothing
  automatically flags the SEO copy as improvable — that's a known,
  deliberate gap, not a bug, resolved (for now) by a human-triggered
  `POST /artifacts/{id}/regenerate` rather than automatic invalidation.

## 8. The test suite — what's mocked, what's real, and why

42 tests total across `api/tests/`:

| File | Count | Focus |
|---|---|---|
| `test_scheduler.py` | 9 | Pure DAG logic: hard failures block dependents, soft failures don't, `max_parallel` is respected |
| `agents/research/` | 3 | Happy path, repair-retry, retry exhaustion |
| `agents/content/` | 11 | All 3 capabilities x happy/repair/exhaustion, plus a pure word-budget-math test |
| `agents/design/` | 8 | Both capabilities x happy/repair (missing role, low contrast, overlay cap)/exhaustion |
| `agents/publishing/` | 11 | Both capabilities, soft-dependency present/absent/malformed, boundary values, and the "package can't self-heal" test |

**The pattern in every agent test file**: mock only the true I/O boundaries
— `get_project`, `get_artifact_by_slug`, `generate_structured` — using
`unittest.mock.AsyncMock` + `patch`. Everything else (the actual validators
like `check_grounding`, `check_word_budget`, `check_contrast`) runs for
real, unmocked. That split matters: it means these tests prove the agent's
*decision logic* is correct (does it catch a bad draft? does it feed back
the right hint? does it give up after 3 tries?) without spending real
money/API calls on Gemini or Tavily, and without needing live credentials
to run in CI.

---

Please now produce the diagrams and explanations requested at the very top
of this prompt, using everything above as ground truth. Where you show code,
keep it short and focus on the *shape* of the pattern, not exhaustive
listings.
