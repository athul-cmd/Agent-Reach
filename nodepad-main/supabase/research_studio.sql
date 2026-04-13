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
