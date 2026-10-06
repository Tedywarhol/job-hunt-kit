/**
 * Shape of the JSON printed by `scripts/ui_data.py`. The Python script owns
 * the business rules (follow-up due dates, trust levels, real statuses); the
 * screen only displays these values.
 */

export interface FollowupDue {
  entreprise: string;
  poste: string;
  etape_suivante: string;
  echeance: string;
  /** Negative: days late. 0: today. Positive: days left. */
  jours: number;
}

export interface NotionSnapshot {
  total: number;
  statuts: Record<string, number>;
  relances_en_retard: Array<{
    entreprise: string;
    poste: string;
    etape: string;
    date_prochaine: string;
  }>;
}

export interface TopOffer {
  entreprise: string;
  poste: string;
  score: number;
  age_jours: number;
  lieu: string;
  lien: string;
}

export interface RecentFolder {
  slug: string;
  entreprise: string;
  poste: string;
  pdf: boolean;
}

export interface NetworkSummary {
  genere_le: string | null;
  contacts: number;
  entreprises: number;
  niveaux_calcules: boolean;
  par_niveau: Record<string, number>;
  opportunites: Array<{ nom: string; entreprise: string }>;
  refus: number;
}

export interface DashboardData {
  genere_le: string;
  relances: FollowupDue[];
  statuts_locaux: Record<string, number>;
  notion: NotionSnapshot | null;
  fraicheur: { today: number; week: number; month: number; older: number };
  offres: { en_attente: number; meilleures: TopOffer[] };
  dossiers: { total: number; recents: RecentFolder[] };
  reseau: NetworkSummary | null;
}

/** Offer as stored in state/pending-notion-upsert.json and state/pass_alternance_scored.json. */
export interface OpportunityItem {
  entreprise?: string;
  intitule?: string;
  poste?: string;
  score_pertinence?: number;
  score?: number;
  date_publication?: string;
  age_jours?: number;
  lien?: string;
  source?: string;
  lieu?: string;
}
