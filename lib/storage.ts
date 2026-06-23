// Session & navigation state only — localStorage.
// All persistent lead data lives in lib/lead-service.ts (Supabase).

import type { Lead } from '@/app/types';

const AUDITS_KEY   = 'zappko-audits-count';
const OUTREACH_KEY = 'zappko-outreach-count';
const SELECTED_KEY = 'zappko-selected-lead';

export function setSelectedLead(lead: Lead | Omit<Lead, 'id' | 'savedAt' | 'status'>): void {
  if (typeof window === 'undefined') return;
  localStorage.setItem(SELECTED_KEY, JSON.stringify(lead));
}

export function getSelectedLead(): Lead | null {
  if (typeof window === 'undefined') return null;
  try {
    const raw = localStorage.getItem(SELECTED_KEY) || localStorage.getItem('selectedLead');
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function incrementAudits(count = 1): void {
  if (typeof window === 'undefined') return;
  const current = parseInt(localStorage.getItem(AUDITS_KEY) || '0', 10);
  localStorage.setItem(AUDITS_KEY, String(current + count));
}

export function incrementOutreach(count = 1): void {
  if (typeof window === 'undefined') return;
  const current = parseInt(localStorage.getItem(OUTREACH_KEY) || '0', 10);
  localStorage.setItem(OUTREACH_KEY, String(current + count));
}
