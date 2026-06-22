import { Button } from "./Button";

export function EmptyState({
  icon,
  message,
  actionLabel,
  onAction,
}: {
  icon?: string;
  message: string;
  actionLabel?: string;
  onAction?: () => void;
}) {
  return (
    <div className="rounded-2xl border border-dashed border-line bg-surface p-10 text-center">
      {icon && <div className="mb-2 text-3xl">{icon}</div>}
      <p className="text-muted">{message}</p>
      {actionLabel && onAction && (
        <div className="mt-4">
          <Button onClick={onAction}>{actionLabel}</Button>
        </div>
      )}
    </div>
  );
}
