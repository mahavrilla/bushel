type Tone = "success" | "danger" | "warning" | "neutral";

const tones: Record<Tone, string> = {
  success: "bg-tint-green text-success",
  danger: "bg-red-100 text-danger",
  warning: "bg-tint-amber text-primary",
  neutral: "bg-stone-100 text-stone-600",
};

export function Pill({ tone = "neutral", children }: { tone?: Tone; children: React.ReactNode }) {
  return (
    <span className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-semibold ${tones[tone]}`}>
      {children}
    </span>
  );
}
