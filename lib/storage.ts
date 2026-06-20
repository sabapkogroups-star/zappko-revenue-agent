import type { Lead, LeadStatus, DashboardStats } from '@/app/types';

const LEADS_KEY    = 'zappko-leads';
const AUDITS_KEY   = 'zappko-audits-count';
const OUTREACH_KEY = 'zappko-outreach-count';

// ---------------------------------------------------------------------------
// Dedup helpers
// ---------------------------------------------------------------------------

function _getDomain(url: string): string {
  try { return new URL(url).hostname.replace(/^www\./, '').toLowerCase(); }
  catch { return ''; }
}

function _phoneDigits(phone: string | undefined): string {
  return (phone ?? '').replace(/\D/g, '');
}

const _GENERIC_EMAIL_PREFIXES = new Set([
  'info', 'hello', 'contact', 'support', 'admin', 'mail', 'office',
  'team', 'enquiries', 'enquiry', 'sales', 'marketing', 'help',
  'general', 'accounts', 'reception', 'enquire', 'connect', 'business',
]);

function _isPersonalEmail(email: string): boolean {
  const prefix = email.split('@')[0].toLowerCase();
  return !!prefix && !_GENERIC_EMAIL_PREFIXES.has(prefix);
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

export function getLeads(): Lead[] {
  if (typeof window === 'undefined') return [];
  try {
    return JSON.parse(localStorage.getItem(LEADS_KEY) || '[]');
  } catch {
    return [];
  }
}

/**
 * Save a lead, blocking duplicates on five signals:
 *   1. Website domain
 *   2. Personal email (non-generic prefix)
 *   3. Phone digits (≥7 digit match)
 *   4. LinkedIn personal profile URL
 *   5. Company name (legacy fallback)
 */
export function saveLead(
  lead: Omit<Lead, 'id' | 'savedAt' | 'status'>,
): { saved: boolean; message: string } {
  const leads = getLeads();

  const newDomain   = _getDomain(lead.website);
  const newEmail    = (lead.email ?? '').toLowerCase().trim();
  const newPhoneD   = _phoneDigits(lead.phone);
  const newLinkedin = (lead.linkedinUrl ?? '').replace(/\/$/, '').toLowerCase();

  const duplicate = leads.find((l) => {
    if (newDomain && _getDomain(l.website) === newDomain) return true;

    const existEmail = (l.email ?? '').toLowerCase().trim();
    if (
      newEmail && existEmail &&
      _isPersonalEmail(newEmail) && _isPersonalEmail(existEmail) &&
      newEmail === existEmail
    ) return true;

    const existPhoneD = _phoneDigits(l.phone);
    if (newPhoneD.length >= 7 && existPhoneD.length >= 7 && newPhoneD === existPhoneD)
      return true;

    const existLinkedin = (l.linkedinUrl ?? '').replace(/\/$/, '').toLowerCase();
    if (
      newLinkedin && existLinkedin &&
      newLinkedin.includes('linkedin.com/in/') &&
      newLinkedin === existLinkedin
    ) return true;

    if (l.company.toLowerCase() === lead.company.toLowerCase()) return true;

    return false;
  });

  if (duplicate) {
    return { saved: false, message: `Already saved as "${duplicate.company}"` };
  }

  const newLead: Lead = {
    ...lead,
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
    status: 'new',
    savedAt: new Date().toISOString(),
  };

  leads.push(newLead);
  localStorage.setItem(LEADS_KEY, JSON.stringify(leads));
  return { saved: true, message: 'Lead saved successfully' };
}

export function deleteLead(id: string): void {
  const leads = getLeads().filter((l) => l.id !== id);
  localStorage.setItem(LEADS_KEY, JSON.stringify(leads));
}

export function updateLeadStatus(id: string, status: LeadStatus): void {
  const leads = getLeads().map((l) => (l.id === id ? { ...l, status } : l));
  localStorage.setItem(LEADS_KEY, JSON.stringify(leads));
}

export function patchLead(id: string, patch: Partial<Lead>): void {
  const leads = getLeads().map((l) => (l.id === id ? { ...l, ...patch } : l));
  localStorage.setItem(LEADS_KEY, JSON.stringify(leads));
}

export function setSelectedLead(lead: Lead | Omit<Lead, 'id' | 'savedAt' | 'status'>): void {
  localStorage.setItem('zappko-selected-lead', JSON.stringify(lead));
}

export function getSelectedLead(): Lead | null {
  if (typeof window === 'undefined') return null;
  try {
    const raw = localStorage.getItem('zappko-selected-lead') || localStorage.getItem('selectedLead');
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function incrementAudits(count = 1): void {
  const current = parseInt(localStorage.getItem(AUDITS_KEY) || '0', 10);
  localStorage.setItem(AUDITS_KEY, String(current + count));
}

export function incrementOutreach(count = 1): void {
  const current = parseInt(localStorage.getItem(OUTREACH_KEY) || '0', 10);
  localStorage.setItem(OUTREACH_KEY, String(current + count));
}

export function getDashboardStats(): DashboardStats {
  const leads = getLeads();
  const hotLeads = leads.filter((l) => l.hotLeadScore >= 60).length;

  const pipelineValue = leads.reduce((sum, l) => {
    const val = parseInt(l.dealValue.replace(/[₹,\s+]/g, ''), 10);
    return sum + (isNaN(val) ? 0 : val);
  }, 0);

  return {
    totalLeads: leads.length,
    hotLeads,
    pipelineValue,
    auditsGenerated: parseInt(localStorage.getItem(AUDITS_KEY) || '0', 10),
    outreachGenerated: parseInt(localStorage.getItem(OUTREACH_KEY) || '0', 10),
  };
}
