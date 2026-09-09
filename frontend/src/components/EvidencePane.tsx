'use client';

// EvidencePane has been merged into FactDetailPane as an expandable drawer.
// This file is kept for compatibility but renders nothing.

import React from 'react';
import { FactItem, RelationshipItem } from '../lib/types';

interface EvidencePaneProps {
  selectedFact: FactItem | null;
  selectedRelationship: RelationshipItem | null;
}

export const EvidencePane: React.FC<EvidencePaneProps> = () => null;
