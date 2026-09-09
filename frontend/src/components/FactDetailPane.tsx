'use client';

import React, { useState } from 'react';
import {
  ChevronDown, ChevronRight, HelpCircle, Check, AlertTriangle, Scale,
  GitCompare, BookOpen, Bookmark, FileText
} from 'lucide-react';
import { FactItem, RelationshipItem } from '../lib/types';

interface FactDetailPaneProps {
  selectedFact: FactItem | null;
  selectedRelationship: RelationshipItem | null;
  relatedRelationships: RelationshipItem[];
}

const relPillStyle = (type: string) => {
  if (type === 'corroborated') return 'bg-rel-corroborated-bg text-rel-corroborated-fg border-rel-corroborated-border';
  if (type === 'contradicted') return 'bg-rel-contradiction-bg text-rel-contradiction-fg border-rel-contradiction-border';
  if (type === 'reconciled') return 'bg-rel-reconciled-bg text-rel-reconciled-fg border-rel-reconciled-border';
  return 'bg-rel-uncertain-bg text-rel-uncertain-fg border-rel-uncertain-border';
};

const RelIcon = ({ type }: { type: string }) => {
  if (type === 'corroborated') return <Check className="w-3.5 h-3.5" />;
  if (type === 'contradicted') return <AlertTriangle className="w-3.5 h-3.5" />;
  if (type === 'reconciled') return <Scale className="w-3.5 h-3.5" />;
  return <HelpCircle className="w-3.5 h-3.5" />;
};

export const FactDetailPane: React.FC<FactDetailPaneProps> = ({
  selectedFact,
  selectedRelationship,
  relatedRelationships,
}) => {
  const [evidenceOpen, setEvidenceOpen] = useState(false);
  const [traceOpen, setTraceOpen] = useState(true);

  // --- Empty state ---
  if (!selectedFact && !selectedRelationship) {
    return (
      <main className="flex-1 flex items-center justify-center bg-paper-bg h-[calc(100vh-3.5rem)]">
        <div className="text-center max-w-sm px-6">
          <div className="w-10 h-10 rounded-full bg-paper-surface border border-paper-border flex items-center justify-center mx-auto mb-4 text-paper-slate">
            <BookOpen className="w-5 h-5" />
          </div>
          <h3 className="font-serif text-base font-semibold text-paper-ink">Select a fact or relationship</h3>
          <p className="text-xs text-paper-slate mt-2 leading-relaxed">
            Pick any item from the left panel to inspect its grounded evidence, attribute values, and structured reasoning trace.
          </p>
        </div>
      </main>
    );
  }

  // --- Relationship view ---
  if (selectedRelationship) {
    const { type, confidence, reasoning, fact_a, fact_b } = selectedRelationship;
    const pill = relPillStyle(type);

    return (
      <main className="flex-1 bg-paper-bg overflow-y-auto h-[calc(100vh-3.5rem)]">
        <div className="max-w-3xl mx-auto px-6 py-6">

          {/* Hero header */}
          <div className="mb-6">
            <div className="flex items-center gap-2 mb-2">
              <span className={`inline-flex items-center gap-1.5 text-xs font-mono font-semibold uppercase px-2.5 py-1 rounded border ${pill}`}>
                <RelIcon type={type} />
                {type}
              </span>
              <span className="text-xs font-mono text-paper-slate">
                Confidence: <strong className="text-paper-ink">{(confidence * 100).toFixed(0)}%</strong>
              </span>
            </div>
            <h2 className="font-serif text-2xl font-bold text-paper-ink capitalize leading-tight">
              {fact_a?.attributes?.metric || 'Factual Relationship'}
            </h2>
            <p className="text-xs text-paper-slate mt-1">
              Cross-document comparison · {fact_a?.document_filename} vs {fact_b?.document_filename}
            </p>
          </div>

          {/* Side-by-side value comparison — HERO element */}
          <div className="grid grid-cols-2 gap-3 mb-6">
            {/* Source A */}
            <div className="bg-paper-surface border border-paper-border rounded-lg p-4">
              <div className="text-[10px] font-mono uppercase text-paper-slate mb-2 tracking-wider">
                Source A · {fact_a?.document_filename} · p.{fact_a?.page_number}
              </div>
              <div className="text-2xl font-mono font-bold text-paper-ink mb-1">
                {fact_a?.attributes?.value}
                <span className="text-sm font-normal text-paper-slate ml-1">{fact_a?.attributes?.unit}</span>
              </div>
              {fact_a?.attributes?.period && (
                <div className="text-xs text-paper-slate mb-3">{fact_a.attributes.period}</div>
              )}
              <blockquote className="text-xs font-serif text-paper-slate italic border-l-2 border-paper-accent/40 pl-2.5 leading-relaxed">
                &ldquo;{fact_a?.source_quote}&rdquo;
              </blockquote>
            </div>

            {/* Source B */}
            <div className="bg-paper-surface border border-paper-border rounded-lg p-4">
              <div className="text-[10px] font-mono uppercase text-paper-slate mb-2 tracking-wider">
                Source B · {fact_b?.document_filename} · p.{fact_b?.page_number}
              </div>
              <div className="text-2xl font-mono font-bold text-paper-ink mb-1">
                {fact_b?.attributes?.value}
                <span className="text-sm font-normal text-paper-slate ml-1">{fact_b?.attributes?.unit}</span>
              </div>
              {fact_b?.attributes?.period && (
                <div className="text-xs text-paper-slate mb-3">{fact_b.attributes.period}</div>
              )}
              <blockquote className="text-xs font-serif text-paper-slate italic border-l-2 border-paper-accent/40 pl-2.5 leading-relaxed">
                &ldquo;{fact_b?.source_quote}&rdquo;
              </blockquote>
            </div>
          </div>

          {/* Reasoning — 2-level: summary first, then expandable trace */}
          <div className="bg-paper-surface border border-paper-border rounded-lg overflow-hidden mb-4">
            <button
              onClick={() => setTraceOpen(!traceOpen)}
              className="w-full px-4 py-3 flex items-center justify-between text-left hover:bg-paper-bg/60 transition"
            >
              <div className="flex items-center gap-2">
                <GitCompare className="w-4 h-4 text-paper-accent" />
                <span className="text-xs font-semibold text-paper-ink font-mono uppercase tracking-wider">Reasoning Trace</span>
              </div>
              {traceOpen ? <ChevronDown className="w-4 h-4 text-paper-slate" /> : <ChevronRight className="w-4 h-4 text-paper-slate" />}
            </button>

            {traceOpen && (
              <div className="px-4 pb-4 space-y-4 border-t border-paper-border">
                {/* Level 1: human-readable summary */}
                <div className="pt-4 px-3 py-3 bg-paper-accent-light/40 border border-paper-accent/20 rounded text-xs text-paper-ink leading-relaxed">
                  <strong className="text-paper-accent block mb-1 font-semibold">Conclusion</strong>
                  {reasoning.summary || 'Reasoning evaluation complete.'}
                </div>

                {/* Reconciliation tag */}
                {reasoning.reconciliation_dimension && (
                  <div className={`inline-flex items-center gap-1.5 px-3 py-1 rounded font-mono text-[11px] font-bold ${
                    type === 'uncertain'
                      ? 'bg-rel-uncertain-bg text-rel-uncertain-fg border border-rel-uncertain-border'
                      : 'bg-rel-reconciled-bg text-rel-reconciled-fg border border-rel-reconciled-border'
                  }`}>
                    {type === 'uncertain' ? <HelpCircle className="w-3.5 h-3.5" /> : <Scale className="w-3.5 h-3.5" />}
                    {type === 'uncertain'
                      ? `COMPARABILITY BLOCKED BY ${reasoning.reconciliation_dimension.toUpperCase()}`
                      : `RECONCILED BY ${reasoning.reconciliation_dimension.toUpperCase()}`}
                  </div>
                )}

                {/* Level 2: attribute verification matrix */}
                <div>
                  <h4 className="font-mono text-[11px] uppercase text-paper-slate mb-2 font-medium">Attribute Verification</h4>
                  <div className="grid grid-cols-3 sm:grid-cols-6 gap-2 text-[11px] font-mono">
                    {[
                      { label: 'Entity', val: reasoning.checklist?.entity ?? reasoning.same_entity },
                      { label: 'Metric', val: reasoning.checklist?.metric ?? reasoning.same_metric },
                      { label: 'Period', val: reasoning.checklist?.period ?? reasoning.same_period },
                      { label: 'Unit', val: reasoning.checklist?.unit ?? reasoning.same_unit },
                      { label: 'Scope', val: reasoning.checklist?.scope ?? reasoning.same_scope },
                      { label: 'Qualifier', val: reasoning.checklist?.qualifier ?? reasoning.same_qualifier },
                    ].map(({ label, val }) => (
                      <div key={label} className={`p-2 rounded border text-center ${
                        val === undefined ? 'bg-paper-bg text-paper-slate border-paper-border' :
                        val ? 'bg-rel-corroborated-bg text-rel-corroborated-fg border-rel-corroborated-border' :
                              'bg-rel-contradiction-bg text-rel-contradiction-fg border-rel-contradiction-border'
                      }`}>
                        <div className="text-[10px] mb-0.5">{label}</div>
                        <div className="font-bold">{val === undefined ? '—' : val ? '✓' : '✗'}</div>
                      </div>
                    ))}
                  </div>
                  {reasoning.evidence_confidence !== undefined && (
                    <p className="mt-2 text-[10px] font-mono text-paper-slate">
                      Evidence-derived confidence: <strong className="text-paper-ink">{(reasoning.evidence_confidence * 100).toFixed(0)}%</strong>
                    </p>
                  )}
                </div>

                {/* Level 2b: step log */}
                {reasoning.reasoning_steps && reasoning.reasoning_steps.length > 0 && (
                  <div>
                    <h4 className="font-mono text-[11px] uppercase text-paper-slate mb-2 font-medium">Execution Steps</h4>
                    <ul className="space-y-1 font-mono text-[11px] text-paper-slate bg-paper-bg p-3 rounded border border-paper-border">
                      {reasoning.reasoning_steps.map((step, idx) => (
                        <li key={idx} className="flex items-start gap-2">
                          <span className="text-paper-accent font-bold shrink-0">›</span>
                          <span>{step}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </main>
    );
  }

  // --- Fact view ---
  if (!selectedFact) return null;
  const isUncertain = selectedFact.status === 'uncertain';

  return (
    <main className="flex-1 bg-paper-bg overflow-y-auto h-[calc(100vh-3.5rem)]">
      <div className="max-w-3xl mx-auto px-6 py-6">

        {/* Hero header */}
        <div className="mb-6">
          <div className="flex items-center gap-2 mb-2">
            {isUncertain ? (
              <span className="inline-flex items-center gap-1.5 text-xs font-mono font-semibold uppercase px-2.5 py-1 rounded border bg-rel-uncertain-bg text-rel-uncertain-fg border-rel-uncertain-border">
                <HelpCircle className="w-3.5 h-3.5" />
                Uncertain
              </span>
            ) : (
              <span className="inline-flex items-center gap-1.5 text-xs font-mono font-semibold uppercase px-2.5 py-1 rounded border bg-paper-accent-light text-paper-accent border-paper-accent/20">
                <Check className="w-3.5 h-3.5" />
                Grounded Fact
              </span>
            )}
            <span className="text-xs font-mono text-paper-slate">
              {selectedFact.attributes?.entity || 'Entity'} · p.{selectedFact.page_number}
            </span>
          </div>
          <h2 className="font-serif text-2xl font-bold text-paper-ink capitalize leading-tight">
            {selectedFact.attributes?.metric || 'Factual Claim'}
          </h2>
          <div className="mt-2 text-xl font-mono font-bold text-paper-ink">
            {selectedFact.attributes?.value}
            {selectedFact.attributes?.unit && <span className="text-sm font-normal text-paper-slate ml-1.5">{selectedFact.attributes.unit}</span>}
            {selectedFact.attributes?.period && <span className="text-sm font-normal text-paper-slate ml-2">({selectedFact.attributes.period})</span>}
          </div>
        </div>

        {/* Uncertain notice */}
        {isUncertain && (
          <div className="mb-6 p-4 bg-rel-uncertain-bg border border-rel-uncertain-border rounded-lg text-xs text-rel-uncertain-fg">
            <div className="flex items-center gap-2 font-bold mb-1.5">
              <HelpCircle className="w-4 h-4" />
              Extraction / Reasoning Failure — Handled Honestly
            </div>
            <p className="leading-relaxed">
              {selectedFact.uncertainty_reason || 'This statement contains ambiguous metric referents or ungrounded qualifiers in source text.'}
            </p>
            <div className="mt-2 font-mono text-[10px] bg-paper-surface p-2 rounded border border-paper-border text-paper-slate">
              Action: Marked as <strong>uncertain</strong> rather than forcing a low-confidence normalized fact.
            </div>
          </div>
        )}

        {/* Attributes */}
        <div className="bg-paper-surface border border-paper-border rounded-lg p-4 mb-5">
          <h3 className="font-mono text-xs uppercase tracking-wider text-paper-slate mb-3 font-medium">Extracted Attributes</h3>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5 text-xs">
            {Object.entries(selectedFact.attributes).map(([key, val]) => (
              <div key={key} className="bg-paper-bg p-2 rounded border border-paper-border">
                <span className="font-mono text-[10px] text-paper-slate uppercase block mb-0.5">{key}</span>
                <span className="font-semibold text-paper-ink capitalize">{String(val)}</span>
              </div>
            ))}
          </div>
          <div className="mt-3 pt-3 border-t border-paper-border text-[11px] font-mono text-paper-slate">
            Signature: <code className="bg-paper-bg px-2 py-0.5 rounded text-paper-ink">{selectedFact.normalized_signature}</code>
          </div>
        </div>

        {/* Expandable evidence drawer */}
        <div className="bg-paper-surface border border-paper-border rounded-lg overflow-hidden mb-5">
          <button
            onClick={() => setEvidenceOpen(!evidenceOpen)}
            className="w-full px-4 py-3 flex items-center justify-between text-left hover:bg-paper-bg/60 transition border-b border-paper-border"
          >
            <div className="flex items-center gap-2">
              <Bookmark className="w-4 h-4 text-paper-accent" />
              <span className="text-xs font-semibold text-paper-ink font-mono uppercase tracking-wider">Source Evidence</span>
              <span className="text-[10px] font-mono text-paper-slate">· {selectedFact.document_filename} · p.{selectedFact.page_number}</span>
            </div>
            {evidenceOpen ? <ChevronDown className="w-4 h-4 text-paper-slate" /> : <ChevronRight className="w-4 h-4 text-paper-slate" />}
          </button>
          {evidenceOpen && (
            <div className="px-4 py-4">
              <div className="flex items-center justify-between text-xs text-paper-slate mb-2">
                <span className="flex items-center gap-1.5 font-semibold text-paper-ink">
                  <FileText className="w-3.5 h-3.5 text-paper-accent" />
                  {selectedFact.document_filename}
                </span>
                <span className="font-mono text-[11px] bg-paper-bg px-2 py-0.5 rounded border border-paper-border">
                  Page {selectedFact.page_number}
                </span>
              </div>
              <div className="font-serif text-sm leading-relaxed text-paper-ink bg-paper-bg p-3.5 rounded border border-paper-border my-2">
                <span className="text-paper-slate text-xs font-mono block mb-1">Verbatim Extract:</span>
                &ldquo;<span className="evidence-highlight">{selectedFact.source_quote}</span>&rdquo;
              </div>
              <div className="flex items-center justify-between text-[10px] font-mono text-paper-slate mt-2">
                <span>Char range: {selectedFact.char_start}–{selectedFact.char_end}</span>
                <span className="text-paper-accent font-medium">Grounded &amp; Verified</span>
              </div>
            </div>
          )}
        </div>

        {/* Related relationships */}
        {relatedRelationships.length > 0 && (
          <div>
            <h3 className="font-mono text-xs uppercase tracking-wider text-paper-slate mb-3 font-medium">
              Cross-Document Edges ({relatedRelationships.length})
            </h3>
            <div className="space-y-3">
              {relatedRelationships.map(rel => {
                const otherFact = rel.fact_a_id === selectedFact.id ? rel.fact_b : rel.fact_a;
                const pill = relPillStyle(rel.type);
                return (
                  <div key={rel.id} className="bg-paper-surface border border-paper-border rounded-lg p-4">
                    <div className="flex items-center justify-between mb-2">
                      <span className={`inline-flex items-center gap-1 text-[10px] font-mono font-semibold uppercase px-1.5 py-0.5 rounded border ${pill}`}>
                        <RelIcon type={rel.type} />
                        {rel.type}
                      </span>
                      <span className="text-[10px] text-paper-slate">{otherFact?.document_filename}</span>
                    </div>
                    <blockquote className="text-xs font-serif text-paper-slate italic border-l-2 border-paper-accent/30 pl-2 my-2 leading-relaxed">
                      &ldquo;{otherFact?.source_quote}&rdquo;
                    </blockquote>
                    <p className="text-xs text-paper-ink font-medium mt-2">
                      {rel.reasoning.summary}
                    </p>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </main>
  );
};
