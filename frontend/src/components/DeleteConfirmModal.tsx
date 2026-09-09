'use client';

import React from 'react';
import { X, Trash2, AlertTriangle } from 'lucide-react';
import { DocumentItem } from '../lib/types';

interface DeleteConfirmModalProps {
  document: DocumentItem | null;
  isOpen: boolean;
  isDeleting: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

export const DeleteConfirmModal: React.FC<DeleteConfirmModalProps> = ({
  document,
  isOpen,
  isDeleting,
  onConfirm,
  onCancel,
}) => {
  if (!isOpen || !document) return null;

  return (
    <div className="fixed inset-0 z-50 bg-black/30 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-paper-surface border border-paper-border rounded-xl max-w-md w-full shadow-2xl">
        {/* Header */}
        <div className="flex items-start justify-between px-5 pt-5 pb-4">
          <div className="flex items-start gap-3">
            <div className="p-2 rounded bg-rel-contradiction-bg border border-rel-contradiction-border mt-0.5 shrink-0">
              <AlertTriangle className="w-4 h-4 text-rel-contradiction-fg" />
            </div>
            <div>
              <h3 className="font-serif text-base font-bold text-paper-ink">Delete document?</h3>
              <p className="text-xs text-paper-slate mt-0.5 font-mono truncate max-w-xs" title={document.filename}>
                {document.filename}
              </p>
            </div>
          </div>
          <button
            onClick={onCancel}
            disabled={isDeleting}
            className="text-paper-slate hover:text-paper-ink transition p-1 disabled:opacity-40"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Body */}
        <div className="px-5 pb-4 border-t border-paper-border pt-4">
          <p className="text-xs text-paper-slate mb-3">This will permanently remove:</p>
          <ul className="space-y-1.5 text-xs text-paper-ink">
            <li className="flex items-center gap-2">
              <span className="w-1 h-1 rounded-full bg-rel-contradiction-icon shrink-0" />
              The uploaded document file
            </li>
            <li className="flex items-center gap-2">
              <span className="w-1 h-1 rounded-full bg-rel-contradiction-icon shrink-0" />
              <strong>{document.fact_count} fact{document.fact_count !== 1 ? 's' : ''}</strong> extracted from this document
            </li>
            <li className="flex items-center gap-2">
              <span className="w-1 h-1 rounded-full bg-rel-contradiction-icon shrink-0" />
              All cross-document relationships involving those facts
            </li>
          </ul>
          <p className="text-[11px] text-paper-slate mt-3 font-serif italic">
            Facts from other documents and unrelated relationships will remain untouched.
          </p>
          <div className="mt-3 px-2.5 py-2 bg-rel-contradiction-bg border border-rel-contradiction-border rounded text-[11px] text-rel-contradiction-fg font-medium">
            This cannot be undone.
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center justify-end gap-2 px-5 py-3.5 border-t border-paper-border">
          <button
            onClick={onCancel}
            disabled={isDeleting}
            className="px-3.5 py-1.5 text-xs font-medium text-paper-ink bg-paper-bg border border-paper-border rounded hover:bg-paper-surface transition disabled:opacity-40"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            disabled={isDeleting}
            className="px-3.5 py-1.5 text-xs font-medium rounded flex items-center gap-1.5 transition disabled:opacity-60 bg-rel-contradiction-bg text-rel-contradiction-fg border border-rel-contradiction-border hover:bg-rel-contradiction-border"
          >
            <Trash2 className="w-3.5 h-3.5" />
            {isDeleting ? 'Deleting…' : 'Delete document'}
          </button>
        </div>
      </div>
    </div>
  );
};
