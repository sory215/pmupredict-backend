export function SaddleBadge({ numero, rang }: { numero: number; rang?: number }) {
  const style =
    rang === 1
      ? "bg-gold text-turf-dark border-gold"
      : rang === 2
      ? "bg-silver text-white border-silver"
      : rang === 3
      ? "bg-bronze text-white border-bronze"
      : "bg-paper text-ink border-ink/30";

  return (
    <span
      className={`inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-full border-2 font-data text-sm font-semibold ${style}`}
      aria-label={rang ? `Numéro ${numero}, rang ${rang}` : `Numéro ${numero}`}
    >
      {numero}
    </span>
  );
}
