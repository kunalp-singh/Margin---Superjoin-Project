'use client';

import React, { useEffect } from 'react';
import { CheckCircle2, X, AlertCircle } from 'lucide-react';

export interface ToastMessage {
  id: string;
  type: 'success' | 'error';
  title: string;
  body?: string;
}

interface ToastProps {
  toasts: ToastMessage[];
  onDismiss: (id: string) => void;
}

export const Toast: React.FC<ToastProps> = ({ toasts, onDismiss }) => {
  return (
    <div className="fixed bottom-5 right-5 z-[60] flex flex-col gap-2 pointer-events-none">
      {toasts.map(toast => (
        <ToastItem key={toast.id} toast={toast} onDismiss={onDismiss} />
      ))}
    </div>
  );
};

const ToastItem: React.FC<{ toast: ToastMessage; onDismiss: (id: string) => void }> = ({
  toast,
  onDismiss,
}) => {
  useEffect(() => {
    const timer = setTimeout(() => onDismiss(toast.id), 4000);
    return () => clearTimeout(timer);
  }, [toast.id, onDismiss]);

  const isSuccess = toast.type === 'success';

  return (
    <div
      className={`pointer-events-auto flex items-start gap-3 px-4 py-3 rounded-lg border shadow-lg max-w-xs animate-in slide-in-from-bottom-2 fade-in duration-200 ${
        isSuccess
          ? 'bg-paper-surface border-paper-border'
          : 'bg-rel-contradiction-bg border-rel-contradiction-border'
      }`}
    >
      {isSuccess ? (
        <CheckCircle2 className="w-4 h-4 text-paper-accent shrink-0 mt-0.5" />
      ) : (
        <AlertCircle className="w-4 h-4 text-rel-contradiction-fg shrink-0 mt-0.5" />
      )}
      <div className="flex-1 min-w-0">
        <p className={`text-xs font-semibold ${isSuccess ? 'text-paper-ink' : 'text-rel-contradiction-fg'}`}>
          {toast.title}
        </p>
        {toast.body && (
          <p className={`text-[11px] mt-0.5 ${isSuccess ? 'text-paper-slate' : 'text-rel-contradiction-fg/80'}`}>
            {toast.body}
          </p>
        )}
      </div>
      <button
        onClick={() => onDismiss(toast.id)}
        className="text-paper-slate hover:text-paper-ink transition shrink-0"
      >
        <X className="w-3.5 h-3.5" />
      </button>
    </div>
  );
};
