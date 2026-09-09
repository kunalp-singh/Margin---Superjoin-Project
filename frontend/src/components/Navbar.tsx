'use client';

import React from 'react';
import { Upload, CheckCircle2, FileText, Hash, GitCompare } from 'lucide-react';

interface NavbarProps {
  documentCount: number;
  factCount: number;
  relationshipCount: number;
  onOpenUpload: () => void;
  onOpenReview: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({
  documentCount,
  factCount,
  relationshipCount,
  onOpenUpload,
  onOpenReview,
}) => {
  return (
    <header className="h-14 bg-paper-surface border-b border-paper-border px-5 flex items-center justify-between sticky top-0 z-30">
      {/* Brand */}
      <div className="flex items-center space-x-3">
        <div className="w-7 h-7 rounded bg-paper-accent flex items-center justify-center text-paper-surface font-serif text-sm font-bold select-none">
          M
        </div>
        <div className="flex items-center space-x-2.5">
          <h1 className="font-serif text-base font-semibold tracking-tight text-paper-ink">Margin</h1>
          <span className="text-[10px] font-mono uppercase bg-paper-accent-light text-paper-accent px-2 py-0.5 rounded font-semibold tracking-wider">
            Fact Knowledge Layer
          </span>
        </div>
      </div>

      {/* Stats + Actions */}
      <div className="flex items-center space-x-5">
        {/* Explicit separated counts */}
        <div className="hidden md:flex items-center divide-x divide-paper-border text-xs text-paper-slate">
          <div className="flex items-center space-x-1.5 pr-4">
            <FileText className="w-3.5 h-3.5 text-paper-accent" />
            <span><strong className="text-paper-ink font-semibold">{documentCount}</strong> docs</span>
          </div>
          <div className="flex items-center space-x-1.5 px-4">
            <Hash className="w-3.5 h-3.5 text-paper-accent" />
            <span><strong className="text-paper-ink font-semibold">{factCount}</strong> facts</span>
          </div>
          <div className="flex items-center space-x-1.5 pl-4">
            <GitCompare className="w-3.5 h-3.5 text-paper-accent" />
            <span><strong className="text-paper-ink font-semibold">{relationshipCount}</strong> relationships</span>
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center space-x-2">
          <button
            onClick={onOpenReview}
            className="text-xs font-medium px-3 py-1.5 rounded bg-paper-accent-light text-paper-accent border border-paper-accent/20 hover:bg-paper-accent-light/80 transition flex items-center space-x-1.5"
          >
            <CheckCircle2 className="w-3.5 h-3.5" />
            <span>Review Cases</span>
          </button>

          <button
            onClick={onOpenUpload}
            className="text-xs font-medium px-3.5 py-1.5 rounded bg-paper-accent text-paper-surface hover:bg-paper-accent-dark transition flex items-center space-x-1.5 shadow-sm"
          >
            <Upload className="w-3.5 h-3.5" />
            <span>Add Document</span>
          </button>
        </div>
      </div>
    </header>
  );
};
