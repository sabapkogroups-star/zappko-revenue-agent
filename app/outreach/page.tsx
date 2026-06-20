'use client';

import { useEffect, useState } from 'react';
import { getLeads, getSelectedLead, setSelectedLead, incrementOutreach } from '@/lib/storage';
import type { Lead } from '@/app/types';

function CopyButton({ text }: { text: string }) {
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

export default function OutreachPage() {
  const [lead, setLead] = useState<Lead | null>(null);
  const [leads, setLeads] = useState<Lead[]>([]);
  const [showPicker, setShowPicker] = useState(false);

  useEffect(() => {
    const selected = getSelectedLead();
    setLead(selected as Lead | null);
    setLeads(getLeads());
  }, []);

  const selectLead = (l: Lead) => {
    setSelectedLead(l);
    setLead(l);
    setShowPicker(false);
  };

  if (!lead) {
    return (
      <div className="p-8 max-w-4xl">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-white">Outreach Generator</h1>
          <p className="text-zinc-500 mt-1 text-sm">Personalised email and WhatsApp drafts based on audit findings.</p>
        </div>
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-10 text-center">
          <p className="text-4xl mb-3">✉️</p>
          <p className="text-zinc-300 font-medium mb-1">No lead selected</p>
          <p className="text-sm text-zinc-500 mb-5">
            Go to Discovery and click <strong className="text-zinc-300">Outreach</strong>, or pick a saved lead below.
          </p>
          {leads.length > 0 && (
            <div className="mt-4 max-w-sm mx-auto text-left border border-zinc-800 rounded-xl overflow-hidden">
              <p className="px-4 py-2 text-xs text-zinc-500 uppercase tracking-wider border-b border-zinc-800 bg-zinc-900">
                Saved Leads
              </p>
              {leads.map((l) => (
                <button
                  key={l.id}
                  onClick={() => selectLead(l)}
                  className="w-full text-left px-4 py-3 border-b border-zinc-800/50 last:border-0 hover:bg-zinc-800/50 transition-colors"
                >
                  <p className="text-sm font-medium text-white">{l.company}</p>
                  <p className="text-xs text-zinc-500">{l.dealValue} · {l.issues.length} issues</p>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    );
  }

  const emailSubject = `Quick question about ${lead.company}`;
  const emailBody    = lead.emailDraft || '';
  const whatsappBody = lead.whatsappDraft || '';

  // ── Validation gates ────────────────────────────────────────────────────
  const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;
  const emailOk =
    !!lead.email &&
    EMAIL_RE.test(lead.email) &&
    lead.emailVerified !== false;

  const waNumber  = (lead.phone || '').replace(/\D/g, '');
  const phoneOk   =
    !!lead.phone &&
    waNumber.length >= 7 &&
    lead.phoneVerified !== false;

  const emailLink    = emailOk
    ? `mailto:${lead.email}?subject=${encodeURIComponent(emailSubject)}&body=${encodeURIComponent(emailBody)}`
    : '#';
  const whatsappLink = phoneOk
    ? `https://wa.me/${waNumber}?text=${encodeURIComponent(whatsappBody)}`
    : '#';

  const handleOpenEmail = (e: React.MouseEvent) => {
    if (!emailOk) { e.preventDefault(); return; }
    incrementOutreach(1);
  };
  const handleOpenWhatsApp = (e: React.MouseEvent) => {
    if (!phoneOk) { e.preventDefault(); return; }
    incrementOutreach(1);
  };

  return (
    <div className="p-8 max-w-4xl">
      {/* Header */}
      <div className="flex items-start justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-white">Outreach Generator</h1>
          <p className="text-zinc-500 mt-1 text-sm">Personalised drafts based on website audit findings.</p>
        </div>
        {leads.length > 1 && (
          <div className="relative">
            <button
              onClick={() => setShowPicker((p) => !p)}
              className="text-sm px-3 py-2 bg-zinc-800 border border-zinc-700 text-zinc-300 hover:text-white rounded-lg transition-colors"
            >
              Switch Lead ↓
            </button>
            {showPicker && (
              <div className="absolute right-0 top-full mt-1 w-64 bg-zinc-900 border border-zinc-800 rounded-xl shadow-2xl z-20 overflow-hidden">
                {leads.map((l) => (
                  <button
                    key={l.id}
                    onClick={() => selectLead(l)}
                    className={`w-full text-left px-4 py-3 border-b border-zinc-800/50 last:border-0 hover:bg-zinc-800 transition-colors ${
                      l.id === lead.id ? 'bg-blue-600/10' : ''
                    }`}
                  >
                    <p className="text-sm font-medium text-white">{l.company}</p>
                    <p className="text-xs text-zinc-500">{l.dealValue}</p>
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Company Details */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 mb-5">
        <h2 className="text-sm font-semibold text-zinc-400 uppercase tracking-wider mb-4">Company Details</h2>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <p className="text-xs text-zinc-600 mb-0.5">Company</p>
            <p className="text-white font-semibold">{lead.company}</p>
          </div>
          <div>
            <p className="text-xs text-zinc-600 mb-0.5">Website</p>
            <a href={lead.website} target="_blank" rel="noopener noreferrer" className="text-blue-400 text-sm hover:text-blue-300 transition-colors">
              {lead.website}
            </a>
          </div>
          <div>
            <p className="text-xs text-zinc-600 mb-0.5">Decision Maker</p>
            <p className="text-white text-sm font-medium">{lead.decisionMaker || '—'}</p>
            {lead.title && (
              <p className="text-blue-400/80 text-xs mt-0.5">{lead.title}</p>
            )}
          </div>
          <div>
            <p className="text-xs text-zinc-600 mb-0.5">Email</p>
            <p className="text-white text-sm">{lead.email || '—'}</p>
          </div>
          <div>
            <p className="text-xs text-zinc-600 mb-0.5">Phone</p>
            <p className="text-white text-sm">{lead.phone || '—'}</p>
          </div>
          <div>
            <p className="text-xs text-zinc-600 mb-0.5">Deal Value</p>
            <p className="text-emerald-400 font-semibold">{lead.dealValue}</p>
          </div>
          {lead.linkedinUrl && (
            <div>
              <p className="text-xs text-zinc-600 mb-0.5">LinkedIn</p>
              <a
                href={lead.linkedinUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-400 text-sm hover:text-blue-300 transition-colors"
              >
                View Profile ↗
              </a>
            </div>
          )}
        </div>

        {lead.issues.length > 0 && (
          <div className="mt-4 pt-4 border-t border-zinc-800">
            <p className="text-xs text-zinc-600 mb-2">Issues Found</p>
            <div className="flex flex-wrap gap-1.5">
              {lead.issues.map((issue, i) => (
                <span key={i} className="text-xs px-2 py-0.5 rounded-md bg-red-500/10 border border-red-500/20 text-red-400">
                  {issue}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Email Draft */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 mb-5">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-semibold text-zinc-400 uppercase tracking-wider">Email Draft</h2>
          <CopyButton text={`Subject: ${emailSubject}\n\n${emailBody}`} />
        </div>
        <div className="mb-2">
          <p className="text-xs text-zinc-600 mb-1">Subject</p>
          <p className="text-white text-sm font-medium">{emailSubject}</p>
        </div>
        <div className="mt-3 bg-zinc-800/50 rounded-lg p-4 border border-zinc-700/50">
          <pre className="whitespace-pre-wrap text-sm text-zinc-200 font-sans leading-relaxed">{emailBody}</pre>
        </div>
      </div>

      {/* WhatsApp Draft */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 mb-6">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-semibold text-zinc-400 uppercase tracking-wider">WhatsApp Draft</h2>
          <CopyButton text={whatsappBody} />
        </div>
        <div className="bg-zinc-800/50 rounded-lg p-4 border border-zinc-700/50">
          <pre className="whitespace-pre-wrap text-sm text-zinc-200 font-sans leading-relaxed">{whatsappBody}</pre>
        </div>
      </div>

      {/* Action Buttons */}
      <div className="flex gap-3 flex-wrap">
        {/* Email button — disabled when no verified email */}
        {emailOk ? (
          <a
            href={emailLink}
            onClick={handleOpenEmail}
            className="flex items-center gap-2 bg-blue-600 hover:bg-blue-500 text-white px-5 py-2.5 rounded-lg text-sm font-semibold transition-colors"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z" />
              <polyline points="22,6 12,13 2,6" />
            </svg>
            Open Email
          </a>
        ) : (
          <div
            title={lead.email ? 'Email failed validation (placeholder or unverified)' : 'No email address found'}
            className="flex items-center gap-2 bg-zinc-800 border border-zinc-700 text-zinc-500 px-5 py-2.5 rounded-lg text-sm font-semibold cursor-not-allowed select-none"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z" />
              <polyline points="22,6 12,13 2,6" />
            </svg>
            Email Unavailable
          </div>
        )}

        {/* WhatsApp button — disabled when no valid phone */}
        {phoneOk ? (
          <a
            href={whatsappLink}
            target="_blank"
            rel="noopener noreferrer"
            onClick={handleOpenWhatsApp}
            className="flex items-center gap-2 bg-emerald-600 hover:bg-emerald-500 text-white px-5 py-2.5 rounded-lg text-sm font-semibold transition-colors"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
              <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z" />
            </svg>
            Open WhatsApp
          </a>
        ) : (
          <div
            title={lead.phone ? 'Phone number failed validation (too short or fake)' : 'No phone number found'}
            className="flex items-center gap-2 bg-zinc-800 border border-zinc-700 text-zinc-500 px-5 py-2.5 rounded-lg text-sm font-semibold cursor-not-allowed select-none"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
              <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z" />
            </svg>
            WhatsApp Unavailable
          </div>
        )}
      </div>
    </div>
  );
}
