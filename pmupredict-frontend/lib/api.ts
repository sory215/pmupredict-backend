const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "";

export type CourseListItem = {
  id: string;
  numero: number;
  libelle: string;
  discipline: string;
  heure_depart: string;
  statut: string;
  reunions: {
    numero: number;
    hippodromes: { nom: string; code: string };
  };
};

export type Partant = {
  numero: number;
  cheval_nom: string;
  jockey: string;
  cote_actuelle: number;
  score_ia: number;
  score_presse: number;
  score_communaute: number;
  score_final: number;
  rang_final: number;
  probabilite_estimee?: number;
  cote_estimee?: number;
};

export async function fetchCoursesDuJour(): Promise<CourseListItem[]> {
  const res = await fetch(`${API_BASE}/api/courses`, { next: { revalidate: 60 } });
  if (!res.ok) throw new Error("Impossible de charger le programme du jour");
  const data = await res.json();
  return data.courses;
}

export async function fetchAnalyseCourse(courseId: string) {
  const res = await fetch(`${API_BASE}/api/analyse/${courseId}`, { next: { revalidate: 30 } });
  if (!res.ok) throw new Error("Course introuvable");
  return res.json() as Promise<{ course: any; partants: Partant[] }>;
}

export async function fetchTipsters(type: "communaute" | "presse" = "communaute") {
  const res = await fetch(`${API_BASE}/api/tipsters?type=${type}`, { next: { revalidate: 300 } });
  if (!res.ok) throw new Error("Impossible de charger le classement des tipsters");
  const data = await res.json();
  return data.tipsters;
}
