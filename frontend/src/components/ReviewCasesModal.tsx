'use client';

import React from 'react';
import { X, Check, AlertTriangle, Scale, HelpCircle, ArrowRight } from 'lucide-react';
import { ReviewCasesResponse } from '../lib/types';

interface ReviewCasesModalProps {
  isOpen: boolean;
  onClose: () => void;
  reviewCasesData: ReviewCasesResponse | null;
  onSelectCase: (caseType: 'corroborated' | 'contradicted' | 'reconciled' | 'uncertain') => void;
}

const cases = [
  {
    id: 'corroborated' as const,
    num: '01',
    title: 'Corroboration Across Phrasings',
    desc: 'Same metric and value confirmed across documents with different wording or units.',
    icon: Check,
    pill: 'bg-rel-corroborated-bg text-rel-corroborated-fg border-rel-corroborated-border',
  },
  {
    id: 'contradicted' as const,
    num: '02',
    title: 'Genuine Contradiction',
    desc: 'Conflicting values for the same entity, metric, period, and scope.',
    icon: AlertTriangle,
    pill: 'bg-rel-contradiction-bg text-rel-contradiction-fg border-rel-contradiction-border',
  },
  {
    id: 'reconciled' as const,
    num: '03',
    title: 'Contextual Reconciliation',
    desc: 'Apparent contradiction explained by time period difference — Q3 headcount vs end-of-FY figure.',
    icon: Scale,
    pill: 'bg-rel-reconciled-bg text-rel-reconciled-fg border-rel-reconciled-border',
  },
  {
    id: 'uncertain' as const,
    num: '04',
    title: 'Extraction Ambiguity',
    desc: 'Ambiguous referents handled honestly — marked uncertain rather than forcing a normalized claim.',
    icon: HelpCircle,
    pill: 'bg-rel-uncertain-bg text-rel-uncertain-fg border-rel-uncertain-border',
  },
];

export const ReviewCasesModal: React.FC<ReviewCasesModalProps> = ({
  isOpen,
  onClose,
  reviewCasesData,
  onSelectCase,
}) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 bg-black/30 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-paper-surface border border-paper-border rounded-xl max-w-lg w-full shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-paper-border">
          <div>
            <h3 className="font-serif text-base font-bold text-paper-ink">4 Canonical Evidence Cases</h3>
            <p className="text-[11px] text-paper-slate mt-0.5">Click any case to navigate directly to its grounded evidence</p>
          </div>
          <button onClick={onClose} className="text-paper-slate hover:text-paper-ink transition p-1">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Case list — compact numbered */}
        <div className="divide-y divide-paper-border">
          {cases.map(c => {
            const Icon = c.icon;
            const caseObj = reviewCasesData?.cases[c.id];
            const isAvailable = !!caseObj;
            return (
              <button
                key={c.id}
                onClick={() => { if (isAvailable) { onSelectCase(c.id); onClose(); } }}
                disabled={!isAvailable}
                className={`w-full text-left px-5 py-3.5 flex items-center gap-4 group transition ${
                  isAvailable
                    ? 'hover:bg-paper-bg cursor-pointer'
                    : 'opacity-40 cursor-not-allowed'
                }`}
              >
                {/* Number + icon */}
                <div className="flex items-center gap-2 shrink-0">
                  <span className="font-mono text-xs text-paper-slate font-semibold w-6">{c.num}</span>
                  <span className={`p-1.5 rounded border ${c.pill}`}>
                    <Icon className="w-3.5 h-3.5" />
                  </span>
                </div>

                {/* Text */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-semibold text-paper-ink">{c.title}</span>
                    {isAvailable ? (
                      <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-paper-accent-light text-paper-accent font-medium">
                        Ready
                      </span>
                    ) : (
                      <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-paper-bg border border-paper-border text-paper-slate">
                        No example yet
                      </span>
                    )}
                  </div>
                  <p className="text-[11px] text-paper-slate font-serif mt-0.5 leading-snug">{c.desc}</p>
                </div>

                {isAvailable && (
                  <ArrowRight className="w-3.5 h-3.5 text-paper-slate group-hover:text-paper-accent transition group-hover:translate-x-0.5 transform shrink-0" />
                )}
              </button>
            );
          })}
        </div>

        <div className="px-5 py-3 border-t border-paper-border flex justify-end">
          <button
            onClick={onClose}
            className="px-3.5 py-1.5 text-xs font-medium bg-paper-bg border border-paper-border rounded text-paper-ink hover:bg-paper-surface transition"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
