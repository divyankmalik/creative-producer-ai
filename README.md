# creative-producer-ai
Agentic content pipeline with hub-and-spoke orchestration. Workers never communicate directly; all coordination flows through structured JSON, events, and shared Postgres state. Dependency-graph staleness enables selective regeneration without destroying user edits.
