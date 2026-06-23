'use client';

import { useEffect, useState, useMemo } from 'react';
import { getLeads, updateLead, deleteLead } from '@/lib/lead-service';
import { setSelectedLead } from '@/lib/storage';
import { useRouter } from 'next/navigation';
import type { Lead, LeadStatus } from '@/app/types';

const STAGES: { status: LeadStatus; label: string; color: string; headerBg: string; dotColor: string }[] = [
  { status: 'new',       label: 'New Leads',   color: 'border-blue-500/30',    headerBg: 'bg-blue-500/10',    dotColor: 'bg-blue-500' },
  { status: 'contacted', label: 'Contacted',   color: 'border-amber-500/30',   headerBg: 'bg-amber-500/10',   dotColor: 'bg-amber-500' },
  { status: 'qualified', label: 'Qualified',   color: 'border-emerald-500/30', headerBg: 'bg-emerald-500/10', dotColor: 'bg-emerald-500' },
  { status: 'closed',    label: 'Closed',      color: 'border-purple-500/30',  headerBg: 'bg-purple-500/10',  dotColor: 'bg-purple-500' },
];

function parseDeal(dv: string): number {
  const nums = dv.replace(/,/g, '').match(/\d+/);
  return nums ? parseInt(nums[0], 10) : 0;
}

function formatDeal(v: number): string {
  if (v >= 100000) return `₹${(v / 100000).toFixed(1)}L`;
  if (v >= 1000) return `₹${(v / 1000).toFixed(0)}K`;
  return `₹${v}`;
}

function isFollowUpDue(lead: Lead): boolean {
  if (!lead.nextFollowUpDate) return false;
  return new Date(lead.nextFollowUpDate) <= new Date();
}

type Toast = { id: number; message: string; type: 'success' | 'error' };

interface LeadCardProps {
  lead: Lead;
  onStatusChange: (id: string, s: LeadStatus) => void;
  onDelete: (id: string) => void;
  onOutreach: (lead: Lead) => void;
  isDragging: boolean;
  onDragStart: () => void;
  onDragEnd: () => void;
}

function LeadCard({ lead, onStatusChange, onDelete, onOutreach, isDragging, onDragStart, onDragEnd }: LeadCardProps) {
  const [confirmDelete, setConfirmDelete] = useState(false);

  const scoreColor = lead.hotLeadScore >= 70 ? 'text-red-400' : lead.hotLeadScore >= 50 ? 'text-amber-400' : 'text-zinc-400';
  const stageIdx = STAGES.findIndex((s) => s.status === lead.status);

  return (
    <div
      draggable
      onDragStart={onDragStart}
      onDragEnd={onDragEnd}
      className={`bg-zinc-900 border border-zinc-800 rounded-xl p-4 cursor-grab active:cursor-grabbing transition-all duration-150 select-none ${
        isDragging ? 'opacity-40 scale-95' : 'hover:border-zinc-700 hover:shadow-lg hover:shadow-black/30'
      }`}
    >
      {/* Company + badges */}
      <div className="flex items-start justify-between gap-2 mb-3">
        <div className="min-w-0">
          <p className="font-semibold text-white text-sm leading-snug truncate">{lead.company}</p>
          <a
            href={lead.website}
            target="_blank"
            rel="noopener noreferrer"
            className="text-[11px] text-blue-400 hover:text-blue-300 transition-colors truncate block max-w-40"
            onClick={(e) => e.stopPropagation()}
          >
            {lead.website.replace('https://', '').replace('http://', '')}
          </a>
        </div>
        <div className="flex items-center gap-1.5 shrink-0">
          {isFollowUpDue(lead) && (
            <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-amber-500/15 border border-amber-500/30 text-amber-400 font-bold">
              DUE
            </span>
          )}
          {lead.hotLeadScore >= 60 && (
            <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-red-500/15 border border-red-500/30 text-red-400 font-bold">
              HOT
            </span>
          )}
        </div>
      </div>

      {/* Deal value + score */}
      <div className="flex items-center justify-between mb-3">
        <span className="text-emerald-400 font-bold text-sm">{lead.dealValue}</span>
        <span className={`text-xs font-semibold tabular-nums ${scoreColor}`}>Score {lead.hotLeadScore}</span>
      </div>

      {/* Contact */}
      {lead.decisionMaker && (
        <div className="mb-3 pb-3 border-b border-zinc-800/60">
          <p className="text-xs text-white font-medium truncate">{lead.decisionMaker}</p>
          {lead.title && <p className="text-[11px] text-blue-400/80 truncate">{lead.title}</p>}
          {lead.email && <p className="text-[11px] text-zinc-500 truncate">{lead.email}</p>}
        </div>
      )}

      {/* Issues chip */}
      {lead.issues.length > 0 && (
        <div className="flex flex-wrap gap-1 mb-3">
          {lead.issues.slice(0, 2).map((issue, i) => (
            <span key={i} className="text-[10px] px-1.5 py-0.5 rounded bg-red-500/10 border border-red-500/15 text-red-400 truncate max-w-28">
              {issue}
            </span>
          ))}
          {lead.issues.length > 2 && (
            <span className="text-[10px] text-zinc-600">+{lead.issues.length - 2}</span>
          )}
        </div>
      )}

      {/* Follow-up progress */}
      {(lead.followUpCount ?? 0) > 0 && (
        <div className="flex gap-1 mb-3">
          {[0, 1, 2, 3].map((i) => (
            <div
              key={i}
              className={`flex-1 h-1 rounded-full ${i < (lead.followUpCount ?? 0) ? 'bg-emerald-400' : 'bg-zinc-800'}`}
            />
          ))}
        </div>
      )}

      {/* Move to stage */}
      <div className="flex items-center gap-1 mb-2">
        {stageIdx > 0 && (
          <button
            onClick={() => onStatusChange(lead.id, STAGES[stageIdx - 1].status)}
            className="flex-1 text-xs py-2 rounded border border-zinc-700 text-zinc-500 hover:text-zinc-300 hover:border-zinc-600 transition-colors"
          >
            ← {STAGES[stageIdx - 1].label}
          </button>
        )}
        {stageIdx < STAGES.length - 1 && (
          <button
            onClick={() => onStatusChange(lead.id, STAGES[stageIdx + 1].status)}
            className="flex-1 text-xs py-2 rounded border border-zinc-700 text-zinc-500 hover:text-zinc-300 hover:border-zinc-600 transition-colors"
          >
            {STAGES[stageIdx + 1].label} →
          </button>
        )}
      </div>

      {/* Action row */}
      <div className="flex items-center gap-1">
        <button
          onClick={() => onOutreach(lead)}
          className="flex-1 text-xs py-2 rounded bg-blue-600/15 border border-blue-600/25 text-blue-400 hover:bg-blue-600/25 transition-colors font-medium"
        >
          Outreach
        </button>
        <button
          onClick={() => {
            if (confirmDelete) {
              onDelete(lead.id);
            } else {
              setConfirmDelete(true);
              setTimeout(() => setConfirmDelete(false), 2500);
            }
          }}
          className={`flex-1 text-xs py-2 rounded border transition-colors font-medium ${
            confirmDelete
              ? 'bg-red-600 border-red-500 text-white'
              : 'bg-red-500/10 border-red-500/20 text-red-400 hover:bg-red-500/20'
          }`}
        >
          {confirmDelete ? 'Confirm?' : 'Delete'}
        </button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Pipeline page
// ---------------------------------------------------------------------------

export default function PipelinePage() {
  const router = useRouter();
  const [leads, setLeads] = useState<Lead[]>([]);
  const [draggingId, setDraggingId] = useState<string | null>(null);
  const [dragOverStatus, setDragOverStatus] = useState<LeadStatus | null>(null);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [search, setSearch] = useState('');

  const [pageLoading, setPageLoading] = useState(true);

  const reload = async () => {
    const fresh = await getLeads();
    setLeads(fresh);
  };

  useEffect(() => {
    async function init() {
      setPageLoading(true);
      await reload();
      setPageLoading(false);
    }
    init();
  }, []);

  const addToast = (message: string, type: 'success' | 'error') => {
    const id = Date.now();
    setToasts((prev) => [...prev, { id, message, type }]);
    setTimeout(() => setToasts((prev) => prev.filter((t) => t.id !== id)), 3000);
  };

  const filtered = useMemo(() => {
    if (!search.trim()) return leads;
    const q = search.toLowerCase();
    return leads.filter(
      (l) =>
        l.company.toLowerCase().includes(q) ||
        (l.decisionMaker || '').toLowerCase().includes(q) ||
        (l.email || '').toLowerCase().includes(q)
    );
  }, [leads, search]);

  const byStatus = (status: LeadStatus) => filtered.filter((l) => l.status === status);

  const handleStatusChange = async (id: string, status: LeadStatus) => {
    await updateLead(id, { status });
    await reload();
    addToast(`Lead moved to ${status}`, 'success');
  };

  const handleDelete = async (id: string) => {
    await deleteLead(id);
    await reload();
    addToast('Lead deleted', 'success');
  };

  const handleOutreach = (lead: Lead) => {
    setSelectedLead(lead);
    router.push('/outreach');
  };

  const handleDrop = async (status: LeadStatus) => {
    if (draggingId && dragOverStatus === status) {
      const lead = leads.find((l) => l.id === draggingId);
      if (lead && lead.status !== status) {
        await updateLead(draggingId, { status });
        await reload();
        addToast(`Moved to ${status}`, 'success');
      }
    }
    setDraggingId(null);
    setDragOverStatus(null);
  };

  const totalValue = leads.reduce((sum, l) => sum + parseDeal(l.dealValue), 0);
  const hotCount = leads.filter((l) => l.hotLeadScore >= 60).length;

  return (
    <div className="p-4 md:p-8 min-h-screen">
      {/* Toasts */}
      <div className="fixed top-20 md:top-4 right-4 z-40 flex flex-col gap-2 pointer-events-none">
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

      {/* Header */}
      <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-2xl md:text-3xl font-bold text-white">CRM Pipeline</h1>
          <p className="text-zinc-500 mt-1 text-sm">
            {leads.length} leads · {formatDeal(totalValue)} pipeline · {hotCount} hot
          </p>
        </div>
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search leads…"
          className="w-full sm:w-56 bg-zinc-900 border border-zinc-800 rounded-lg px-4 py-2 text-sm text-white placeholder-zinc-600 focus:outline-none focus:border-blue-500 transition-colors"
        />
      </div>

      {/* Loading state */}
      {pageLoading && (
        <div className="flex items-center justify-center py-20 gap-3 text-zinc-500">
          <span className="w-5 h-5 border-2 border-zinc-700 border-t-blue-500 rounded-full animate-spin" />
          <span className="text-sm">Loading pipeline…</span>
        </div>
      )}

      {/* Kanban board */}
      {!pageLoading && <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
        {STAGES.map((stage) => {
          const stageLeads = byStatus(stage.status);
          const stageValue = stageLeads.reduce((sum, l) => sum + parseDeal(l.dealValue), 0);
          const isDragTarget = dragOverStatus === stage.status && draggingId !== null;

          return (
            <div
              key={stage.status}
              onDragOver={(e) => { e.preventDefault(); setDragOverStatus(stage.status); }}
              onDragLeave={(e) => {
                if (!e.currentTarget.contains(e.relatedTarget as Node)) {
                  setDragOverStatus(null);
                }
              }}
              onDrop={() => handleDrop(stage.status)}
              className={`flex flex-col rounded-xl border transition-all duration-150 ${stage.color} ${
                isDragTarget ? 'ring-2 ring-blue-500/40 bg-zinc-900/60' : 'bg-zinc-950/40'
              }`}
            >
              {/* Column header */}
              <div className={`${stage.headerBg} border-b ${stage.color} px-4 py-3 rounded-t-xl`}>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className={`w-2 h-2 rounded-full ${stage.dotColor}`} />
                    <span className="font-semibold text-white text-sm">{stage.label}</span>
                    <span className="text-xs text-zinc-500 bg-zinc-800/60 px-1.5 py-0.5 rounded-full">
                      {stageLeads.length}
                    </span>
                  </div>
                  {stageValue > 0 && (
                    <span className="text-xs text-emerald-400 font-semibold">{formatDeal(stageValue)}</span>
                  )}
                </div>
              </div>

              {/* Cards */}
              <div className={`flex-1 p-3 space-y-3 min-h-32 ${isDragTarget ? 'bg-zinc-900/20' : ''}`}>
                {stageLeads.length === 0 ? (
                  <div className={`flex items-center justify-center h-24 rounded-lg border-2 border-dashed text-zinc-700 text-xs text-center transition-colors ${
                    isDragTarget ? 'border-blue-500/40 text-blue-600' : 'border-zinc-800'
                  }`}>
                    {isDragTarget ? 'Drop here' : 'No leads'}
                  </div>
                ) : (
                  stageLeads.map((lead) => (
                    <LeadCard
                      key={lead.id}
                      lead={lead}
                      onStatusChange={handleStatusChange}
                      onDelete={handleDelete}
                      onOutreach={handleOutreach}
                      isDragging={draggingId === lead.id}
                      onDragStart={() => setDraggingId(lead.id)}
                      onDragEnd={() => { setDraggingId(null); setDragOverStatus(null); }}
                    />
                  ))
                )}
              </div>
            </div>
          );
        })}
      </div>}

      {!pageLoading && leads.length === 0 && (
        <div className="text-center py-20 text-zinc-600">
          <p className="text-5xl mb-4">📋</p>
          <p className="text-lg font-medium text-zinc-400">Pipeline is empty</p>
          <p className="text-sm mt-1">Run Discovery and save leads to see them here.</p>
        </div>
      )}
    </div>
  );
}
