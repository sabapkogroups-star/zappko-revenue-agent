'use client';

import { useEffect, useState, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import { getLeads, deleteLead, updateLeadStatus, setSelectedLead, patchLead } from '@/lib/storage';
import type { Lead, LeadStatus, FollowUp } from '@/app/types';

const STATUS_OPTIONS: LeadStatus[] = ['new', 'contacted', 'qualified', 'closed'];

const STATUS_STYLES: Record<LeadStatus, string> = {
  new:       'bg-blue-500/15 text-blue-400 border-blue-500/30',
  contacted: 'bg-amber-500/15 text-amber-400 border-amber-500/30',
  qualified: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
  closed:    'bg-purple-500/15 text-purple-400 border-purple-500/30',
};

const FOLLOW_UP_GAPS = [4, 4, 6]; // days between steps

function ScoreChip({ score }: { score: number }) {
  const color =
    score >= 70 ? 'text-emerald-400' : score >= 50 ? 'text-amber-400' : 'text-red-400';
  return <span className={`font-semibold text-sm ${color}`}>{score}</span>;
}

function CopyBtn({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };
  return (
    <button
      onClick={copy}
      className="text-xs px-2.5 py-1 rounded-md bg-zinc-700/50 border border-zinc-700 text-zinc-400 hover:text-white hover:bg-zinc-700 transition-colors font-medium"
    >
      {copied ? '✓ Copied' : 'Copy'}
    </button>
  );
}

// ---------------------------------------------------------------------------
// Follow-Up Modal
// ---------------------------------------------------------------------------

const STEP_LABELS  = ['Email 1', 'Follow-up 1', 'Follow-up 2', 'Final Follow-up'];
const STEP_DAYS    = [0, 4, 8, 14];
const STEP_COLORS  = [
  'bg-blue-600/20 border-blue-500/30 text-blue-300',
  'bg-amber-600/20 border-amber-500/30 text-amber-300',
  'bg-violet-600/20 border-violet-500/30 text-violet-300',
  'bg-red-600/20 border-red-500/30 text-red-300',
];

function addDays(date: Date, days: number): Date {
  const d = new Date(date);
  d.setDate(d.getDate() + days);
  return d;
}

function formatDate(iso: string | undefined): string {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString([], { month: 'short', day: 'numeric' });
}

interface FollowUpModalProps {
  lead: Lead;
  messages: FollowUp[];
  loading: boolean;
  activeIdx: number;
  onSelectIdx: (i: number) => void;
  onMarkSent: (idx: number) => void;
  onClose: () => void;
}

function FollowUpModal({
  lead, messages, loading, activeIdx, onSelectIdx, onMarkSent, onClose,
}: FollowUpModalProps) {
  const sentCount  = lead.followUpCount ?? 0;
  const sentOffset = STEP_DAYS[Math.max(0, sentCount - 1)] ?? 0;

  // Compute absolute schedule dates from when Email 1 was / will be sent
  const email1Date = sentCount > 0
    ? new Date(new Date(lead.lastContactDate!).getTime() - sentOffset * 86400000)
    : new Date();

  const scheduleDates = STEP_DAYS.map((d) => addDays(email1Date, d));

  const active = messages[activeIdx];

  return (
    <div
      className="fixed inset-0 z-50 bg-black/75 flex items-center justify-center p-4"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="bg-zinc-950 border border-zinc-800 rounded-2xl w-full max-w-2xl max-h-[92vh] flex flex-col shadow-2xl">

        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-zinc-800 shrink-0">
          <div>
            <h2 className="text-white font-bold text-base">Follow-Up Sequence</h2>
            <p className="text-zinc-500 text-xs mt-0.5">
              {lead.company}
              {sentCount > 0 && (
                <span className="ml-2 text-emerald-400">{sentCount}/{STEP_LABELS.length} sent</span>
              )}
            </p>
          </div>
          <button
            onClick={onClose}
            className="w-7 h-7 flex items-center justify-center rounded-lg text-zinc-500 hover:text-white hover:bg-zinc-800 transition-colors text-lg leading-none"
          >
            ✕
          </button>
        </div>

        {loading ? (
          <div className="flex-1 flex flex-col items-center justify-center gap-3 p-16">
            <div className="w-8 h-8 border-2 border-zinc-700 border-t-blue-500 rounded-full animate-spin" />
            <p className="text-zinc-400 text-sm">Generating follow-up sequence…</p>
          </div>
        ) : (
          <div className="flex-1 overflow-y-auto flex flex-col min-h-0">

            {/* Step tabs */}
            <div className="px-6 pt-4 pb-0 shrink-0">
              <div className="grid grid-cols-4 gap-2">
                {STEP_LABELS.map((label, i) => {
                  const isSent    = i < sentCount;
                  const isCurrent = i === activeIdx;
                  return (
                    <button
                      key={i}
                      onClick={() => onSelectIdx(i)}
                      className={`relative px-2 py-2 rounded-lg border text-xs font-medium transition-all text-center ${
                        isCurrent
                          ? STEP_COLORS[i]
                          : isSent
                          ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400'
                          : 'bg-zinc-900 border-zinc-800 text-zinc-500 hover:text-zinc-300 hover:border-zinc-700'
                      }`}
                    >
                      {isSent && !isCurrent && (
                        <span className="absolute -top-1.5 -right-1.5 w-4 h-4 bg-emerald-500 rounded-full text-white text-[9px] flex items-center justify-center">✓</span>
                      )}
                      <span className="block truncate">{label}</span>
                      <span className="block text-[10px] opacity-60 mt-0.5">Day {STEP_DAYS[i]}</span>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Message body */}
            {active ? (
              <div className="flex-1 px-6 py-4 space-y-3">
                {/* Subject */}
                <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4">
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="text-xs text-zinc-500 font-medium uppercase tracking-wider">Subject</span>
                    <CopyBtn text={active.subject} />
                  </div>
                  <p className="text-white text-sm font-semibold">{active.subject}</p>
                </div>

                {/* Body */}
                <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs text-zinc-500 font-medium uppercase tracking-wider">Message</span>
                    <CopyBtn text={`Subject: ${active.subject}\n\n${active.body}`} />
                  </div>
                  <pre className="whitespace-pre-wrap text-sm text-zinc-200 font-sans leading-relaxed">
                    {active.body}
                  </pre>
                </div>

                {/* Mark Sent */}
                <div className="flex items-center justify-between pt-1">
                  <div className="flex items-center gap-2">
                    {activeIdx < sentCount ? (
                      <span className="flex items-center gap-1.5 text-xs text-emerald-400 font-medium">
                        <span className="w-4 h-4 bg-emerald-500/20 border border-emerald-500/30 rounded-full flex items-center justify-center text-[9px]">✓</span>
                        Sent {formatDate(
                          activeIdx === sentCount - 1
                            ? lead.lastContactDate
                            : scheduleDates[activeIdx].toISOString()
                        )}
                      </span>
                    ) : activeIdx === sentCount ? (
                      <button
                        onClick={() => onMarkSent(activeIdx)}
                        className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold rounded-lg transition-colors"
                      >
                        ✓ Mark as Sent
                      </button>
                    ) : (
                      <span className="text-xs text-zinc-600">
                        Send after completing previous steps
                      </span>
                    )}
                  </div>
                  {activeIdx < STEP_LABELS.length - 1 && activeIdx === sentCount - 1 && (
                    <span className="text-xs text-zinc-500">
                      Next follow-up: <span className="text-zinc-300">{formatDate(scheduleDates[activeIdx + 1].toISOString())}</span>
                    </span>
                  )}
                </div>
              </div>
            ) : (
              <div className="flex-1 flex items-center justify-center p-8">
                <p className="text-zinc-600 text-sm">No messages generated yet.</p>
              </div>
            )}

            {/* Schedule footer */}
            <div className="px-6 py-4 border-t border-zinc-800/60 shrink-0">
              <p className="text-xs text-zinc-600 mb-2 uppercase tracking-wider font-medium">Send Schedule</p>
              <div className="grid grid-cols-4 gap-2">
                {STEP_LABELS.map((label, i) => {
                  const isSent = i < sentCount;
                  const dateStr = scheduleDates[i]
                    ? scheduleDates[i].toLocaleDateString([], { month: 'short', day: 'numeric' })
                    : '—';
                  return (
                    <div key={i} className="text-center">
                      <p className={`text-[10px] font-medium ${isSent ? 'text-emerald-400' : i === sentCount ? 'text-zinc-300' : 'text-zinc-600'}`}>
                        {label}
                      </p>
                      <p className={`text-xs tabular-nums mt-0.5 ${isSent ? 'text-emerald-400/70' : i === sentCount ? 'text-zinc-400' : 'text-zinc-700'}`}>
                        {dateStr}
                      </p>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Leads page
// ---------------------------------------------------------------------------

type Toast = { id: number; message: string; type: 'success' | 'error' };

export default function LeadsPage() {
  const router = useRouter();
  const [leads, setLeads] = useState<Lead[]>([]);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<LeadStatus | 'all'>('all');
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);
  const [toasts, setToasts] = useState<Toast[]>([]);

  const [proposalLoading, setProposalLoading] = useState<Set<string>>(new Set());

  // Follow-up modal state
  const [followUpLead, setFollowUpLead] = useState<Lead | null>(null);
  const [followUpMessages, setFollowUpMessages] = useState<FollowUp[]>([]);
  const [followUpLoading, setFollowUpLoading] = useState(false);
  const [activeFollowUpIdx, setActiveFollowUpIdx] = useState(0);

  const reload = () => setLeads(getLeads());

  useEffect(() => { reload(); }, []);

  const addToast = (message: string, type: 'success' | 'error') => {
    const id = Date.now();
    setToasts((prev) => [...prev, { id, message, type }]);
    setTimeout(() => setToasts((prev) => prev.filter((t) => t.id !== id)), 3000);
  };

  const filtered = useMemo(() => {
    return leads.filter((l) => {
      const matchSearch =
        search === '' ||
        l.company.toLowerCase().includes(search.toLowerCase()) ||
        (l.city ?? '').toLowerCase().includes(search.toLowerCase()) ||
        (l.industry ?? '').toLowerCase().includes(search.toLowerCase());
      const matchStatus = statusFilter === 'all' || l.status === statusFilter;
      return matchSearch && matchStatus;
    });
  }, [leads, search, statusFilter]);

  const handleStatusChange = (id: string, status: LeadStatus) => {
    updateLeadStatus(id, status);
    reload();
  };

  const handleDelete = (id: string) => {
    if (deleteConfirm === id) {
      deleteLead(id);
      setDeleteConfirm(null);
      reload();
    } else {
      setDeleteConfirm(id);
      setTimeout(() => setDeleteConfirm(null), 3000);
    }
  };

  const handleOutreach = (lead: Lead) => {
    setSelectedLead(lead);
    router.push('/outreach');
  };

  const handleDownloadProposal = async (lead: Lead) => {
    if (proposalLoading.has(lead.id)) return;
    setProposalLoading((prev) => new Set(prev).add(lead.id));
    try {
      const res = await fetch('http://127.0.0.1:8000/proposal-pdf', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(lead),
      });
      if (!res.ok) throw new Error(`Server error ${res.status}`);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `zappko-proposal-${lead.company.toLowerCase().replace(/\s+/g, '-')}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      addToast('Proposal generation failed — is the backend running?', 'error');
    } finally {
      setProposalLoading((prev) => { const s = new Set(prev); s.delete(lead.id); return s; });
    }
  };

  const handleGenerateFollowUps = async (lead: Lead) => {
    setFollowUpLead(lead);
    setActiveFollowUpIdx(lead.followUpCount ?? 0);

    // Use cached messages if available
    if (lead.followUps?.length) {
      setFollowUpMessages(lead.followUps);
      return;
    }

    setFollowUpLoading(true);
    try {
      const res = await fetch('http://127.0.0.1:8000/follow-ups', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(lead),
      });
      if (!res.ok) throw new Error(`Server error ${res.status}`);
      const data = await res.json();
      const messages: FollowUp[] = data.followUps;

      patchLead(lead.id, { followUps: messages });
      setFollowUpMessages(messages);
      reload();
    } catch {
      addToast('Failed to generate follow-ups — is the backend running?', 'error');
      setFollowUpLead(null);
    } finally {
      setFollowUpLoading(false);
    }
  };

  const handleMarkSent = (msgIndex: number) => {
    if (!followUpLead) return;

    const today = new Date();
    const nextGap = FOLLOW_UP_GAPS[msgIndex];
    const nextDate = nextGap
      ? new Date(today.getTime() + nextGap * 86400000).toISOString()
      : undefined;

    const patch: Partial<Lead> = {
      followUpCount: msgIndex + 1,
      lastContactDate: today.toISOString(),
      ...(nextDate ? { nextFollowUpDate: nextDate } : { nextFollowUpDate: undefined }),
    };

    patchLead(followUpLead.id, patch);
    const updatedLead = { ...followUpLead, ...patch };
    setFollowUpLead(updatedLead);

    const nextIdx = msgIndex + 1;
    if (nextIdx < STEP_LABELS.length) {
      setActiveFollowUpIdx(nextIdx);
    }

    addToast(`${STEP_LABELS[msgIndex]} marked as sent`, 'success');
    reload();
  };

  const counts = useMemo(() => {
    const c: Record<string, number> = { all: leads.length };
    STATUS_OPTIONS.forEach((s) => { c[s] = leads.filter((l) => l.status === s).length; });
    return c;
  }, [leads]);

  const isFollowUpDue = (lead: Lead) => {
    if (!lead.nextFollowUpDate) return false;
    return new Date(lead.nextFollowUpDate) <= new Date();
  };

  const followUpButtonLabel = (lead: Lead) => {
    const count = lead.followUpCount ?? 0;
    if (count === 0) return 'Follow-Ups';
    if (count >= STEP_LABELS.length) return 'Sequence ✓';
    return `Follow-Ups (${count}/${STEP_LABELS.length})`;
  };

  return (
    <div className="p-8 max-w-full">
      {/* Toasts */}
      <div className="fixed top-4 right-4 z-40 flex flex-col gap-2 pointer-events-none">
        {toasts.map((t) => (
          <div
            key={t.id}
            className={`px-4 py-2.5 rounded-lg shadow-xl text-sm font-medium border pointer-events-auto ${
              t.type === 'success'
                ? 'bg-emerald-900/90 border-emerald-700 text-emerald-200'
                : 'bg-red-900/90 border-red-700 text-red-200'
            }`}
          >
            {t.message}
          </div>
        ))}
      </div>

      {/* Follow-Up Modal */}
      {followUpLead && (
        <FollowUpModal
          lead={followUpLead}
          messages={followUpMessages}
          loading={followUpLoading}
          activeIdx={activeFollowUpIdx}
          onSelectIdx={setActiveFollowUpIdx}
          onMarkSent={handleMarkSent}
          onClose={() => { setFollowUpLead(null); setFollowUpMessages([]); }}
        />
      )}

      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-white">Leads Pipeline</h1>
        <p className="text-zinc-500 mt-1 text-sm">Manage saved leads, track status, and run follow-up sequences.</p>
      </div>

      {/* Controls */}
      <div className="flex flex-col sm:flex-row gap-3 mb-5">
        <div className="relative flex-1">
          <span className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" />
            </svg>
          </span>
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by company, city or industry…"
            className="w-full bg-zinc-900 border border-zinc-800 rounded-lg pl-9 pr-4 py-2.5 text-sm text-white placeholder-zinc-600 focus:outline-none focus:border-blue-500 transition-colors"
          />
        </div>
        <div className="flex gap-1 bg-zinc-900 border border-zinc-800 rounded-lg p-1">
          {(['all', ...STATUS_OPTIONS] as const).map((s) => (
            <button
              key={s}
              onClick={() => setStatusFilter(s)}
              className={`px-3 py-1.5 rounded-md text-xs font-medium capitalize transition-colors ${
                statusFilter === s
                  ? 'bg-blue-600 text-white'
                  : 'text-zinc-400 hover:text-white hover:bg-zinc-800'
              }`}
            >
              {s} {counts[s] > 0 && <span className="ml-0.5 opacity-70">({counts[s]})</span>}
            </button>
          ))}
        </div>
      </div>

      {/* Table */}
      {filtered.length === 0 ? (
        <div className="text-center py-20 bg-zinc-900 border border-zinc-800 rounded-xl">
          <p className="text-4xl mb-3">👥</p>
          <p className="text-zinc-400 font-medium">
            {leads.length === 0 ? 'No leads saved yet' : 'No leads match your filter'}
          </p>
          <p className="text-xs text-zinc-600 mt-1">
            {leads.length === 0 ? 'Run Discovery to find and save leads.' : 'Try a different search or status filter.'}
          </p>
        </div>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-zinc-800">
          <table className="w-full text-sm min-w-300">
            <thead>
              <tr className="bg-zinc-900 border-b border-zinc-800">
                <th className="text-left px-4 py-3 text-xs text-zinc-500 font-medium uppercase tracking-wider">Company</th>
                <th className="text-left px-4 py-3 text-xs text-zinc-500 font-medium uppercase tracking-wider">Contact</th>
                <th className="text-left px-4 py-3 text-xs text-zinc-500 font-medium uppercase tracking-wider">Web Score</th>
                <th className="text-left px-4 py-3 text-xs text-zinc-500 font-medium uppercase tracking-wider">Deal Value</th>
                <th className="text-left px-4 py-3 text-xs text-zinc-500 font-medium uppercase tracking-wider">Status</th>
                <th className="text-left px-4 py-3 text-xs text-zinc-500 font-medium uppercase tracking-wider">Follow-ups</th>
                <th className="text-left px-4 py-3 text-xs text-zinc-500 font-medium uppercase tracking-wider">Actions</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((lead) => (
                <tr key={lead.id} className="border-b border-zinc-800/60 hover:bg-zinc-800/20 transition-colors">
                  {/* Company */}
                  <td className="px-4 py-3.5">
                    <div className="flex items-center gap-2">
                      <p className="font-semibold text-white">{lead.company}</p>
                      {isFollowUpDue(lead) && (
                        <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-amber-500/15 border border-amber-500/30 text-amber-400 font-bold whitespace-nowrap">
                          Due
                        </span>
                      )}
                    </div>
                    <a
                      href={lead.website}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs text-blue-400 hover:text-blue-300 transition-colors"
                    >
                      {lead.website.replace('https://', '')}
                    </a>
                  </td>
                  {/* Contact */}
                  <td className="px-4 py-3.5">
                    {lead.decisionMaker ? (
                      <>
                        <p className="text-white text-xs font-semibold">{lead.decisionMaker}</p>
                        {lead.title && <p className="text-blue-400/80 text-xs">{lead.title}</p>}
                      </>
                    ) : (
                      <p className="text-zinc-600 text-xs">—</p>
                    )}
                    {lead.email && <p className="text-zinc-500 text-xs mt-0.5">{lead.email}</p>}
                    {lead.phone && <p className="text-zinc-500 text-xs">{lead.phone}</p>}
                    {lead.linkedinUrl && (
                      <a href={lead.linkedinUrl} target="_blank" rel="noopener noreferrer" className="text-xs text-blue-400 hover:text-blue-300">
                        LinkedIn ↗
                      </a>
                    )}
                  </td>
                  {/* Web Score */}
                  <td className="px-4 py-3.5">
                    <ScoreChip score={lead.websiteScore} />
                  </td>
                  {/* Deal Value */}
                  <td className="px-4 py-3.5 text-emerald-400 font-semibold">{lead.dealValue}</td>
                  {/* Status */}
                  <td className="px-4 py-3.5">
                    <select
                      value={lead.status}
                      onChange={(e) => handleStatusChange(lead.id, e.target.value as LeadStatus)}
                      className={`text-xs px-2 py-1 rounded-md border font-medium capitalize bg-transparent cursor-pointer focus:outline-none ${STATUS_STYLES[lead.status]}`}
                    >
                      {STATUS_OPTIONS.map((s) => (
                        <option key={s} value={s} className="bg-zinc-900 text-white capitalize">{s}</option>
                      ))}
                    </select>
                  </td>
                  {/* Follow-ups */}
                  <td className="px-4 py-3.5">
                    {(lead.followUpCount ?? 0) > 0 ? (
                      <div>
                        <div className="flex gap-1 mb-1">
                          {STEP_LABELS.map((_, i) => (
                            <div
                              key={i}
                              className={`w-4 h-1.5 rounded-full ${
                                i < (lead.followUpCount ?? 0) ? 'bg-emerald-400' : 'bg-zinc-700'
                              }`}
                            />
                          ))}
                        </div>
                        <p className="text-xs text-zinc-500">
                          {(lead.followUpCount ?? 0) >= STEP_LABELS.length
                            ? <span className="text-emerald-400">Sequence complete</span>
                            : lead.nextFollowUpDate
                            ? <>Next: <span className={isFollowUpDue(lead) ? 'text-amber-400 font-medium' : 'text-zinc-400'}>{formatDate(lead.nextFollowUpDate)}</span></>
                            : `${lead.followUpCount}/${STEP_LABELS.length} sent`
                          }
                        </p>
                      </div>
                    ) : (
                      <span className="text-zinc-700 text-xs">Not started</span>
                    )}
                  </td>
                  {/* Actions */}
                  <td className="px-4 py-3.5">
                    <div className="flex flex-col gap-1.5">
                      <button
                        onClick={() => handleOutreach(lead)}
                        className="text-xs px-3 py-1.5 rounded-md bg-blue-600/20 border border-blue-600/30 text-blue-300 hover:bg-blue-600/30 transition-colors font-medium"
                      >
                        Outreach
                      </button>
                      <button
                        onClick={() => handleDownloadProposal(lead)}
                        disabled={proposalLoading.has(lead.id)}
                        className="text-xs px-3 py-1.5 rounded-md bg-amber-600/20 border border-amber-600/30 text-amber-300 hover:bg-amber-600/30 disabled:opacity-40 disabled:cursor-not-allowed transition-colors font-medium flex items-center gap-1"
                      >
                        {proposalLoading.has(lead.id) ? (
                          <>
                            <span className="inline-block w-2.5 h-2.5 border border-amber-400/40 border-t-amber-300 rounded-full animate-spin" />
                            Generating…
                          </>
                        ) : '↓ Proposal'}
                      </button>
                      <button
                        onClick={() => handleGenerateFollowUps(lead)}
                        className={`text-xs px-3 py-1.5 rounded-md border transition-colors font-medium ${
                          (lead.followUpCount ?? 0) >= STEP_LABELS.length
                            ? 'bg-emerald-600/10 border-emerald-600/20 text-emerald-500'
                            : (lead.followUpCount ?? 0) > 0
                            ? 'bg-amber-600/20 border-amber-600/30 text-amber-300 hover:bg-amber-600/30'
                            : 'bg-violet-600/20 border-violet-600/30 text-violet-300 hover:bg-violet-600/30'
                        }`}
                      >
                        {followUpButtonLabel(lead)}
                      </button>
                      <button
                        onClick={() => handleDelete(lead.id)}
                        className={`text-xs px-3 py-1.5 rounded-md border transition-colors font-medium ${
                          deleteConfirm === lead.id
                            ? 'bg-red-600 border-red-500 text-white'
                            : 'bg-red-600/10 border-red-600/20 text-red-400 hover:bg-red-600/20'
                        }`}
                      >
                        {deleteConfirm === lead.id ? 'Confirm?' : 'Delete'}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
