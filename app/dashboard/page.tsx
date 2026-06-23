'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { getDashboardStats, getLeads } from '@/lib/lead-service';
import type { AIRecommendation, DashboardStats, Lead, LeadStatus, PipelineHealth } from '@/app/types';

// ---------------------------------------------------------------------------
// Local AI engine (no backend required)
// ---------------------------------------------------------------------------

const STATUS_OPTIONS: LeadStatus[] = ['new', 'contacted', 'qualified', 'closed'];

function parseDeal(dv: string): number {
  const nums = dv.replace(/,/g, '').match(/\d+/);
  return nums ? parseInt(nums[0], 10) : 0;
}

function daysSince(iso: string | undefined): number {
  if (!iso) return 0;
  return (Date.now() - new Date(iso).getTime()) / 86400000;
}

function buildRecommendations(leads: Lead[]): AIRecommendation[] {
  const today = new Date();
  const recs: AIRecommendation[] = [];

  const byStatus = (s: LeadStatus) => leads.filter((l) => l.status === s);

  // 1. Hot uncontacted leads
  byStatus('new')
    .filter((l) => l.hotLeadScore >= 60)
    .sort((a, b) => b.hotLeadScore - a.hotLeadScore)
    .slice(0, 2)
    .forEach((l) =>
      recs.push({
        priority: 'high',
        action: `Contact ${l.company} immediately`,
        company: l.company,
        reason: `Hot lead (score ${l.hotLeadScore}) with zero outreach — highest close probability`,
        expectedValue: l.dealValue,
      })
    );

  // 2. Overdue follow-ups
  leads
    .filter((l) => l.nextFollowUpDate && new Date(l.nextFollowUpDate) <= today)
    .slice(0, 2)
    .forEach((l) => {
      const step = (l.followUpCount ?? 0) + 1;
      recs.push({
        priority: 'high',
        action: `Send follow-up #${step} to ${l.company}`,
        company: l.company,
        reason: 'Overdue follow-up — reply rate drops ~5% per day of delay',
        expectedValue: l.dealValue,
      });
    });

  // 3. Qualified → ready for proposal
  byStatus('qualified')
    .filter((l) => l.opportunityScore >= 50)
    .slice(0, 2)
    .forEach((l) =>
      recs.push({
        priority: 'medium',
        action: `Generate & send proposal to ${l.company}`,
        company: l.company,
        reason: `Qualified with ${l.opportunityScore} opp score — proposal needed to close`,
        expectedValue: l.dealValue,
      })
    );

  // 4. Stale contacted leads (>7 days)
  byStatus('contacted')
    .map((l) => ({ l, days: daysSince(l.lastContactDate || l.savedAt) }))
    .filter(({ days }) => days >= 7)
    .sort((a, b) => b.days - a.days)
    .slice(0, 2)
    .forEach(({ l, days }) => {
      if (recs.some((r) => r.company === l.company)) return;
      recs.push({
        priority: 'medium',
        action: `Re-engage ${l.company} — ${Math.floor(days)}d stale`,
        company: l.company,
        reason: `No contact in ${Math.floor(days)} days — lead going cold`,
        expectedValue: l.dealValue,
      });
    });

  // 5. High-value new leads
  byStatus('new')
    .sort((a, b) => parseDeal(b.dealValue) - parseDeal(a.dealValue))
    .slice(0, 2)
    .forEach((l) => {
      if (recs.some((r) => r.company === l.company)) return;
      recs.push({
        priority: 'low',
        action: `Prepare audit PDF for ${l.company}`,
        company: l.company,
        reason: `High-value deal (${l.dealValue}) — strengthen pitch with audit report`,
        expectedValue: l.dealValue,
      });
    });

  // Dedup + sort + cap
  const seen = new Set<string>();
  const unique = recs.filter((r) => {
    if (seen.has(r.company)) return false;
    seen.add(r.company);
    return true;
  });
  const order: Record<string, number> = { high: 0, medium: 1, low: 2 };
  unique.sort((a, b) => (order[a.priority] ?? 3) - (order[b.priority] ?? 3));
  return unique.slice(0, 5);
}

function buildHealth(leads: Lead[]): PipelineHealth {
  const total = leads.length;
  if (total === 0) return { score: 0, label: 'Empty', staleLeads: 0, dueFollowUps: 0, hotLeads: 0 };

  const today = new Date();
  const hot = leads.filter((l) => l.hotLeadScore >= 60).length;
  const active = leads.filter((l) => ['contacted', 'qualified', 'closed'].includes(l.status)).length;
  const staleLeads = leads.filter(
    (l) => l.status === 'contacted' && daysSince(l.lastContactDate || l.savedAt) >= 7
  ).length;
  const dueFollowUps = leads.filter(
    (l) => l.nextFollowUpDate && new Date(l.nextFollowUpDate) <= today
  ).length;

  const activeRate = (active / total) * 40;
  const hotRate = Math.min(1, hot / total) * 30;
  const stalePenalty = Math.min(30, staleLeads * 5);
  const score = Math.min(100, Math.round(activeRate + hotRate + (30 - stalePenalty)));
  const label = score >= 70 ? 'Healthy' : score >= 40 ? 'At Risk' : 'Critical';

  return { score, label, staleLeads, dueFollowUps, hotLeads: hot };
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function StatCard({
  label, value, sub, accent,
}: {
  label: string; value: string; sub?: string; accent: string;
}) {
  return (
    <div className={`bg-zinc-900 border ${accent} rounded-xl p-5 flex flex-col gap-2`}>
      <p className="text-xs uppercase tracking-widest text-zinc-500 font-medium">{label}</p>
      <p className="text-3xl font-bold text-white">{value}</p>
      {sub && <p className="text-xs text-zinc-500">{sub}</p>}
    </div>
  );
}

const PRIORITY_STYLES: Record<string, string> = {
  high:   'bg-red-500/10 border-red-500/25 text-red-400',
  medium: 'bg-amber-500/10 border-amber-500/25 text-amber-400',
  low:    'bg-blue-500/10 border-blue-500/25 text-blue-400',
};

function RecommendationCard({ rec }: { rec: AIRecommendation }) {
  return (
    <div className="flex items-start gap-3 p-4 bg-zinc-900/60 border border-zinc-800 rounded-xl hover:border-zinc-700 transition-colors">
      <span className={`shrink-0 text-[10px] px-2 py-0.5 rounded-full border font-bold uppercase tracking-wide mt-0.5 ${PRIORITY_STYLES[rec.priority]}`}>
        {rec.priority}
      </span>
      <div className="min-w-0">
        <p className="text-white text-sm font-semibold leading-snug">{rec.action}</p>
        <p className="text-zinc-500 text-xs mt-0.5 leading-relaxed">{rec.reason}</p>
        <p className="text-emerald-400 text-xs font-semibold mt-1">{rec.expectedValue}</p>
      </div>
    </div>
  );
}

function HealthDonut({ health }: { health: PipelineHealth }) {
  const r = 44;
  const circ = 2 * Math.PI * r;
  const offset = circ * (1 - health.score / 100);
  const scoreColor = health.score >= 70 ? '#34d399' : health.score >= 40 ? '#fbbf24' : '#f87171';
  const labelColor = health.score >= 70 ? 'text-emerald-400' : health.score >= 40 ? 'text-amber-400' : 'text-red-400';

  return (
    <div className="flex flex-col items-center gap-4">
      <div className="relative w-28 h-28">
        <svg viewBox="0 0 100 100" className="w-full h-full -rotate-90">
          <circle cx="50" cy="50" r={r} fill="none" stroke="#27272a" strokeWidth="10" />
          <circle
            cx="50" cy="50" r={r}
            fill="none"
            stroke={scoreColor}
            strokeWidth="10"
            strokeDasharray={circ}
            strokeDashoffset={offset}
            strokeLinecap="round"
            className="transition-all duration-700"
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className={`text-2xl font-bold ${labelColor}`}>{health.score}</span>
          <span className="text-[10px] text-zinc-500">/ 100</span>
        </div>
      </div>
      <div className={`text-sm font-bold ${labelColor}`}>{health.label}</div>
      <div className="grid grid-cols-3 gap-3 w-full text-center">
        {[
          { label: 'Hot', value: health.hotLeads, color: 'text-red-400' },
          { label: 'Due', value: health.dueFollowUps, color: 'text-amber-400' },
          { label: 'Stale', value: health.staleLeads, color: 'text-zinc-400' },
        ].map((item) => (
          <div key={item.label}>
            <p className={`text-lg font-bold ${item.color}`}>{item.value}</p>
            <p className="text-[10px] text-zinc-600 uppercase tracking-wider">{item.label}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

const STAGE_BAR_COLORS = ['#3b82f6', '#f59e0b', '#10b981', '#a855f7'];

function PipelineChart({ leads }: { leads: Lead[] }) {
  const data = STATUS_OPTIONS.map((s, i) => {
    const group = leads.filter((l) => l.status === s);
    const value = group.reduce((sum, l) => sum + parseDeal(l.dealValue), 0);
    return { label: s, count: group.length, value, color: STAGE_BAR_COLORS[i] };
  });
  const maxVal = Math.max(...data.map((d) => d.value), 1);

  const fmt = (v: number) => {
    if (v >= 100000) return `₹${(v / 100000).toFixed(1)}L`;
    if (v >= 1000) return `${(v / 1000).toFixed(0)}K`;
    return String(v);
  };

  return (
    <div className="space-y-3">
      {data.map((d) => (
        <div key={d.label}>
          <div className="flex items-center justify-between mb-1">
            <span className="text-xs capitalize text-zinc-400 font-medium">{d.label}</span>
            <span className="text-xs text-zinc-500">{d.count} lead{d.count !== 1 ? 's' : ''} · {fmt(d.value)}</span>
          </div>
          <div className="h-2 bg-zinc-800 rounded-full overflow-hidden">
            <div
              className="h-full rounded-full transition-all duration-500"
              style={{ width: `${(d.value / maxVal) * 100}%`, backgroundColor: d.color }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function Dashboard() {
  const [stats, setStats] = useState<DashboardStats>({
    totalLeads: 0, hotLeads: 0, pipelineValue: 0, auditsGenerated: 0, outreachGenerated: 0,
  });
  const [leads, setLeads] = useState<Lead[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      setLoading(true);
      const [freshLeads, freshStats] = await Promise.all([getLeads(), getDashboardStats()]);
      setLeads(freshLeads);
      setStats(freshStats);
      setLoading(false);
    }
    load();
  }, []);

  const recommendations = useMemo(() => buildRecommendations(leads), [leads]);
  const health = useMemo(() => buildHealth(leads), [leads]);

  const recentLeads = useMemo(
    () => [...leads].sort((a, b) => new Date(b.savedAt).getTime() - new Date(a.savedAt).getTime()).slice(0, 5),
    [leads]
  );

  const dueCount = useMemo(
    () => leads.filter((l) => l.nextFollowUpDate && new Date(l.nextFollowUpDate) <= new Date()).length,
    [leads]
  );

  const qualifiedCount = leads.filter((l) => l.status === 'qualified').length;
  const closedCount = leads.filter((l) => l.status === 'closed').length;

  const formatPipeline = (val: number) => {
    if (val >= 100000) return `₹${(val / 100000).toFixed(1)}L`;
    if (val >= 1000) return `₹${(val / 1000).toFixed(0)}K`;
    return `₹${val}`;
  };

  const STATUS_STYLES: Record<LeadStatus, string> = {
    new:       'bg-blue-500/15 text-blue-400 border-blue-500/30',
    contacted: 'bg-amber-500/15 text-amber-400 border-amber-500/30',
    qualified: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
    closed:    'bg-purple-500/15 text-purple-400 border-purple-500/30',
  };

  return (
    <div className="p-4 md:p-8 max-w-7xl">
      {/* Header */}
      <div className="mb-6 md:mb-8 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-2xl md:text-3xl font-bold text-white">Revenue Command Center</h1>
          <p className="text-zinc-500 mt-1 text-sm">AI-powered pipeline intelligence and sales automation.</p>
        </div>
        <Link
          href="/pipeline"
          className="self-start text-xs px-4 py-2 bg-blue-600/15 border border-blue-600/25 text-blue-400 rounded-lg hover:bg-blue-600/25 transition-colors font-medium whitespace-nowrap"
        >
          CRM Pipeline →
        </Link>
      </div>

      {/* Stats row */}
      <div className={`grid grid-cols-2 lg:grid-cols-6 gap-4 mb-8 transition-opacity duration-300 ${loading ? 'opacity-50 pointer-events-none' : ''}`}>
        <StatCard label="Total Leads" value={String(stats.totalLeads)} sub="In pipeline" accent="border-zinc-800" />
        <StatCard label="Hot Leads" value={String(stats.hotLeads)} sub="Score ≥ 60" accent="border-red-500/30" />
        <StatCard label="Pipeline Value" value={formatPipeline(stats.pipelineValue)} sub="Estimated deals" accent="border-emerald-500/30" />
        <StatCard label="Follow-Ups Due" value={String(dueCount)} sub="Action required" accent={dueCount > 0 ? 'border-amber-500/40' : 'border-zinc-800'} />
        <StatCard label="Qualified" value={String(qualifiedCount)} sub="Ready to close" accent="border-violet-500/30" />
        <StatCard label="Closed" value={String(closedCount)} sub="Won deals" accent="border-emerald-500/30" />
      </div>

      {/* Main grid */}
      <div className="grid lg:grid-cols-3 gap-6 mb-6">

        {/* AI Sales Coach */}
        <div className="lg:col-span-2 bg-zinc-900 border border-zinc-800 rounded-xl overflow-hidden">
          <div className="flex items-center justify-between px-5 py-4 border-b border-zinc-800">
            <div>
              <h2 className="font-semibold text-white flex items-center gap-2">
                <span className="w-5 h-5 bg-blue-600/20 border border-blue-500/30 rounded flex items-center justify-center text-blue-400 text-[10px]">AI</span>
                Sales Coach
              </h2>
              <p className="text-xs text-zinc-500 mt-0.5">Priority actions to accelerate revenue</p>
            </div>
            <Link href="/leads" className="text-xs text-blue-400 hover:text-blue-300 transition-colors">
              View Pipeline →
            </Link>
          </div>
          <div className="p-4">
            {recommendations.length === 0 ? (
              <div className="py-10 text-center">
                <p className="text-zinc-500 text-sm">Add leads to get AI recommendations.</p>
                <Link href="/discovery" className="mt-2 inline-block text-xs text-blue-400 hover:text-blue-300 transition-colors">
                  Start Discovery →
                </Link>
              </div>
            ) : (
              <div className="space-y-2.5">
                {recommendations.map((rec, i) => (
                  <RecommendationCard key={i} rec={rec} />
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Pipeline Health */}
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
          <h2 className="font-semibold text-white mb-5">Pipeline Health</h2>
          <HealthDonut health={health} />
          <div className="mt-5 pt-4 border-t border-zinc-800 space-y-3">
            <p className="text-xs text-zinc-600 uppercase tracking-wider font-medium">By Stage</p>
            <PipelineChart leads={leads} />
          </div>
        </div>
      </div>

      {/* Bottom grid */}
      <div className="grid lg:grid-cols-3 gap-6">

        {/* Recent Leads */}
        <div className="lg:col-span-2 bg-zinc-900 border border-zinc-800 rounded-xl overflow-hidden">
          <div className="flex items-center justify-between px-5 py-4 border-b border-zinc-800">
            <h2 className="font-semibold text-white">Recent Leads</h2>
            <Link href="/leads" className="text-xs text-blue-400 hover:text-blue-300 transition-colors">
              View all →
            </Link>
          </div>
          {recentLeads.length === 0 ? (
            <div className="px-5 py-12 text-center">
              <p className="text-zinc-500 text-sm">No leads yet.</p>
              <Link href="/discovery" className="mt-2 inline-block text-xs text-blue-400 hover:text-blue-300 transition-colors">
                Start Discovery →
              </Link>
            </div>
          ) : (
            <>
              {/* Desktop table */}
              <table className="hidden md:table w-full text-sm">
                <thead>
                  <tr className="border-b border-zinc-800">
                    <th className="text-left px-5 py-3 text-xs text-zinc-500 font-medium uppercase tracking-wider">Company</th>
                    <th className="text-left px-5 py-3 text-xs text-zinc-500 font-medium uppercase tracking-wider">Hot Score</th>
                    <th className="text-left px-5 py-3 text-xs text-zinc-500 font-medium uppercase tracking-wider">Deal</th>
                    <th className="text-left px-5 py-3 text-xs text-zinc-500 font-medium uppercase tracking-wider">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {recentLeads.map((lead) => (
                    <tr key={lead.id} className="border-b border-zinc-800/50 hover:bg-zinc-800/30 transition-colors">
                      <td className="px-5 py-3.5">
                        <p className="font-medium text-white text-sm">{lead.company}</p>
                        <p className="text-xs text-zinc-500 truncate max-w-36">{lead.website.replace('https://', '')}</p>
                      </td>
                      <td className="px-5 py-3.5">
                        <span className={`font-semibold text-sm ${lead.hotLeadScore >= 70 ? 'text-red-400' : lead.hotLeadScore >= 50 ? 'text-amber-400' : 'text-zinc-400'}`}>
                          {lead.hotLeadScore}
                        </span>
                      </td>
                      <td className="px-5 py-3.5 text-emerald-400 font-medium text-sm">{lead.dealValue}</td>
                      <td className="px-5 py-3.5">
                        <span className={`text-xs px-2 py-0.5 rounded-md border font-medium capitalize ${STATUS_STYLES[lead.status]}`}>
                          {lead.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>

              {/* Mobile cards */}
              <div className="md:hidden divide-y divide-zinc-800/60">
                {recentLeads.map((lead) => (
                  <div key={lead.id} className="px-4 py-3.5 hover:bg-zinc-800/20 transition-colors">
                    <div className="flex items-start justify-between gap-2 mb-1.5">
                      <div className="min-w-0">
                        <p className="font-medium text-white text-sm truncate">{lead.company}</p>
                        <p className="text-xs text-zinc-500 truncate">{lead.website.replace('https://', '')}</p>
                      </div>
                      <span className={`shrink-0 text-xs px-2 py-0.5 rounded-md border font-medium capitalize ${STATUS_STYLES[lead.status]}`}>
                        {lead.status}
                      </span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className={`font-semibold text-sm ${lead.hotLeadScore >= 70 ? 'text-red-400' : lead.hotLeadScore >= 50 ? 'text-amber-400' : 'text-zinc-400'}`}>
                        Score {lead.hotLeadScore}
                      </span>
                      <span className="text-emerald-400 font-medium text-sm">{lead.dealValue}</span>
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>

        {/* Quick Actions + Mission */}
        <div className="flex flex-col gap-4">
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
            <h2 className="font-semibold text-white mb-4">Quick Actions</h2>
            <div className="flex flex-col gap-2">
              <Link href="/discovery" className="flex items-center gap-3 p-3 rounded-lg bg-blue-600/10 border border-blue-600/20 hover:bg-blue-600/20 transition-colors text-sm text-blue-300">
                <span>🔍</span> Start New Discovery
              </Link>
              <Link href="/pipeline" className="flex items-center gap-3 p-3 rounded-lg bg-violet-600/10 border border-violet-600/20 hover:bg-violet-600/20 transition-colors text-sm text-violet-300">
                <span>📋</span> CRM Pipeline
              </Link>
              <Link href="/leads" className="flex items-center gap-3 p-3 rounded-lg bg-zinc-800/50 border border-zinc-700 hover:bg-zinc-800 transition-colors text-sm text-zinc-300">
                <span>👥</span> Leads Table
              </Link>
              <Link href="/outreach" className="flex items-center gap-3 p-3 rounded-lg bg-zinc-800/50 border border-zinc-700 hover:bg-zinc-800 transition-colors text-sm text-zinc-300">
                <span>✉️</span> Generate Outreach
              </Link>
            </div>
          </div>

          <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
            <h2 className="font-semibold text-white mb-4">Today&apos;s Mission</h2>
            <ul className="space-y-2.5 text-sm">
              {[
                'Find 50 new companies',
                'Generate 50 outreach messages',
                'Contact 30 prospects',
                'Book 3 meetings',
                'Close 1 deal',
              ].map((task) => (
                <li key={task} className="flex items-center gap-2.5 text-zinc-400">
                  <span className="w-4 h-4 rounded-full border border-zinc-700 flex items-center justify-center shrink-0">
                    <span className="w-1.5 h-1.5 rounded-full bg-zinc-600" />
                  </span>
                  {task}
                </li>
              ))}
            </ul>
          </div>

          {/* Follow-ups due alert */}
          {dueCount > 0 && (
            <div className="bg-amber-500/5 border border-amber-500/25 rounded-xl p-4">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-amber-400 text-sm">⚡</span>
                <p className="text-amber-400 font-semibold text-sm">{dueCount} Follow-Up{dueCount > 1 ? 's' : ''} Due</p>
              </div>
              <p className="text-xs text-zinc-500 mb-3">Send these today to keep momentum.</p>
              <Link href="/leads" className="text-xs text-amber-400 hover:text-amber-300 transition-colors font-medium">
                View Follow-Ups →
              </Link>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
