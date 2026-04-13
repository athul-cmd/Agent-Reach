create table if not exists public.research_user_settings (
  user_id text primary key,
  openai_api_key_ciphertext text,
  openai_api_key_last4 text,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = timezone('utc', now());
  return new;
end;
$$;

drop trigger if exists research_user_settings_set_updated_at on public.research_user_settings;
create trigger research_user_settings_set_updated_at
before update on public.research_user_settings
for each row execute function public.set_updated_at();

alter table public.research_user_settings enable row level security;

create policy "research_user_settings_select_own"
on public.research_user_settings
for select
to authenticated
using (auth.uid()::text = user_id);

create policy "research_user_settings_insert_own"
on public.research_user_settings
for insert
to authenticated
with check (auth.uid()::text = user_id);

create policy "research_user_settings_update_own"
on public.research_user_settings
for update
to authenticated
using (auth.uid()::text = user_id)
with check (auth.uid()::text = user_id);

create policy "research_user_settings_delete_own"
on public.research_user_settings
for delete
to authenticated
using (auth.uid()::text = user_id);

create table if not exists public.refresh_requests (
  id text primary key,
  research_profile_id text not null references public.research_profiles(id) on delete cascade,
  trigger text not null,
  status text not null,
  query_snapshot jsonb not null default '{}'::jsonb,
  latest_stage text not null default '',
  summary text not null default '',
  source_status jsonb not null default '{}'::jsonb,
  started_at timestamptz,
  finished_at timestamptz,
  created_at timestamptz not null,
  updated_at timestamptz not null
);

alter table public.job_runs add column if not exists refresh_request_id text not null default '';
alter table public.job_runs add column if not exists depends_on_job_run_id text not null default '';
alter table public.job_runs add column if not exists output_snapshot jsonb not null default '{}'::jsonb;
alter table public.job_runs add column if not exists current_step text not null default '';
alter table public.job_runs add column if not exists current_source text not null default '';
alter table public.job_runs add column if not exists progress_current integer not null default 0;
alter table public.job_runs add column if not exists progress_total integer not null default 0;

create table if not exists public.job_run_events (
  id text primary key,
  job_run_id text not null references public.job_runs(id) on delete cascade,
  refresh_request_id text not null default '',
  level text not null default 'info',
  message text not null,
  step text not null default '',
  source text not null default '',
  progress_current integer not null default 0,
  progress_total integer not null default 0,
  event_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null
);

create index if not exists idx_refresh_requests_profile_created
on public.refresh_requests (research_profile_id, created_at desc);

create index if not exists idx_job_runs_refresh
on public.job_runs (refresh_request_id, scheduled_for asc);

create index if not exists idx_job_run_events_refresh_created
on public.job_run_events (refresh_request_id, created_at desc);

create or replace function public.claim_due_job_runs(
  p_now timestamptz,
  p_limit integer default 1,
  p_lease_seconds integer default 900,
  p_lease_owner text default 'scheduler'
)
returns setof public.job_runs
language plpgsql
as $$
declare
  v_ids text[];
begin
  with candidates as (
    select id
    from public.job_runs
    where (
      status = 'pending'
      and scheduled_for <= p_now
      and (
        depends_on_job_run_id = ''
        or exists (
          select 1
          from public.job_runs dep
          where dep.id = public.job_runs.depends_on_job_run_id
            and dep.status = 'succeeded'
        )
      )
    ) or (
      status = 'running'
      and lease_expires_at is not null
      and lease_expires_at <= p_now
    )
    order by scheduled_for asc
    for update skip locked
    limit greatest(p_limit, 1)
  ),
  updated as (
    update public.job_runs j
    set status = 'running',
        started_at = coalesce(j.started_at, p_now),
        finished_at = null,
        attempt_count = j.attempt_count + 1,
        heartbeat_at = p_now,
        error_summary = '',
        lease_token = md5(random()::text || clock_timestamp()::text || j.id),
        lease_owner = coalesce(nullif(p_lease_owner, ''), 'scheduler'),
        lease_expires_at = p_now + make_interval(secs => greatest(p_lease_seconds, 60)),
        dispatched_at = null
    from candidates c
    where j.id = c.id
    returning j.id
  )
  select array_agg(id) into v_ids from updated;

  if v_ids is null then
    return;
  end if;

  return query
  select *
  from public.job_runs
  where id = any(v_ids)
  order by scheduled_for asc;
end;
$$;
