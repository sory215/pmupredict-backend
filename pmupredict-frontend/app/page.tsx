import { fetchCoursesDuJour } from "@/lib/api";

export default async function HomePage() {
  const courses = await fetchCoursesDuJour().catch(() => []);

  return (
    <div>
      <div className="mb-10">
        <p className="font-body text-xs uppercase tracking-[0.2em] text-turf">
          Programme officiel
        </p>
        <h1 className="font-display text-4xl text-ink mt-1">
          {new Date().toLocaleDateString("fr-FR", {
            weekday: "long",
            day: "numeric",
            month: "long",
          })}
        </h1>
      </div>

      {courses.length === 0 && (
        <p className="font-body text-ink/60 italic">
          Aucune course disponible pour le moment. Le programme est généralement
          publié en début de matinée.
        </p>
      )}

      <div className="space-y-1">
        {courses.map((c) => (
          <a
            key={c.id}
            href={`/course/?id=${c.id}`}
            className="racecard-rule flex items-center justify-between py-4 group"
          >
            <div>
              <p className="font-body text-xs uppercase tracking-wide text-turf">
                R{c.reunions?.numero} · {c.reunions?.hippodromes?.nom}
              </p>
              <p className="font-display text-xl text-ink group-hover:text-gold transition-colors">
                C{c.numero} — {c.libelle}
              </p>
            </div>
            <div className="text-right">
              <p className="font-data text-lg text-ink">
                {c.heure_depart
                  ? new Date(c.heure_depart).toLocaleTimeString("fr-FR", {
                      hour: "2-digit",
                      minute: "2-digit",
                    })
                  : "—"}
              </p>
              <p className="font-body text-[11px] uppercase tracking-wide text-ink/50">
                {c.discipline}
              </p>
            </div>
          </a>
        ))}
      </div>
    </div>
  );
}
