"use client";

import { useState } from "react";
import { supabase } from "@/lib/supabase";

export default function TestPage() {
  const [result, setResult] = useState<{ ok: boolean; message: string; detail?: string } | null>(null);
  const [loading, setLoading] = useState(false);

  const handleInsert = async () => {
    setLoading(true);
    setResult(null);

    const { error } = await supabase.from("leads").insert({
      company: "Test Company",
      website: "https://test.com",
      status: "new",
      website_score: 0,
      opportunity_score: 0,
      hot_lead_score: 0,
      deal_value: "",
      issues: [],
      recommended_services: [],
    });

    setLoading(false);

    if (error) {
      setResult({
        ok: false,
        message: error.message,
        detail: JSON.stringify(
          { code: error.code, hint: error.hint, details: error.details },
          null,
          2
        ),
      });
    } else {
      setResult({ ok: true, message: "INSERT SUCCESS — row written to Supabase." });
    }
  };

  return (
    <div className="p-8 max-w-xl space-y-4">
      <h1 className="text-lg font-bold">Supabase Write Diagnostics</h1>

      <button
        onClick={handleInsert}
        disabled={loading}
        className="px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-sm font-semibold rounded-lg transition-colors"
      >
        {loading ? "Inserting…" : "Insert Test Lead"}
      </button>

      {result && (
        <div
          className={`rounded-lg border p-4 text-sm font-mono whitespace-pre-wrap ${
            result.ok
              ? "border-green-500 bg-green-950 text-green-300"
              : "border-red-500 bg-red-950 text-red-300"
          }`}
        >
          <p className="font-bold mb-1">{result.ok ? "✓" : "✗"} {result.message}</p>
          {result.detail && <p className="opacity-80 text-xs">{result.detail}</p>}
        </div>
      )}
    </div>
  );
}
