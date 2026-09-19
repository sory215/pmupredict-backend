import { Partant } from "@/lib/api";
import { SaddleBadge } from "./SaddleBadge";

export function HorseRow({ partant }: { partant: Partant }) {
  return (
    <div className="racecard-rule flex items-center gap-4 py-4">
      <SaddleBadge numero={partant.numero} rang={partant.rang_final} />

      <div className="min-w-0 flex-1">
        <p className="font-display text-lg leading-tight text-ink truncate">
          {partant.cheval_nom}
        </p>
        <p className="font-body text-sm text-ink/60">{partant.jockey}</p>
      </div>

      <div className="hidden sm:flex flex-col items-end gap-0.5 font-data text-xs text-ink/50 w-32">
        <span>IA {(partant.score_ia * 100).toFixed(0)}</span>
        <span>Presse {(partant.score_presse * 100).toFixed(0)}</span>
        <span>Public {(partant.score_communaute * 100).toFixed(0)}</span>
      </div>

      <div className="text-right">
        <p className="font-data text-xl font-semibold text-turf">
          {partant.cote_actuelle?.toFixed(1)}
        </p>
        <p className="font-body text-[11px] uppercase tracking-wide text-ink/50">cote</p>
      </div>
    </div>
  );
}
