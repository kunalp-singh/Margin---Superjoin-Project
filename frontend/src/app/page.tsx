'use client';

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Navbar } from '../components/Navbar';
import { KnowledgePane } from '../components/KnowledgePane';
import { FactDetailPane } from '../components/FactDetailPane';
import { UploadModal } from '../components/UploadModal';
import { ReviewCasesModal } from '../components/ReviewCasesModal';
import { DeleteConfirmModal } from '../components/DeleteConfirmModal';
import { Toast, ToastMessage } from '../components/Toast';
import {
  fetchDocuments, fetchFacts, fetchRelationships, fetchReviewCases,
  deleteDocument, reprocessDocument
} from '../lib/api';
import { DocumentItem, FactItem, RelationshipItem, ReviewCasesResponse } from '../lib/types';

export default function HomePage() {
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [facts, setFacts] = useState<FactItem[]>([]);
  const [relationships, setRelationships] = useState<RelationshipItem[]>([]);
  const [reviewCasesData, setReviewCasesData] = useState<ReviewCasesResponse | null>(null);

  const [selectedFactId, setSelectedFactId] = useState<string | null>(null);
  const [selectedRelationship, setSelectedRelationship] = useState<RelationshipItem | null>(null);
  const [activeFilter, setActiveFilter] = useState<string>('all');

  const [isUploadOpen, setIsUploadOpen] = useState(false);
  const [isReviewOpen, setIsReviewOpen] = useState(false);
  const [loading, setLoading] = useState(true);

  // Deletion state
  const [deleteTarget, setDeleteTarget] = useState<DocumentItem | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  // Toast state
  const [toasts, setToasts] = useState<ToastMessage[]>([]);

  // Resizable left pane
  const [leftWidth, setLeftWidth] = useState(280);
  const isResizing = useRef(false);

  const addToast = (toast: Omit<ToastMessage, 'id'>) => {
    const id = Math.random().toString(36).slice(2);
    setToasts(prev => [...prev, { ...toast, id }]);
  };

  const dismissToast = useCallback((id: string) => {
    setToasts(prev => prev.filter(t => t.id !== id));
  }, []);

  const handleResizeStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    isResizing.current = true;
    const startX = e.clientX;
    const startWidth = leftWidth;
    const onMouseMove = (ev: MouseEvent) => {
      if (!isResizing.current) return;
      const delta = ev.clientX - startX;
      setLeftWidth(Math.min(520, Math.max(200, startWidth + delta)));
    };
    const onMouseUp = () => {
      isResizing.current = false;
      document.removeEventListener('mousemove', onMouseMove);
      document.removeEventListener('mouseup', onMouseUp);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
    document.addEventListener('mousemove', onMouseMove);
    document.addEventListener('mouseup', onMouseUp);
  }, [leftWidth]);

  const loadData = useCallback(async () => {
    try {
      const [docsData, factsData, relsData, casesData] = await Promise.all([
        fetchDocuments(), fetchFacts(), fetchRelationships(), fetchReviewCases(),
      ]);
      setDocuments(docsData);
      setFacts(factsData);
      setRelationships(relsData);
      setReviewCasesData(casesData);
      return { docsData, factsData, relsData };
    } catch (err) {
      console.error('Failed to load data:', err);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData().then(result => {
      if (result && result.factsData.length > 0 && !selectedFactId && !selectedRelationship) {
        setSelectedFactId(result.factsData[0].id);
      }
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Background ingestion continues after upload returns. Poll while any
  // document is processing so the UI reflects completion or backend failure
  // instead of leaving a stale "processing" label on screen.
  useEffect(() => {
    if (!documents.some(doc => doc.status === 'processing')) return;
    const timer = window.setInterval(() => {
      loadData();
    }, 2000);
    return () => window.clearInterval(timer);
  }, [documents, loadData]);

  const handleSelectFact = (factId: string) => {
    setSelectedFactId(factId);
    setSelectedRelationship(null);
  };

  const handleSelectRelationship = (rel: RelationshipItem) => {
    setSelectedRelationship(rel);
    setSelectedFactId(null);
  };

  const handleSelectReviewCase = (caseType: 'corroborated' | 'contradicted' | 'reconciled' | 'uncertain') => {
    if (!reviewCasesData?.cases) return;
    const reviewCase = reviewCasesData.cases[caseType];
    if (!reviewCase) return; // case doesn't exist (e.g. no reconciled examples yet)

    // Always switch the filter tab to the correct type
    setActiveFilter(caseType);
    setSelectedFactId(null);

    // 1. Try to find the relationship in the already-loaded relationships state
    if (reviewCase.relationship_id) {
      const matchingRel = relationships.find(r => r.id === reviewCase.relationship_id);
      if (matchingRel) {
        setSelectedRelationship(matchingRel);
        return;
      }
    }

    // 2. Fallback: build a synthetic RelationshipItem from the embedded data in reviewCasesData
    //    (works even when the relationship_id isn't in the loaded list)
    if (reviewCase.fact_a && reviewCase.fact_b) {
      const synthetic: RelationshipItem = {
        id: reviewCase.relationship_id || 'review-case-' + caseType,
        fact_a_id: reviewCase.fact_a.id,
        fact_b_id: reviewCase.fact_b.id,
        type: reviewCase.type,
        confidence: reviewCase.confidence,
        reasoning: reviewCase.reasoning,
        created_at: reviewCase.fact_a.created_at,
        fact_a: reviewCase.fact_a,
        fact_b: reviewCase.fact_b,
      };
      setSelectedRelationship(synthetic);
      return;
    }

    // 3. Last resort: just highlight fact_a in the list
    if (reviewCase.fact_a) {
      setSelectedFactId(reviewCase.fact_a.id);
      setSelectedRelationship(null);
    }
  };

  // --- Deletion flow ---
  const handleDeleteRequest = (doc: DocumentItem) => {
    setDeleteTarget(doc);
  };

  const handleDeleteCancel = () => {
    setDeleteTarget(null);
  };

  const handleDeleteConfirm = async () => {
    if (!deleteTarget) return;
    const docId = deleteTarget.id;
    const docName = deleteTarget.filename;

    setIsDeleting(true);
    try {
      const result = await deleteDocument(docId);

      // Clear selection if the deleted doc's facts/relationships were selected
      setSelectedFactId(prev => {
        // We'll re-select after data refresh below
        return null;
      });
      setSelectedRelationship(null);

      // Refresh all data
      const refreshed = await loadData();

      // Auto-select first remaining fact
      if (refreshed && refreshed.factsData.length > 0) {
        setSelectedFactId(refreshed.factsData[0].id);
      } else {
        setSelectedFactId(null);
      }

      setDeleteTarget(null);
      addToast({
        type: 'success',
        title: 'Document deleted',
        body: `${result.deleted_facts} fact${result.deleted_facts !== 1 ? 's' : ''} and ${result.deleted_relationships} relationship${result.deleted_relationships !== 1 ? 's' : ''} removed.`,
      });
    } catch (err: any) {
      addToast({
        type: 'error',
        title: 'Could not delete document',
        body: err.message || 'The document was not removed. Please try again.',
      });
    } finally {
      setIsDeleting(false);
    }
  };

  const handleReprocess = async (doc: DocumentItem) => {
    try {
      await reprocessDocument(doc.id);
      await loadData();
      addToast({
        type: 'success',
        title: 'Reprocessing started',
        body: `${doc.filename} is running through the staged pipeline again.`,
      });
    } catch (err: any) {
      addToast({
        type: 'error',
        title: 'Could not reprocess document',
        body: err.message || 'Please try again.',
      });
    }
  };

  const selectedFact = facts.find(f => f.id === selectedFactId) || null;
  const relatedRelationships = selectedFact
    ? relationships.filter(r => r.fact_a_id === selectedFact.id || r.fact_b_id === selectedFact.id)
    : [];

  return (
    <div className="min-h-screen flex flex-col bg-paper-bg">
      <Navbar
        documentCount={documents.length}
        factCount={facts.length}
        relationshipCount={relationships.length}
        onOpenUpload={() => setIsUploadOpen(true)}
        onOpenReview={() => setIsReviewOpen(true)}
      />

      {/* 2-pane workspace: left nav + drag divider + main detail */}
      <div className="flex-1 flex overflow-hidden">
        <KnowledgePane
          facts={facts}
          relationships={relationships}
          documents={documents}
          selectedFactId={selectedFactId}
          selectedRelationshipId={selectedRelationship?.id || null}
          activeFilter={activeFilter}
          onSelectFact={handleSelectFact}
          onSelectRelationship={handleSelectRelationship}
          onFilterChange={filter => setActiveFilter(filter)}
          onDeleteDocument={handleDeleteRequest}
          onReprocessDocument={handleReprocess}
          onOpenUpload={() => setIsUploadOpen(true)}
          width={leftWidth}
        />

        {/* Drag-to-resize divider */}
        <div
          onMouseDown={handleResizeStart}
          className="w-1 shrink-0 cursor-col-resize hover:bg-paper-accent/40 active:bg-paper-accent transition-colors group relative"
          title="Drag to resize"
        >
          <div className="absolute inset-y-0 -left-1 -right-1" />
        </div>

        <FactDetailPane
          selectedFact={selectedFact}
          selectedRelationship={selectedRelationship}
          relatedRelationships={relatedRelationships}
        />
      </div>

      <UploadModal
        isOpen={isUploadOpen}
        onClose={() => setIsUploadOpen(false)}
        onUploadSuccess={() => loadData()}
      />

      <ReviewCasesModal
        isOpen={isReviewOpen}
        onClose={() => setIsReviewOpen(false)}
        reviewCasesData={reviewCasesData}
        onSelectCase={handleSelectReviewCase}
      />

      <DeleteConfirmModal
        document={deleteTarget}
        isOpen={deleteTarget !== null}
        isDeleting={isDeleting}
        onConfirm={handleDeleteConfirm}
        onCancel={handleDeleteCancel}
      />

      <Toast toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
}
