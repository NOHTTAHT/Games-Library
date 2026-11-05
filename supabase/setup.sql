-- Games Library: run once in Supabase → SQL Editor → New query → Run.
-- Safe to run again.

-- 1) All app data lives in one table: collection name + document id + JSON data
create table if not exists public.docs (
  coll       text        not null,
  id         text        not null,
  data       jsonb       not null default '{}'::jsonb,
  updated_at timestamptz not null default now(),
  primary key (coll, id)
);
alter table public.docs enable row level security;
alter table public.docs replica identity full;   -- so live updates also carry deletes

-- Only signed-in users can read or write. Turn off new sign-ups so that means only you.
drop policy if exists "signed in can read"  on public.docs;
drop policy if exists "signed in can write" on public.docs;
create policy "signed in can read"  on public.docs for select to authenticated using (true);
create policy "signed in can write" on public.docs for all    to authenticated using (true) with check (true);

-- 2) Live updates between devices
do $$ begin
  alter publication supabase_realtime add table public.docs;
exception when duplicate_object then null; end $$;

-- 3) Storage for covers you upload yourself (anyone can view an image, only you can add one)
insert into storage.buckets (id, name, public) values ('covers', 'covers', true)
on conflict (id) do update set public = true;
drop policy if exists "covers upload" on storage.objects;
drop policy if exists "covers change" on storage.objects;
create policy "covers upload" on storage.objects for insert to authenticated with check (bucket_id = 'covers');
create policy "covers change" on storage.objects for update to authenticated using (bucket_id = 'covers');
