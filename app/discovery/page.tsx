'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { saveLead, setSelectedLead, incrementAudits, incrementOutreach } from '@/lib/storage';
import type { DiscoveryResult, DiscoverySource } from '@/app/types';

// ---------------------------------------------------------------------------
// Badge components
// ---------------------------------------------------------------------------

function ScoreChip({ score }: { score: number }) {
  const color =
    score >= 75
      ? 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20'
      : score >= 50
      ? 'text-amber-400 bg-amber-500/10 border-amber-500/20'
      : 'text-red-400 bg-red-500/10 border-red-500/20';
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded border text-xs font-semibold ${color}`}>
      {score}
    </span>
  );
}

function HotBadge({ score }: { score: number }) {
  if (score >= 70)
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-red-500/15 border border-red-500/30 text-red-400 text-xs font-bold">
        🔥 HOT
      </span>
    );
  if (score >= 50)
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-amber-500/15 border border-amber-500/30 text-amber-400 text-xs font-bold">
        ♨ WARM
      </span>
    );
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-blue-500/15 border border-blue-500/30 text-blue-400 text-xs font-bold">
      ❄ COLD
    </span>
  );
}

const SOURCE_STYLES: Record<string, string> = {
  google:      'bg-blue-500/15 text-blue-400 border-blue-500/25',
  google_maps: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/25',
  directory:   'bg-zinc-700/50 text-zinc-400 border-zinc-600/50',
};
const SOURCE_LABELS: Record<string, string> = {
  google:      'Google',
  google_maps: 'Maps',
  directory:   'Directory',
};

function SourceBadge({ source }: { source?: DiscoverySource }) {
  if (!source) return <span className="text-zinc-600 text-xs">—</span>;
  const cls = SOURCE_STYLES[source] ?? SOURCE_STYLES.directory;
  const label = SOURCE_LABELS[source] ?? source;
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded border text-xs font-semibold ${cls}`}>
      {label}
    </span>
  );
}

function ConfidenceChip({ value }: { value?: number }) {
  if (value === undefined || value === null) return <span className="text-zinc-600 text-xs">—</span>;
  const pct = Math.round(value * 100);
  const color = pct >= 80 ? 'text-emerald-400' : pct >= 65 ? 'text-amber-400' : 'text-zinc-400';
  return <span className={`text-sm font-semibold tabular-nums ${color}`}>{pct}%</span>;
}

function ContactConfidencePip({ value }: { value?: number }) {
  if (!value) return null;
  const pct = Math.round(value * 100);
  const cls =
    pct >= 70
      ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/25'
      : pct >= 40
      ? 'bg-amber-500/15 text-amber-400 border-amber-500/25'
      : 'bg-zinc-700/40 text-zinc-500 border-zinc-600/40';
  return (
    <span className={`inline-flex items-center px-1.5 py-0.5 rounded border text-[10px] font-semibold tabular-nums ${cls}`}>
      {pct}%
    </span>
  );
}

function AuditTimestamp({ ts }: { ts?: string }) {
  if (!ts) return <span className="text-zinc-600 text-xs">—</span>;
  try {
    const d = new Date(ts);
    return (
      <span className="text-xs text-zinc-500 tabular-nums">
        {d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
      </span>
    );
  } catch {
    return <span className="text-zinc-600 text-xs">—</span>;
  }
}

// ---------------------------------------------------------------------------
// Toast
// ---------------------------------------------------------------------------

type Toast = { id: number; message: string; type: 'success' | 'error' };

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function DiscoveryPage() {
  const router = useRouter();

  const [results, setResults] = useState<DiscoveryResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);

  const [industry, setIndustry] = useState('Interior Design');
  const [city, setCity] = useState('Dubai');
  const [country, setCountry] = useState('UAE');
  const [leadCount, setLeadCount] = useState(20);

  const [toasts, setToasts] = useState<Toast[]>([]);
  const [savedIds, setSavedIds] = useState<Set<string>>(new Set());
  const [pdfLoading, setPdfLoading] = useState<Set<string>>(new Set());
  const [proposalLoading, setProposalLoading] = useState<Set<string>>(new Set());

  const addToast = (message: string, type: 'success' | 'error') => {
    const id = Date.now();
    setToasts((prev) => [...prev, { id, message, type }]);
    setTimeout(() => setToasts((prev) => prev.filter((t) => t.id !== id)), 3000);
  };

  const fetchPage = async (pageNum: number, append: boolean) => {
    if (append) setLoadingMore(true);
    else setLoading(true);

    try {
      const response = await fetch('http://127.0.0.1:8000/discover', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ industry, city, country, limit: leadCount, page: pageNum }),
      });
      if (!response.ok) throw new Error(`Server error ${response.status}`);
      const data: DiscoveryResult[] = await response.json();

      if (append) {
        setResults((prev) => {
          const existingDomains = new Set(
            prev.map((r) => {
              try { return new URL(r.website).hostname; } catch { return r.website; }
            })
          );
          const fresh = data.filter((r) => {
            try { return !existingDomains.has(new URL(r.website).hostname); } catch { return true; }
          });
          return [...prev, ...fresh];
        });
      } else {
        setResults(data);
      }

      setPage(pageNum);
      setHasMore(data.length >= leadCount);
      incrementAudits(data.length);
    } catch (error) {
      console.error('Discovery Error:', error);
      addToast('Backend not reachable. Start the FastAPI server.', 'error');
    } finally {
      if (append) setLoadingMore(false);
      else setLoading(false);
    }
  };

  const runDiscovery = () => {
    setSavedIds(new Set());
    fetchPage(1, false);
  };

  const loadMore = () => {
    fetchPage(page + 1, true);
  };

  const handleSaveLead = (lead: DiscoveryResult) => {
    const result = saveLead({ ...lead, industry, city, country });
    if (result.saved) {
      setSavedIds((prev) => new Set(prev).add(lead.company));
      addToast(`${lead.company} saved to pipeline`, 'success');
    } else {
      addToast(result.message, 'error');
    }
  };

  const handleDownloadProposal = async (lead: DiscoveryResult) => {
    if (proposalLoading.has(lead.company)) return;
    setProposalLoading((prev) => new Set(prev).add(lead.company));
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
      setProposalLoading((prev) => { const s = new Set(prev); s.delete(lead.company); return s; });
    }
  };

  const handleOutreach = (lead: DiscoveryResult) => {
    setSelectedLead({ ...lead, industry, city, country } as Parameters<typeof setSelectedLead>[0]);
    incrementOutreach(1);
    router.push('/outreach');
  };

  const handleDownloadPdf = async (lead: DiscoveryResult) => {
    if (pdfLoading.has(lead.company)) return;
    setPdfLoading((prev) => new Set(prev).add(lead.company));
    try {
      const res = await fetch('http://127.0.0.1:8000/audit-pdf', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(lead),
      });
      if (!res.ok) throw new Error(`Server error ${res.status}`);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `zappko-audit-${lead.company.toLowerCase().replace(/\s+/g, '-')}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      addToast('PDF generation failed — is the backend running?', 'error');
    } finally {
      setPdfLoading((prev) => { const s = new Set(prev); s.delete(lead.company); return s; });
    }
  };

  return (
    <div className="p-8 max-w-full">
      {/* Toasts */}
      <div className="fixed top-4 right-4 z-50 flex flex-col gap-2">
        {toasts.map((t) => (
          <div
            key={t.id}
            className={`px-4 py-2.5 rounded-lg shadow-xl text-sm font-medium border ${
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
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-white">Lead Discovery</h1>
        <p className="text-zinc-500 mt-1 text-sm">
          Multi-provider engine: Google → Maps → Directory with automatic failover.
        </p>
      </div>

      {/* Controls */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 mb-6">
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
          <div>
            <label className="block text-xs text-zinc-500 mb-1.5 font-medium">Industry</label>
            <input
              value={industry}
              onChange={(e) => setIndustry(e.target.value)}
              placeholder="e.g. Interior Design"
              className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2.5 text-sm text-white placeholder-zinc-600 focus:outline-none focus:border-blue-500 transition-colors"
            />
          </div>
          <div>
            <label className="block text-xs text-zinc-500 mb-1.5 font-medium">City</label>
            <input
              value={city}
              onChange={(e) => setCity(e.target.value)}
              placeholder="e.g. Dubai"
              className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2.5 text-sm text-white placeholder-zinc-600 focus:outline-none focus:border-blue-500 transition-colors"
            />
          </div>
          <div>
            <label className="block text-xs text-zinc-500 mb-1.5 font-medium">Country</label>
            <input
              value={country}
              onChange={(e) => setCountry(e.target.value)}
              placeholder="e.g. UAE"
              className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2.5 text-sm text-white placeholder-zinc-600 focus:outline-none focus:border-blue-500 transition-colors"
            />
          </div>
          <div>
            <label className="block text-xs text-zinc-500 mb-1.5 font-medium">Per Page</label>
            <input
              type="number"
              min={5}
              max={50}
              value={leadCount}
              onChange={(e) => setLeadCount(Math.min(50, Math.max(5, Number(e.target.value))))}
              className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2.5 text-sm text-white focus:outline-none focus:border-blue-500 transition-colors"
            />
          </div>
        </div>
        <button
          onClick={runDiscovery}
          disabled={loading}
          className="bg-blue-600 hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed px-6 py-2.5 rounded-lg text-sm font-semibold text-white transition-colors flex items-center gap-2"
        >
          {loading ? (
            <>
              <span className="inline-block w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              Discovering…
            </>
          ) : (
            <>🔍 Start Discovery</>
          )}
        </button>
      </div>

      {/* Results */}
      {results.length > 0 && (
        <div>
          <div className="flex items-center justify-between mb-3">
            <p className="text-sm text-zinc-400">
              <span className="text-white font-semibold">{results.length}</span> companies found in{' '}
              <span className="text-white">{city}, {country}</span>
              {page > 1 && <span className="text-zinc-600"> · page {page}</span>}
            </p>
          </div>

          <div className="overflow-x-auto rounded-xl border border-zinc-800">
            <table className="w-full text-sm min-w-350">
              <thead>
                <tr className="bg-zinc-900 border-b border-zinc-800">
                  <th className="text-left px-4 py-3 text-xs text-zinc-500 font-medium uppercase tracking-wider">Company</th>
                  <th className="text-left px-4 py-3 text-xs text-zinc-500 font-medium uppercase tracking-wider">Contact</th>
                  <th className="text-left px-4 py-3 text-xs text-zinc-500 font-medium uppercase tracking-wider">Source</th>
                  <th className="text-left px-4 py-3 text-xs text-zinc-500 font-medium uppercase tracking-wider">Confidence</th>
                  <th className="text-left px-4 py-3 text-xs text-zinc-500 font-medium uppercase tracking-wider">Web Score</th>
                  <th className="text-left px-4 py-3 text-xs text-zinc-500 font-medium uppercase tracking-wider">Opp Score</th>
                  <th className="text-left px-4 py-3 text-xs text-zinc-500 font-medium uppercase tracking-wider">Hot Lead</th>
                  <th className="text-left px-4 py-3 text-xs text-zinc-500 font-medium uppercase tracking-wider">Deal Value</th>
                  <th className="text-left px-4 py-3 text-xs text-zinc-500 font-medium uppercase tracking-wider">Issues</th>
                  <th className="text-left px-4 py-3 text-xs text-zinc-500 font-medium uppercase tracking-wider">Service</th>
                  <th className="text-left px-4 py-3 text-xs text-zinc-500 font-medium uppercase tracking-wider">Last Audit</th>
                  <th className="text-left px-4 py-3 text-xs text-zinc-500 font-medium uppercase tracking-wider">Actions</th>
                </tr>
              </thead>
              <tbody>
                {results.map((lead, i) => (
                  <tr key={i} className="border-b border-zinc-800/60 hover:bg-zinc-800/20 transition-colors">
                    {/* Company */}
                    <td className="px-4 py-3.5">
                      <p className="font-semibold text-white">{lead.company}</p>
                      <a
                        href={lead.website}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-xs text-blue-400 hover:text-blue-300 transition-colors truncate block max-w-40"
                      >
                        {lead.website.replace('https://', '')}
                      </a>
                    </td>
                    {/* Contact */}
                    <td className="px-4 py-3.5 min-w-40">
                      {lead.decisionMaker ? (
                        <div className="flex items-start gap-1.5">
                          <div className="min-w-0">
                            <p className="text-white text-xs font-semibold truncate max-w-36">{lead.decisionMaker}</p>
                            {lead.title && (
                              <p className="text-blue-400/80 text-xs truncate max-w-36">{lead.title}</p>
                            )}
                          </div>
                          <ContactConfidencePip value={lead.contactConfidence} />
                        </div>
                      ) : (
                        <p className="text-zinc-600 text-xs">—</p>
                      )}
                      {lead.email && (
                        <p className="text-zinc-500 text-xs truncate max-w-40 mt-0.5">{lead.email}</p>
                      )}
                      {lead.phone && <p className="text-zinc-500 text-xs">{lead.phone}</p>}
                      {lead.linkedinUrl && (
                        <a
                          href={lead.linkedinUrl}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-xs text-blue-400 hover:text-blue-300 transition-colors"
                        >
                          LinkedIn ↗
                        </a>
                      )}
                    </td>
                    {/* Source */}
                    <td className="px-4 py-3.5">
                      <SourceBadge source={lead.source} />
                    </td>
                    {/* Confidence */}
                    <td className="px-4 py-3.5">
                      <ConfidenceChip value={lead.confidence} />
                    </td>
                    {/* Web Score */}
                    <td className="px-4 py-3.5">
                      <ScoreChip score={lead.websiteScore} />
                    </td>
                    {/* Opp Score */}
                    <td className="px-4 py-3.5">
                      <ScoreChip score={lead.opportunityScore} />
                    </td>
                    {/* Hot Lead */}
                    <td className="px-4 py-3.5">
                      <HotBadge score={lead.hotLeadScore} />
                    </td>
                    {/* Deal Value */}
                    <td className="px-4 py-3.5 text-emerald-400 font-semibold whitespace-nowrap">
                      {lead.dealValue}
                    </td>
                    {/* Issues */}
                    <td className="px-4 py-3.5">
                      <ul className="space-y-0.5">
                        {lead.issues.slice(0, 3).map((issue, j) => (
                          <li key={j} className="text-xs text-zinc-400 flex items-start gap-1">
                            <span className="text-red-400 mt-0.5 shrink-0">▸</span>
                            {issue}
                          </li>
                        ))}
                        {lead.issues.length > 3 && (
                          <li className="text-xs text-zinc-600">+{lead.issues.length - 3} more</li>
                        )}
                      </ul>
                    </td>
                    {/* Service */}
                    <td className="px-4 py-3.5">
                      <ul className="space-y-0.5">
                        {lead.recommendedService.slice(0, 2).map((svc, j) => (
                          <li key={j} className="text-xs text-blue-400 flex items-start gap-1">
                            <span className="shrink-0">✦</span>
                            {svc}
                          </li>
                        ))}
                        {lead.recommendedService.length > 2 && (
                          <li className="text-xs text-zinc-600">+{lead.recommendedService.length - 2} more</li>
                        )}
                      </ul>
                    </td>
                    {/* Last Audit */}
                    <td className="px-4 py-3.5">
                      <AuditTimestamp ts={lead.discoveredAt} />
                    </td>
                    {/* Actions */}
                    <td className="px-4 py-3.5">
                      <div className="flex flex-col gap-1.5">
                        <button
                          onClick={() => handleSaveLead(lead)}
                          disabled={savedIds.has(lead.company)}
                          className="text-xs px-3 py-1.5 rounded-md bg-blue-600/20 border border-blue-600/30 text-blue-300 hover:bg-blue-600/30 disabled:opacity-40 disabled:cursor-not-allowed transition-colors font-medium whitespace-nowrap"
                        >
                          {savedIds.has(lead.company) ? '✓ Saved' : 'Save Lead'}
                        </button>
                        <button
                          onClick={() => handleOutreach(lead)}
                          className="text-xs px-3 py-1.5 rounded-md bg-emerald-600/20 border border-emerald-600/30 text-emerald-300 hover:bg-emerald-600/30 transition-colors font-medium"
                        >
                          Outreach
                        </button>
                        <button
                          onClick={() => handleDownloadPdf(lead)}
                          disabled={pdfLoading.has(lead.company)}
                          className="text-xs px-3 py-1.5 rounded-md bg-violet-600/20 border border-violet-600/30 text-violet-300 hover:bg-violet-600/30 disabled:opacity-40 disabled:cursor-not-allowed transition-colors font-medium flex items-center gap-1"
                        >
                          {pdfLoading.has(lead.company) ? (
                            <>
                              <span className="inline-block w-2.5 h-2.5 border border-violet-400/40 border-t-violet-300 rounded-full animate-spin" />
                              Generating…
                            </>
                          ) : (
                            '↓ Download Audit PDF'
                          )}
                        </button>
                        <button
                          onClick={() => handleDownloadProposal(lead)}
                          disabled={proposalLoading.has(lead.company)}
                          className="text-xs px-3 py-1.5 rounded-md bg-amber-600/20 border border-amber-600/30 text-amber-300 hover:bg-amber-600/30 disabled:opacity-40 disabled:cursor-not-allowed transition-colors font-medium flex items-center gap-1"
                        >
                          {proposalLoading.has(lead.company) ? (
                            <>
                              <span className="inline-block w-2.5 h-2.5 border border-amber-400/40 border-t-amber-300 rounded-full animate-spin" />
                              Generating…
                            </>
                          ) : (
                            '↓ Proposal'
                          )}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Load More */}
          {hasMore && (
            <div className="mt-4 flex justify-center">
              <button
                onClick={loadMore}
                disabled={loadingMore}
                className="flex items-center gap-2 px-6 py-2.5 bg-zinc-800 border border-zinc-700 text-zinc-300 hover:text-white hover:bg-zinc-700 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg text-sm font-medium transition-colors"
              >
                {loadingMore ? (
                  <>
                    <span className="inline-block w-3.5 h-3.5 border-2 border-zinc-500 border-t-white rounded-full animate-spin" />
                    Loading more…
                  </>
                ) : (
                  'Load More ↓'
                )}
              </button>
            </div>
          )}
        </div>
      )}

      {!loading && results.length === 0 && (
        <div className="text-center py-20 text-zinc-600">
          <p className="text-5xl mb-4">🔍</p>
          <p className="text-lg font-medium text-zinc-400">No results yet</p>
          <p className="text-sm mt-1">Enter an industry, city and country, then click Start Discovery.</p>
          <p className="text-xs mt-2 text-zinc-600">
            Engine: Google Search → Google Maps → Directory (automatic failover)
          </p>
        </div>
      )}
    </div>
  );
}
