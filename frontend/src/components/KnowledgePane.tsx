'use client';

import React, { useState, useRef, useEffect } from 'react';
import {
  Search, Check, AlertTriangle, Scale, HelpCircle, Layers,
  GitCompare, FileText, MoreVertical, Trash2, Upload, RotateCcw
} from 'lucide-react';
import { FactItem, RelationshipItem, DocumentItem } from '../lib/types';

interface KnowledgePaneProps {
  facts: FactItem[];
  relationships: RelationshipItem[];
  documents: DocumentItem[];
  selectedFactId: string | null;
  selectedRelationshipId: string | null;
  activeFilter: string;
  onSelectFact: (factId: string) => void;
  onSelectRelationship: (rel: RelationshipItem) => void;
  onFilterChange: (filter: string) => void;
  onDeleteDocument: (doc: DocumentItem) => void;
  onReprocessDocument: (doc: DocumentItem) => void;
  onOpenUpload: () => void;
  width: number;
}

const relTypeConfig: Record<string, { icon: React.FC<any>; pill: string }> = {
  corroborated: { icon: Check,         pill: 'bg-rel-corroborated-bg text-rel-corroborated-fg border-rel-corroborated-border' },
  contradicted: { icon: AlertTriangle, pill: 'bg-rel-contradiction-bg text-rel-contradiction-fg border-rel-contradiction-border' },
  reconciled:   { icon: Scale,         pill: 'bg-rel-reconciled-bg text-rel-reconciled-fg border-rel-reconciled-border' },
  uncertain:    { icon: HelpCircle,    pill: 'bg-rel-uncertain-bg text-rel-uncertain-fg border-rel-uncertain-border' },
};

// Three-dot menu per document row
const DocMenu: React.FC<{ doc: DocumentItem; onDelete: (doc: DocumentItem) => void; onReprocess: (doc: DocumentItem) => void }> = ({ doc, onDelete, onReprocess }) => {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    if (open) document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);

  return (
    <div ref={ref} className="relative shrink-0">
      <button
        onClick={e => { e.stopPropagation(); setOpen(!open); }}
        title="Document options"
        className="p-1 rounded text-paper-slate hover:text-paper-ink hover:bg-paper-border/40 transition opacity-0 group-hover:opacity-100"
      >
        <MoreVertical className="w-3.5 h-3.5" />
      </button>
      {open && (
        <div className="absolute right-0 bottom-full mb-1 w-44 bg-paper-surface border border-paper-border rounded-lg shadow-xl z-50 overflow-hidden">
          {doc.status === 'processing' ? (
            <div className="px-3 py-2 text-[11px] text-paper-slate font-serif italic">
              Processing — cannot delete yet
            </div>
          ) : (
            <>
            {doc.status === 'failed' && (
              <button
                onClick={e => { e.stopPropagation(); setOpen(false); onReprocess(doc); }}
                className="w-full text-left px-3 py-2 text-xs flex items-center gap-2 text-paper-accent hover:bg-paper-accent-light transition"
              >
                <RotateCcw className="w-3.5 h-3.5" />
                Reprocess document
              </button>
            )}
            <button
              onClick={e => { e.stopPropagation(); setOpen(false); onDelete(doc); }}
              className="w-full text-left px-3 py-2 text-xs flex items-center gap-2 text-rel-contradiction-fg hover:bg-rel-contradiction-bg transition"
            >
              <Trash2 className="w-3.5 h-3.5" />
              Delete document
            </button>
            </>
          )}
        </div>
      )}
    </div>
  );
};

export const KnowledgePane: React.FC<KnowledgePaneProps> = ({
  facts,
  relationships,
  documents,
  selectedFactId,
  selectedRelationshipId,
  activeFilter,
  onSelectFact,
  onSelectRelationship,
  onFilterChange,
  onDeleteDocument,
  onReprocessDocument,
  onOpenUpload,
  width,
}) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [showDocs, setShowDocs] = useState(true);

  // ─── COUNTS ──────────────────────────────────────────────────────────────
  // "All Facts" tab → fact count  
  // Relationship tabs (corroborated/contradicted/reconciled/uncertain) → relationship count
  // Uncertain tab → ONLY relationship count (uncertain relationships are the primary view;
  //   uncertain facts are already marked inline in the All Facts list)
  const filterTabs = [
    {
      id: 'all', label: 'All', icon: Layers,
      count: facts.length,
      unit: 'facts',
    },
    {
      id: 'corroborated', label: 'Corroborated', icon: Check,
      count: relationships.filter(r => r.type === 'corroborated').length,
      unit: 'rels',
    },
    {
      id: 'contradicted', label: 'Contradicted', icon: AlertTriangle,
      count: relationships.filter(r => r.type === 'contradicted').length,
      unit: 'rels',
    },
    {
      id: 'reconciled', label: 'Reconciled', icon: Scale,
      count: relationships.filter(r => r.type === 'reconciled').length,
      unit: 'rels',
    },
    {
      id: 'uncertain', label: 'Uncertain', icon: HelpCircle,
      count: relationships.filter(r => r.type === 'uncertain').length,
      unit: 'rels',
    },
  ];

  // ─── VIEW MODE ───────────────────────────────────────────────────────────
  // All four relationship tabs (including uncertain) show RELATIONSHIPS.
  // Only 'all' shows facts.
  const isRelView = activeFilter !== 'all';

  // ─── FILTERED LISTS ──────────────────────────────────────────────────────
  const q = searchTerm.toLowerCase();

  const filteredFacts = facts.filter(f => {
    const textMatch = !q ||
      f.source_quote.toLowerCase().includes(q) ||
      f.normalized_signature.toLowerCase().includes(q) ||
      JSON.stringify(f.attributes).toLowerCase().includes(q);
    return textMatch; // shown only when activeFilter === 'all'
  });

  const filteredRelationships = relationships.filter(r => {
    const typeMatch = r.type === activeFilter;
    const textMatch = !q ||
      (r.fact_a?.source_quote || '').toLowerCase().includes(q) ||
      (r.fact_b?.source_quote || '').toLowerCase().includes(q) ||
      (r.fact_a?.attributes?.metric || '').toLowerCase().includes(q);
    return typeMatch && textMatch;
  });

  const noDocuments = documents.length === 0;

  return (
    <aside
      style={{ width, minWidth: 200, maxWidth: 520 }}
      className="border-r border-paper-border bg-paper-surface flex flex-col h-[calc(100vh-3.5rem)] overflow-hidden"
    >
      {/* Search */}
      <div className="px-3 pt-3 pb-2 border-b border-paper-border shrink-0">
        <div className="relative">
          <Search className="w-3.5 h-3.5 absolute left-2.5 top-2.5 text-paper-slate" />
          <input
            type="text"
            placeholder={isRelView ? 'Search relationships…' : 'Search facts…'}
            value={searchTerm}
            onChange={e => setSearchTerm(e.target.value)}
            className="w-full bg-paper-bg border border-paper-border rounded px-2.5 py-2 pl-8 text-xs text-paper-ink focus:outline-none focus:border-paper-accent placeholder:text-paper-slate/60"
          />
        </div>
      </div>

      {/* Filter tabs */}
      <div className="px-2 py-2 border-b border-paper-border flex flex-wrap gap-1 shrink-0">
        {filterTabs.map(tab => {
          const Icon = tab.icon;
          const active = activeFilter === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => onFilterChange(tab.id)}
              title={`${tab.count} ${tab.unit}`}
              className={`text-[11px] px-2 py-1 rounded flex items-center gap-1 transition font-medium ${
                active
                  ? 'bg-paper-ink text-paper-surface'
                  : 'text-paper-slate hover:text-paper-ink hover:bg-paper-bg'
              }`}
            >
              <Icon className="w-3 h-3 shrink-0" />
              <span>{tab.label}</span>
              <span
                className={`ml-0.5 text-[10px] px-1 rounded ${
                  active ? 'bg-white/20 text-white' : 'bg-paper-border/70 text-paper-slate'
                }`}
              >
                {tab.count}
              </span>
            </button>
          );
        })}
      </div>

      {/* Unit context line */}
      <div className="px-3 py-1.5 bg-paper-bg/60 border-b border-paper-border/50 shrink-0">
        <p className="text-[10px] font-mono text-paper-slate">
          {activeFilter === 'all'
            ? `${filteredFacts.length} facts · search to filter`
            : `${filteredRelationships.length} ${activeFilter} relationships`}
        </p>
      </div>

      {/* Main list */}
      <div className="flex-1 overflow-y-auto">
        {noDocuments ? (
          <div className="flex flex-col items-center justify-center h-full px-6 text-center gap-3">
            <div className="w-10 h-10 rounded-full bg-paper-bg border border-paper-border flex items-center justify-center text-paper-slate">
              <FileText className="w-5 h-5" />
            </div>
            <div>
              <p className="text-xs font-semibold text-paper-ink">Knowledge layer is empty</p>
              <p className="text-[11px] text-paper-slate mt-1 font-serif leading-snug">
                Upload a PDF to begin extracting grounded facts.
              </p>
            </div>
            <button
              onClick={onOpenUpload}
              className="text-xs font-medium px-3 py-1.5 rounded bg-paper-accent text-paper-surface hover:bg-paper-accent-dark transition flex items-center gap-1.5"
            >
              <Upload className="w-3.5 h-3.5" />
              Add Document
            </button>
          </div>
        ) : isRelView ? (
          /* ── RELATIONSHIP LIST (corroborated / contradicted / reconciled / uncertain) ── */
          filteredRelationships.length === 0 ? (
            <div className="p-6 text-center text-xs text-paper-slate font-serif italic">
              No {activeFilter} relationships found.
              {searchTerm && <span className="block mt-1">Try clearing your search.</span>}
            </div>
          ) : (
            filteredRelationships.map(rel => {
              const cfg = relTypeConfig[rel.type] || relTypeConfig.uncertain;
              const Icon = cfg.icon;
              const isSelected = selectedRelationshipId === rel.id;
              return (
                <button
                  key={rel.id}
                  onClick={() => onSelectRelationship(rel)}
                  className={`w-full text-left px-3 py-3 border-b border-paper-border/60 transition ${
                    isSelected ? 'bg-paper-accent-light border-l-2 border-l-paper-accent' : 'hover:bg-paper-bg'
                  }`}
                >
                  <div className="flex items-center justify-between mb-1.5">
                    <span className={`inline-flex items-center gap-1 text-[10px] font-mono font-semibold uppercase px-1.5 py-0.5 rounded border ${cfg.pill}`}>
                      <Icon className="w-2.5 h-2.5" />
                      {rel.type}
                    </span>
                    <span className="text-[10px] font-mono text-paper-slate">{(rel.confidence * 100).toFixed(0)}%</span>
                  </div>
                  <p className="text-xs font-semibold text-paper-ink capitalize truncate">
                    {rel.fact_a?.attributes?.metric || 'Factual Claim'}
                  </p>
                  <p className="text-[11px] text-paper-slate mt-0.5 line-clamp-2 font-serif leading-snug">
                    &ldquo;{rel.fact_a?.source_quote}&rdquo;
                  </p>
                  <div className="mt-1.5 text-[10px] text-paper-slate flex items-center gap-1 font-mono">
                    <span className="truncate max-w-[40%]">{rel.fact_a?.document_filename}</span>
                    <GitCompare className="w-2.5 h-2.5 shrink-0" />
                    <span className="truncate max-w-[40%]">{rel.fact_b?.document_filename}</span>
                  </div>
                </button>
              );
            })
          )
        ) : (
          /* ── FACTS LIST (all) ── */
          filteredFacts.length === 0 ? (
            <div className="p-6 text-center text-xs text-paper-slate font-serif italic">
              {facts.length === 0 ? 'No facts have been extracted yet.' : 'No facts match your search.'}
            </div>
          ) : (
            filteredFacts.map(fact => {
              const isSelected = selectedFactId === fact.id;
              const isUncertain = fact.status === 'uncertain';

              // Suppress placeholder/garbage values from the fallback extractor
              const rawValue = fact.attributes?.value ?? '';
              const isGarbageValue = !rawValue || /^[,.\s]+$/.test(rawValue);
              const displayValue = isGarbageValue ? null : rawValue;
              const displayUnit = displayValue && fact.attributes?.unit ? ` ${fact.attributes.unit}` : '';

              const rawEntity = fact.attributes?.entity ?? '';
              const isGenericEntity = !rawEntity || rawEntity.toLowerCase() === 'target entity';
              const displayEntity = isGenericEntity ? null : rawEntity;

              return (
                <button
                  key={fact.id}
                  onClick={() => onSelectFact(fact.id)}
                  className={`w-full text-left px-3 py-3 border-b border-paper-border/60 transition ${
                    isSelected ? 'bg-paper-accent-light border-l-2 border-l-paper-accent' : 'hover:bg-paper-bg'
                  }`}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-[10px] font-mono text-paper-slate uppercase tracking-wider truncate max-w-[55%]">
                      {displayEntity || fact.document_filename?.split('.')[0] || 'Fact'}
                    </span>
                    {isUncertain ? (
                      <span className="text-[10px] font-mono font-semibold uppercase px-1.5 py-0.5 rounded border bg-rel-uncertain-bg text-rel-uncertain-fg border-rel-uncertain-border shrink-0">
                        Uncertain
                      </span>
                    ) : (
                      <span className="text-[10px] font-mono text-paper-accent bg-paper-accent-light px-1.5 py-0.5 rounded shrink-0">
                        p.{fact.page_number}
                      </span>
                    )}
                  </div>
                  <p className="text-xs font-semibold text-paper-ink capitalize truncate">
                    {fact.attributes?.metric || 'Ground Claim'}
                  </p>
                  <p className="text-[11px] text-paper-slate mt-0.5 line-clamp-2 font-serif leading-snug">
                    &ldquo;{fact.source_quote}&rdquo;
                  </p>
                  <div className="mt-1.5 text-[10px] text-paper-slate flex items-center justify-between font-mono">
                    {displayValue ? (
                      <span className="font-semibold text-paper-ink">{displayValue}{displayUnit}</span>
                    ) : (
                      <span className="text-paper-slate/50 italic text-[10px]">—</span>
                    )}
                    <span className="truncate max-w-[50%]">{fact.document_filename}</span>
                  </div>
                </button>
              );
            })
          )
        )}
      </div>

      {/* Sources footer (collapsible, with ⋮ delete menus) */}
      {!noDocuments && (
        <div className="border-t border-paper-border shrink-0">
          <button
            onClick={() => setShowDocs(!showDocs)}
            className="w-full px-3 py-2 flex items-center justify-between text-[11px] text-paper-slate hover:text-paper-ink transition"
          >
            <span className="flex items-center gap-1.5 font-mono uppercase tracking-wider font-medium">
              <FileText className="w-3 h-3" />
              Sources ({documents.length})
            </span>
            <span className="text-[10px]">{showDocs ? '▲' : '▼'}</span>
          </button>
          {showDocs && (
            <div className="pb-2 max-h-40 overflow-y-auto bg-paper-bg">
              {documents.map(doc => (
                <div key={doc.id} className="group flex items-center justify-between px-3 py-1.5 hover:bg-paper-surface/60">
                  <div className="flex-1 min-w-0">
                    <p className="text-[11px] text-paper-ink truncate" title={doc.filename}>{doc.filename}</p>
                    <p className="text-[10px] font-mono text-paper-slate">
                      {doc.status === 'done'
                        ? `${doc.fact_count} fact${doc.fact_count !== 1 ? 's' : ''}`
                        : doc.status === 'processing'
                        ? '⟳ processing…'
                        : `✕ failed${doc.error_message ? `: ${doc.error_message}` : ''}`}
                    </p>
                    {doc.current_stage && doc.status !== 'done' && (
                      <div className="mt-1 flex items-center gap-1 text-[9px] font-mono text-paper-accent">
                        <span className="inline-block w-1.5 h-1.5 rounded-full bg-paper-accent animate-pulse" />
                        stage: {doc.current_stage}
                      </div>
                    )}
                    {doc.stage_status && (
                      <div className="mt-1 flex gap-0.5" title="Pipeline stage timeline">
                        {Object.entries(doc.stage_status).map(([name, state]) => (
                          <span
                            key={name}
                            title={`${name}: ${state.status}`}
                            className={`h-1 flex-1 rounded ${state.status === 'done' ? 'bg-paper-accent' : state.status === 'failed' ? 'bg-rel-contradiction-fg' : state.status === 'running' ? 'bg-rel-reconciled-fg animate-pulse' : 'bg-paper-border'}`}
                          />
                        ))}
                      </div>
                    )}
                  </div>
                  <DocMenu doc={doc} onDelete={onDeleteDocument} onReprocess={onReprocessDocument} />
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </aside>
  );
};
