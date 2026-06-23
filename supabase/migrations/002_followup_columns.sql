-- Add follow-up tracking columns so patchLead state lives in Supabase,
-- not localStorage.

alter table leads
  add column if not exists follow_ups          jsonb       default '[]',
  add column if not exists follow_up_count     integer     default 0,
  add column if not exists last_contact_date   timestamptz,
  add column if not exists next_follow_up_date timestamptz;
