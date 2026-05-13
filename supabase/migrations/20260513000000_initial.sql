-- QB AI Agent — initial schema

-- Companies: QBO OAuth tokens per company
create table if not exists companies (
  id            serial primary key,
  name          text not null unique,
  realm_id      text not null,
  env           text not null default 'production', -- 'production' | 'sandbox'
  access_token  text,
  refresh_token text not null,
  token_type    text default 'Bearer',
  connected_at  timestamptz default now(),
  updated_at    timestamptz default now()
);

-- Conversations: chat history per company session
create table if not exists conversations (
  id          uuid primary key default gen_random_uuid(),
  company_id  integer references companies(id) on delete cascade,
  messages    jsonb not null default '[]',
  created_at  timestamptz default now(),
  updated_at  timestamptz default now()
);

-- Tax deadline tracking: mark deadlines done / add notes
create table if not exists deadline_status (
  id            serial primary key,
  company_id    integer references companies(id) on delete cascade,
  deadline_id   text not null,  -- matches id in irs_calendar.py
  status        text not null default 'pending', -- 'pending' | 'done' | 'na'
  notes         text,
  updated_at    timestamptz default now(),
  unique(company_id, deadline_id)
);

-- Auto-update updated_at on companies
create or replace function set_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create trigger companies_updated_at
  before update on companies
  for each row execute function set_updated_at();

create trigger conversations_updated_at
  before update on conversations
  for each row execute function set_updated_at();

create trigger deadline_status_updated_at
  before update on deadline_status
  for each row execute function set_updated_at();
