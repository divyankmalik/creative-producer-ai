-- Adds per-user project ownership. Nullable on purpose: projects created
-- while signed out (still fully supported -- see api/app/routes/projects.py)
-- have no owner and are only ever reachable by direct URL, never listed for
-- anyone. Signed-in creation stamps this from the verified Supabase session.
--
-- References auth.users (Supabase's own user table, always present once
-- Auth is enabled on a project) rather than a table this schema owns.
-- on delete set null: if a user's Supabase auth account is ever deleted,
-- their past projects survive as anonymous/unowned rather than being
-- silently destroyed.

alter table projects
    add column owner_id uuid references auth.users(id) on delete set null;

create index projects_owner_id_idx on projects (owner_id);
