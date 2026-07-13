export type ProvenanceKind = "source_report" | "model_extraction" | "graph_inference" | "human_verification";

export interface EvidenceRef {
  evidenceId: string;
  documentId: string;
  sourceUrl: string;
  startOffset: number;
  endOffset: number;
  spanHash: string;
  kind: ProvenanceKind;
}

export interface EntitySummary {
  stableId: string;
  displayName: string;
  entityType: "Person" | "Organization" | "Company" | "Location" | "GovernmentAgency" | "Product";
  confidence: number;
  status: "candidate" | "model_verified" | "human_verified" | "disputed" | "retracted";
  evidence: EvidenceRef[];
}

export interface AlertPolicyResult {
  alertScore: number;
  severityCode: number;
  routingCode: number;
  suppressed: boolean;
  policyVersionId: string;
  traceHash: string;
}

export interface AlertView {
  id: string;
  title: string;
  summary: string;
  createdAt: string;
  policy: AlertPolicyResult;
  entities: EntitySummary[];
  evidence: EvidenceRef[];
  graphPathIds: string[];
}
