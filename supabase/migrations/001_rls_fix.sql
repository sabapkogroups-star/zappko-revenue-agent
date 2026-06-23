-- Fix RLS so the anon key can read and write the leads table

alter table leads enable row level security;

drop policy if exists "Allow all operations" on leads;

create policy "Allow all operations"
  on leads
  for all
  using (true)
  with check (true);

-- Add column defaults so minimal inserts (company + website + status) don't
-- violate NOT NULL constraints on the numeric / array columns.
alter table leads
  alter column website_score      set default 0,
  alter column opportunity_score  set default 0,
  alter column hot_lead_score     set default 0,
  alter column deal_value         set default '',
  alter column issues             set default '{}',
  alter column recommended_services set default '{}';
