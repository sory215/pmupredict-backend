"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { fetchAnalyseCourse, Partant } from "@/lib/api";
import { getSupabaseClient } from "@/lib/supabaseClient";
import { HorseRow } from "@/components/HorseRow";

function CourseContent() {
  const searchParams = useSearchParams();
  const id = searchParams.get("id") || "";
  const [course, setCourse] = useState<any>(null);
  const [partants, setPartants] = useState<Partant[]>([]);
  const [chargement, setChargement] = useState(true);

  useEffect(() => {
    if (!id) return;
    fetchAnalyseCourse(id)
      .then((data) => {
        setCourse(data.course);
        setPartants(data.partants);
      })
      .finally(() => setChargement(false));
  }, [id]);

  useEffect(() => {
    if (!id) return;
    const supabase = getSupabaseClient();
    const channel = supabase
      .channel(`course-${id}`)
      .on(
        "postgres_changes",
        {
          event: "UPDATE",
          schema: "public",
          table: "partants",
          filter: `course_id=eq.${id}`,
        },
        (payload) => {
          setPartants((prev) =>
            prev.map((p) =>
              p.numero === payload.new.numero
                ? { ...p, cote_actuelle: payload.new.cote_actuelle }
                : p
            )
          );
        }
      )
      .subscribe();

    return () => {
      supabase.removeChannel(channel);
    };
  }, [id]);

  if (chargement) {
    return <p className="font-body text-ink/60 italic">Chargement du programme…</p>;
  }

  if (!course) {
    return <p className="font-body text-silk">Cette course est introuvable.</p>;
  }

  return (
    <div>
      <div className="mb-8">
        <p className="font-body text-xs uppercase tracking-[0.2em] text-turf">
          Analyse fusionnée — IA · Presse · Communauté
        </p>
        <h1 className="font-display text-3xl text-ink mt-1">
          C{course.numero} — {course.libelle}
        </h1>
        <p className="font-data text-sm text-ink/50 mt-1 inline-flex items-center gap-1.5">
          <span className="h-1.5 w-1.5 rounded-full bg-turf animate-pulse" />
          cotes en direct
        </p>
      </div>

      <div className="divide-y-0">
        {partants.map((p) => (
          <HorseRow key={p.numero} partant={p} />
        ))}
      </div>
    </div>
  );
}

export default function CoursePage() {
  return (
    <Suspense fallback={<p className="font-body text-ink/60 italic">Chargement…</p>}>
      <CourseContent />
    </Suspense>
  );
}
