import { fetchTipsters } from "@/lib/api";
import { SaddleBadge } from "@/components/SaddleBadge";

export default async function TipstersPage() {
  const tipsters = await fetchTipsters("communaute").catch(() => []);

  return (
    <div>
      <p className="font-body text-xs uppercase tracking-[0.2em] text-turf">
        Fiabilité mesurée sur les pronostics passés
      </p>
      <h1 className="font-display text-4xl text-ink mt-1 mb-8">Classement des tipsters</h1>

      <div>
        {tipsters.map((t: any, i: number) => (
          <div key={t.nom} className="racecard-rule flex items-center gap-4 py-4">
            <SaddleBadge numero={i + 1} rang={i < 3 ? i + 1 : undefined} />
            <div className="flex-1">
              <p className="font-display text-lg text-ink">{t.nom}</p>
              <p className="font-body text-xs text-ink/50">{t.nb_pronostics} pronostics</p>
            </div>
            <p className="font-data text-xl font-semibold text-turf">{t.points} pts</p>
          </div>
        ))}
        {tipsters.length === 0 && (
          <p className="font-body text-ink/60 italic">Aucun tipster classé pour le moment.</p>
        )}
      </div>
    </div>
  );
}
