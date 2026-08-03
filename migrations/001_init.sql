-- showrunner: initial schema
-- Five tables: projects, task_nodes, artifacts, artifact_versions, artifact_dependencies.

create extension if not exists "pgcrypto";

-- ---------------------------------------------------------------------------
-- projects
-- ---------------------------------------------------------------------------

create table projects (
    id              uuid primary key default gen_random_uuid(),
    title           text not null,
    idea            text not null,
    status          text not null default 'planning'
                        check (status in ('planning', 'running', 'blocked', 'awaiting_gate', 'done', 'failed')),
    params          jsonb not null default '{}'::jsonb,
    created_at      timestamptz not null default now(),
    updated_at      timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- task_nodes
-- ---------------------------------------------------------------------------

create table task_nodes (
    id              uuid primary key default gen_random_uuid(),
    project_id      uuid not null references projects(id) on delete cascade,
    node_key        text not null,
    agent           text not null,
    capability      text not null,
    status          text not null default 'queued'
                        check (status in ('queued', 'ready', 'running', 'succeeded', 'failed', 'blocked', 'skipped')),
    -- [{"nodeKey": "...", "kind": "hard"|"soft"}]
    dependencies    jsonb not null default '[]'::jsonb,
    params          jsonb not null default '{}'::jsonb,
    attempts         integer not null default 0,
    last_error      text,
    created_at      timestamptz not null default now(),
    updated_at      timestamptz not null default now(),
    unique (project_id, node_key)
);

create index idx_task_nodes_project_id on task_nodes(project_id);
create index idx_task_nodes_status on task_nodes(status);

-- ---------------------------------------------------------------------------
-- artifacts
-- ---------------------------------------------------------------------------

create table artifacts (
    id              uuid primary key default gen_random_uuid(),
    project_id      uuid not null references projects(id) on delete cascade,
    node_key        text not null,
    type            text not null,
    slug            text not null,
    current_version integer not null default 1,
    payload         jsonb not null default '{}'::jsonb,
    summary         text,
    is_stale        boolean not null default false,
    stale_reason    text,
    edited_by       text,
    model           text,
    created_at      timestamptz not null default now(),
    updated_at      timestamptz not null default now(),
    unique (project_id, slug)
);

create index idx_artifacts_project_id on artifacts(project_id);
create index idx_artifacts_node_key on artifacts(node_key);

-- ---------------------------------------------------------------------------
-- artifact_versions
-- ---------------------------------------------------------------------------

create table artifact_versions (
    id              uuid primary key default gen_random_uuid(),
    artifact_id     uuid not null references artifacts(id) on delete cascade,
    version         integer not null,
    payload         jsonb not null,
    summary         text,
    edited_by       text,
    model           text,
    created_at      timestamptz not null default now(),
    unique (artifact_id, version)
);

create index idx_artifact_versions_artifact_id on artifact_versions(artifact_id);

-- ---------------------------------------------------------------------------
-- artifact_dependencies
-- ---------------------------------------------------------------------------

create table artifact_dependencies (
    id                  uuid primary key default gen_random_uuid(),
    project_id          uuid not null references projects(id) on delete cascade,
    artifact_id         uuid not null references artifacts(id) on delete cascade,
    depends_on_artifact_id uuid not null references artifacts(id) on delete cascade,
    kind                text not null default 'hard' check (kind in ('hard', 'soft')),
    created_at          timestamptz not null default now(),
    unique (artifact_id, depends_on_artifact_id)
);

create index idx_artifact_dependencies_artifact_id on artifact_dependencies(artifact_id);
create index idx_artifact_dependencies_depends_on on artifact_dependencies(depends_on_artifact_id);

-- ---------------------------------------------------------------------------
-- versioning trigger: snapshot artifacts.payload into artifact_versions
-- ---------------------------------------------------------------------------

create or replace function snapshot_artifact_version()
returns trigger as $$
begin
    insert into artifact_versions (artifact_id, version, payload, summary, edited_by, model)
    values (new.id, new.current_version, new.payload, new.summary, new.edited_by, new.model)
    on conflict (artifact_id, version) do nothing;
    return new;
end;
$$ language plpgsql;

create trigger trg_snapshot_artifact_version
    before insert or update of payload on artifacts
    for each row
    execute function snapshot_artifact_version();

-- ---------------------------------------------------------------------------
-- mark_dependents_stale: recursive walk over hard artifact_dependencies edges
-- ---------------------------------------------------------------------------

create or replace function mark_dependents_stale(p_artifact_id uuid, p_reason text)
returns integer as $$
declare
    affected_count integer;
begin
    with recursive dependents as (
        select ad.artifact_id, 1 as depth
        from artifact_dependencies ad
        where ad.depends_on_artifact_id = p_artifact_id
          and ad.kind = 'hard'

        union

        select ad.artifact_id, d.depth + 1
        from artifact_dependencies ad
        join dependents d on ad.depends_on_artifact_id = d.artifact_id
        where ad.kind = 'hard'
          and d.depth < 10
    ),
    updated as (
        update artifacts
        set is_stale = true,
            stale_reason = p_reason,
            updated_at = now()
        where id in (select distinct artifact_id from dependents)
        returning id
    )
    select count(*) into affected_count from updated;

    return affected_count;
end;
$$ language plpgsql;

-- ---------------------------------------------------------------------------
-- updated_at maintenance
-- ---------------------------------------------------------------------------

create or replace function set_updated_at()
returns trigger as $$
begin
    new.updated_at = now();
    return new;
end;
$$ language plpgsql;

create trigger trg_projects_updated_at
    before update on projects
    for each row execute function set_updated_at();

create trigger trg_task_nodes_updated_at
    before update on task_nodes
    for each row execute function set_updated_at();

create trigger trg_artifacts_updated_at
    before update on artifacts
    for each row execute function set_updated_at();
