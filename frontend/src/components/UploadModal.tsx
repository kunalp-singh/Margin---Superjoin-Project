'use client';

import React, { useState, useRef } from 'react';
import { X, Upload, FileText, CheckCircle2, Loader2, AlertCircle } from 'lucide-react';
import { uploadDocument } from '../lib/api';
import { DocumentItem } from '../lib/types';

interface UploadModalProps {
  isOpen: boolean;
  onClose: () => void;
  onUploadSuccess: (doc: DocumentItem) => void;
}

export const UploadModal: React.FC<UploadModalProps> = ({
  isOpen,
  onClose,
  onUploadSuccess,
}) => {
  const [file, setFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadStep, setUploadStep] = useState<number>(0);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  if (!isOpen) return null;

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const selected = e.target.files[0];
      if (!selected.name.endsWith('.pdf')) {
        setErrorMsg('Please select a valid PDF document.');
        return;
      }
      setFile(selected);
      setErrorMsg(null);
    }
  };

  const handleUploadSubmit = async () => {
    if (!file) return;
    setIsUploading(true);
    setErrorMsg(null);
    setUploadStep(1);

    try {
      // Simulate step progress visualization for smooth user feedback
      setTimeout(() => setUploadStep(2), 600);
      setTimeout(() => setUploadStep(3), 1400);

      const doc = await uploadDocument(file);
      
      setUploadStep(4);
      setTimeout(() => {
        onUploadSuccess(doc);
        setIsUploading(false);
        setFile(null);
        setUploadStep(0);
        onClose();
      }, 1000);
    } catch (err: any) {
      setIsUploading(false);
      setErrorMsg(err.message || 'Failed to upload and process PDF.');
    }
  };

  const steps = [
    { title: 'Uploading PDF to server', desc: 'Securely saving document to ingestion workspace' },
    { title: 'PyMuPDF page parsing & text segmentation', desc: 'Extracting text blocks and mapping character offsets' },
    { title: 'Parser extraction & Gemini verification', desc: 'Checking grounded claims, metrics, units, and periods' },
    { title: 'Cross-document relationship classification', desc: 'Comparing verified facts and persisting graph edges' },
  ];

  return (
    <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="bg-paper-surface border border-paper-border rounded-lg max-w-md w-full p-6 shadow-xl relative">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-paper-border pb-3 mb-4">
          <h3 className="font-serif text-lg font-bold text-paper-ink">Upload Document</h3>
          <button onClick={onClose} className="text-paper-slate hover:text-paper-ink">
            <X className="w-5 h-5" />
          </button>
        </div>

        {errorMsg && (
          <div className="mb-4 p-3 bg-rose-50 border border-rose-200 text-rose-800 rounded text-xs flex items-center space-x-2">
            <AlertCircle className="w-4 h-4 flex-shrink-0" />
            <span>{errorMsg}</span>
          </div>
        )}

        {!isUploading ? (
          <div>
            {/* File Dropzone */}
            <div
              onClick={() => fileInputRef.current?.click()}
              className="border-2 border-dashed border-paper-border rounded-lg p-8 text-center cursor-pointer hover:border-paper-accent hover:bg-paper-bg transition"
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf"
                onChange={handleFileChange}
                className="hidden"
              />
              <Upload className="w-8 h-8 text-paper-accent mx-auto mb-2" />
              <p className="text-xs font-semibold text-paper-ink">
                {file ? file.name : 'Click to select or drag PDF file here'}
              </p>
              <p className="text-[11px] text-paper-slate mt-1">
                Supports all text-native PDF reports & filings
              </p>
            </div>

            <div className="mt-6 flex justify-end space-x-3">
              <button
                onClick={onClose}
                className="px-4 py-2 text-xs font-medium text-paper-slate hover:text-paper-ink"
              >
                Cancel
              </button>
              <button
                onClick={handleUploadSubmit}
                disabled={!file}
                className="px-4 py-2 text-xs font-medium bg-paper-accent text-paper-surface rounded hover:bg-paper-accent/90 disabled:opacity-50 transition"
              >
                Upload & Process
              </button>
            </div>
          </div>
        ) : (
          /* Step-by-Step Processing Timeline */
          <div className="py-4 space-y-4">
            <h4 className="font-mono text-xs uppercase text-paper-slate mb-4">Ingestion Timeline Progress</h4>
            {steps.map((st, idx) => {
              const stepNum = idx + 1;
              const isDone = uploadStep > stepNum;
              const isCurrent = uploadStep === stepNum;

              return (
                <div key={idx} className="flex items-start space-x-3">
                  <div className="mt-0.5">
                    {isDone ? (
                      <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                    ) : isCurrent ? (
                      <Loader2 className="w-4 h-4 text-paper-accent animate-spin" />
                    ) : (
                      <div className="w-4 h-4 rounded-full border border-paper-border bg-paper-bg flex items-center justify-center text-[10px] text-paper-slate">
                        {stepNum}
                      </div>
                    )}
                  </div>
                  <div>
                    <p className={`text-xs font-medium ${isCurrent ? 'text-paper-ink font-bold' : isDone ? 'text-paper-ink' : 'text-paper-slate'}`}>
                      {st.title}
                    </p>
                    <p className="text-[11px] text-paper-slate font-serif">{st.desc}</p>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};
