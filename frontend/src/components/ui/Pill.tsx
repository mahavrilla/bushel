type Tone = "success" | "danger" | "warning" | "neutral";

const tones: Record<Tone, string> = {
  success: "bg-success-tint text-success",
  danger: "bg-danger-tint text-danger",
  warning: "bg-warning-tint text-warning",
  neutral: "bg-canvas text-muted",
};

export function Pill({ tone = "neutral", children }: { tone?: Tone; children: React.ReactNode }) {
  return (
    <span className={`inline-block rounded-md px-2 py-0.5 text-xs font-semibold ${tones[tone]}`}>
      {children}
    </span>
  );
}
