import { Button } from "./Button";

export function ErrorBanner({
  message,
  actionLabel,
  onAction,
}: {
  message: string;
  actionLabel?: string;
  onAction?: () => void;
}) {
  return (
    <div
      role="alert"
      className="mb-4 flex items-center gap-3 rounded-lg border border-danger/20 bg-danger-tint px-4 py-3 text-sm text-danger"
    >
      <span>{message}</span>
      {actionLabel && onAction && (
        <Button variant="link" className="ml-auto" onClick={onAction}>
          {actionLabel}
        </Button>
      )}
    </div>
  );
}
