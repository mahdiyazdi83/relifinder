import type { RelationshipListItem } from "../../api/client";

export type RelationshipSortKey = "confidence" | "source" | "target" | "cardinality" | "validation";

export interface RelationshipFilters {
  search: string;
  sourceSchema: string;
  targetSchema: string;
  minConfidence: number;
  confidenceLabel: string;
  cardinality: string;
  validationStatus: string;
  crossSchemaOnly: boolean;
  targetKeyType: string;
  sortKey: RelationshipSortKey;
  sortDirection: "asc" | "desc";
}

export const defaultRelationshipFilters: RelationshipFilters = {
  search: "",
  sourceSchema: "",
  targetSchema: "",
  minConfidence: 0,
  confidenceLabel: "",
  cardinality: "",
  validationStatus: "",
  crossSchemaOnly: false,
  targetKeyType: "",
  sortKey: "confidence",
  sortDirection: "desc",
};

export function filterAndSortRelationships(
  relationships: RelationshipListItem[],
  filters: RelationshipFilters,
): RelationshipListItem[] {
  const query = filters.search.trim().toLocaleLowerCase();
  const filtered = relationships.filter((item) => {
    const searchable = [
      item.source.schema_name,
      item.source.table_name,
      item.source.column_name,
      item.target.schema_name,
      item.target.table_name,
      item.target.column_name,
    ]
      .join(" ")
      .toLocaleLowerCase();
    return (
      (!query || searchable.includes(query)) &&
      (!filters.sourceSchema || item.source.schema_name === filters.sourceSchema) &&
      (!filters.targetSchema || item.target.schema_name === filters.targetSchema) &&
      item.confidence_score >= filters.minConfidence &&
      (!filters.confidenceLabel || item.confidence_label === filters.confidenceLabel) &&
      (!filters.cardinality || item.cardinality === filters.cardinality) &&
      (!filters.validationStatus || item.validation_status === filters.validationStatus) &&
      (!filters.crossSchemaOnly || item.cross_schema) &&
      (!filters.targetKeyType || item.target_key_type === filters.targetKeyType)
    );
  });

  return [...filtered].sort((left, right) => {
    const primary = compare(sortValue(left, filters.sortKey), sortValue(right, filters.sortKey));
    if (primary !== 0) return filters.sortDirection === "asc" ? primary : -primary;
    return compare(stableKey(left), stableKey(right));
  });
}

export function hasActiveFilters(filters: RelationshipFilters): boolean {
  return (
    filters.search.trim() !== "" ||
    filters.sourceSchema !== "" ||
    filters.targetSchema !== "" ||
    filters.minConfidence > 0 ||
    filters.confidenceLabel !== "" ||
    filters.cardinality !== "" ||
    filters.validationStatus !== "" ||
    filters.crossSchemaOnly ||
    filters.targetKeyType !== ""
  );
}

export function relationshipFilterOptions(relationships: RelationshipListItem[]) {
  const unique = (values: string[]) => [...new Set(values)].sort();
  return {
    sourceSchemas: unique(relationships.map((item) => item.source.schema_name)),
    targetSchemas: unique(relationships.map((item) => item.target.schema_name)),
    confidenceLabels: unique(relationships.map((item) => item.confidence_label)),
    cardinalities: unique(relationships.map((item) => item.cardinality)),
    validationStatuses: unique(relationships.map((item) => item.validation_status)),
    targetKeyTypes: unique(relationships.map((item) => item.target_key_type)),
  };
}

function sortValue(item: RelationshipListItem, key: RelationshipSortKey): string | number {
  if (key === "confidence") return item.confidence_score;
  if (key === "source") return endpointKey(item.source);
  if (key === "target") return endpointKey(item.target);
  if (key === "cardinality") return item.cardinality;
  return item.validation_status;
}

function endpointKey(endpoint: RelationshipListItem["source"]): string {
  return `${endpoint.schema_name}.${endpoint.table_name}.${endpoint.column_name}`;
}

function stableKey(item: RelationshipListItem): string {
  return `${endpointKey(item.source)}->${endpointKey(item.target)}`;
}

function compare(left: string | number, right: string | number): number {
  if (typeof left === "number" && typeof right === "number") return left - right;
  return String(left).localeCompare(String(right));
}
