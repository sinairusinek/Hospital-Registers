
export interface RegistryRecord {
  // null marks a value the app has cleaned away, e.g. a stray Sex letter.
  [key: string]: string | number | null | undefined;
  'Admission Date [ISO]'?: string;
  'Discharge Date (ISO)'?: string;
  'Days in Hospital (Calc)'?: number;
  'Age'?: number;
  'Age Group'?: string;
  'Sex'?: string;
  'Religion'?: string;
  'Standardized Religion'?: string;
  'StandardNationality'?: string;
  'Standardized Diagnosis'?: string;
  'Primary-ICD9'?: string;
  'Standardized Result'?: string;
  'standardized ward'?: string;
  'Infectious / Non-infectious'?: string;
  'Class'?: string;
  'City'?: string;
  'City Kima ID'?: string;
  'City Wikidata'?: string;
  'standardprimaryICD9names'?: string;
}

export type ViewType = 'about' | 'browse' | 'statistics' | 'review' | 'places';

export interface RangeFilter {
  min: number;
  max: number;
  currentMin: number;
  currentMax: number;
}

export interface FilterState {
  searchQuery: string;
  advancedSearch: {
    column: string;
    query: string;
  }[];
  facets: {
    [column: string]: string[];
  };
  ranges: {
    [column: string]: RangeFilter;
  };
}

export interface ColumnConfig {
  key: string;
  label: string;
  visible: boolean;
}
