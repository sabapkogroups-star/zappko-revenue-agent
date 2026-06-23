import { supabase } from './supabase';
import type { Lead, LeadStatus, DashboardStats, FollowUp } from '@/app/types';

// ---------------------------------------------------------------------------
// DB row type (snake_case columns from Supabase)
// ---------------------------------------------------------------------------

type DbRow = {
  id: string;
  company: string;
  website: string;
  decision_maker: string | null;
  email: string | null;
  phone: string | null;
  linkedin_url: string | null;
  website_score: number;
  opportunity_score: number;
  hot_lead_score: number;
  deal_value: string;
  issues: string[];
  recommended_services: string[];
  status: string;
  created_at: string;
  follow_ups: FollowUp[] | null;
  follow_up_count: number | null;
  last_contact_date: string | null;
  next_follow_up_date: string | null;
};

function rowToLead(row: DbRow): Lead {
  return {
    id: row.id,
    company: row.company,
    website: row.website,
    decisionMaker: row.decision_maker || '',
    title: '',
    email: row.email || '',
    phone: row.phone || '',
    linkedinUrl: row.linkedin_url || '',
    contactConfidence: 0,
    emailVerified: false,
    phoneVerified: false,
    source: '' as Lead['source'],
    confidence: 0,
    discoveredAt: '',
    websiteScore: row.website_score,
    opportunityScore: row.opportunity_score,
    hotLeadScore: row.hot_lead_score,
    dealValue: row.deal_value,
    issues: row.issues || [],
    recommendedService: row.recommended_services || [],
    emailDraft: '',
    whatsappDraft: '',
    status: row.status as LeadStatus,
    savedAt: row.created_at,
    followUps: row.follow_ups || [],
    followUpCount: row.follow_up_count ?? 0,
    lastContactDate: row.last_contact_date ?? undefined,
    nextFollowUpDate: row.next_follow_up_date ?? undefined,
  };
}

// ---------------------------------------------------------------------------
// Queries
// ---------------------------------------------------------------------------

export async function getLeads(): Promise<Lead[]> {
  const { data, error } = await supabase
    .from('leads')
    .select('*')
    .order('created_at', { ascending: false });

  if (error) {
    console.error('getLeads error:', error.message);
    return [];
  }

  return (data as DbRow[]).map(rowToLead);
}

export async function getLeadById(id: string): Promise<Lead | null> {
  const { data, error } = await supabase
    .from('leads')
    .select('*')
    .eq('id', id)
    .single();

  if (error || !data) return null;
  return rowToLead(data as DbRow);
}

// ---------------------------------------------------------------------------
// Mutations
// ---------------------------------------------------------------------------

export async function saveLead(
  lead: Omit<Lead, 'id' | 'savedAt' | 'status'>,
): Promise<{ saved: boolean; message: string }> {
  // Duplicate guard by company name
  const { data: byCompany, error: companyErr } = await supabase
    .from('leads')
    .select('id')
    .ilike('company', lead.company)
    .limit(1);

  if (companyErr) {
    console.error('saveLead company check error:', companyErr.message);
    return { saved: false, message: 'Database error — please try again' };
  }
  if (byCompany && byCompany.length > 0) {
    return { saved: false, message: 'Lead already exists' };
  }

  // Duplicate guard by website URL
  const { data: byWebsite, error: websiteErr } = await supabase
    .from('leads')
    .select('id')
    .ilike('website', lead.website)
    .limit(1);

  if (websiteErr) {
    console.error('saveLead website check error:', websiteErr.message);
    return { saved: false, message: 'Database error — please try again' };
  }
  if (byWebsite && byWebsite.length > 0) {
    return { saved: false, message: 'Lead already exists' };
  }

  const { error: insertErr } = await supabase.from('leads').insert({
    company: lead.company,
    website: lead.website,
    decision_maker: lead.decisionMaker || null,
    email: lead.email || null,
    phone: lead.phone || null,
    linkedin_url: lead.linkedinUrl || null,
    website_score: lead.websiteScore,
    opportunity_score: lead.opportunityScore,
    hot_lead_score: lead.hotLeadScore,
    deal_value: lead.dealValue,
    issues: lead.issues,
    recommended_services: lead.recommendedService,
    status: 'new',
  });

  if (insertErr) {
    console.error('saveLead insert error:', insertErr.message);
    return { saved: false, message: 'Failed to save — check console for details' };
  }

  return { saved: true, message: 'Lead saved successfully' };
}

export async function updateLead(id: string, patch: Partial<Lead>): Promise<void> {
  const update: Record<string, unknown> = {};

  if (patch.status !== undefined)           update.status             = patch.status;
  if (patch.followUps !== undefined)        update.follow_ups         = patch.followUps;
  if (patch.followUpCount !== undefined)    update.follow_up_count    = patch.followUpCount;
  if (patch.lastContactDate !== undefined)  update.last_contact_date  = patch.lastContactDate;
  if (patch.nextFollowUpDate !== undefined) update.next_follow_up_date = patch.nextFollowUpDate;
  if (patch.decisionMaker !== undefined)    update.decision_maker     = patch.decisionMaker;
  if (patch.email !== undefined)            update.email              = patch.email;
  if (patch.phone !== undefined)            update.phone              = patch.phone;
  if (patch.linkedinUrl !== undefined)      update.linkedin_url       = patch.linkedinUrl;

  if (Object.keys(update).length === 0) return;

  const { error } = await supabase.from('leads').update(update).eq('id', id);
  if (error) console.error('updateLead error:', error.message);
}

export async function deleteLead(id: string): Promise<void> {
  const { error } = await supabase.from('leads').delete().eq('id', id);
  if (error) console.error('deleteLead error:', error.message);
}

// ---------------------------------------------------------------------------
// Stats (computed from Supabase leads)
// ---------------------------------------------------------------------------

export async function getDashboardStats(): Promise<DashboardStats> {
  const leads = await getLeads();

  const hotLeads = leads.filter((l) => l.hotLeadScore >= 60).length;

  const pipelineValue = leads.reduce((sum, l) => {
    const val = parseInt(l.dealValue.replace(/[₹,\s+]/g, ''), 10);
    return sum + (isNaN(val) ? 0 : val);
  }, 0);

  return {
    totalLeads: leads.length,
    hotLeads,
    pipelineValue,
    auditsGenerated: 0,
    outreachGenerated: 0,
  };
}
