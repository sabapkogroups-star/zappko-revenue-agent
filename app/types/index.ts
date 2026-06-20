export type LeadStatus = 'new' | 'contacted' | 'qualified' | 'closed';

export interface FollowUp {
  label: string;
  dayOffset: number;
  subject: string;
  body: string;
}

export type DiscoverySource = 'google' | 'google_maps' | 'directory' | '';

export interface Lead {
  id: string;
  company: string;
  website: string;
  decisionMaker: string;
  title?: string;
  email: string;
  phone: string;
  linkedinUrl?: string;
  contactConfidence?: number;
  emailVerified?: boolean;
  phoneVerified?: boolean;
  source?: DiscoverySource;
  confidence?: number;
  discoveredAt?: string;
  websiteScore: number;
  opportunityScore: number;
  hotLeadScore: number;
  dealValue: string;
  issues: string[];
  recommendedService: string[];
  emailDraft: string;
  whatsappDraft: string;
  status: LeadStatus;
  savedAt: string;
  industry?: string;
  city?: string;
  country?: string;
  followUps?: FollowUp[];
  followUpCount?: number;
  lastContactDate?: string;
  nextFollowUpDate?: string;
}

export interface DiscoveryResult {
  company: string;
  website: string;
  decisionMaker: string;
  title?: string;
  email: string;
  phone: string;
  linkedinUrl?: string;
  contactConfidence?: number;
  emailVerified?: boolean;
  phoneVerified?: boolean;
  source?: DiscoverySource;
  confidence?: number;
  discoveredAt?: string;
  websiteScore: number;
  opportunityScore: number;
  hotLeadScore: number;
  dealValue: string;
  issues: string[];
  recommendedService: string[];
  emailDraft: string;
  whatsappDraft: string;
}

export interface DashboardStats {
  totalLeads: number;
  hotLeads: number;
  pipelineValue: number;
  auditsGenerated: number;
  outreachGenerated: number;
}

export interface AIRecommendation {
  priority: 'high' | 'medium' | 'low';
  action: string;
  company: string;
  reason: string;
  expectedValue: string;
}

export interface PipelineHealth {
  score: number;
  label: string;
  staleLeads: number;
  dueFollowUps: number;
  hotLeads: number;
}
