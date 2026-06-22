import type { InputHTMLAttributes } from "react";

export function Input({
  label,
  className = "",
  ...props
}: InputHTMLAttributes<HTMLInputElement> & { label: string }) {
  return (
    <label className="flex flex-col gap-1 text-sm text-ink">
      <span className="font-medium text-heading">{label}</span>
      <input
        className={`min-h-[44px] rounded-lg border border-line-strong bg-surface px-3 py-2 text-ink outline-none focus:border-primary focus:ring-1 focus:ring-primary ${className}`}
        {...props}
      />
    </label>
  );
}
