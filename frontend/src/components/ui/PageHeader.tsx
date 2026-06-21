export function PageHeader({ title, action }: { title: string; action?: React.ReactNode }) {
  return (
    <div className="mb-4 flex items-center gap-3">
      <h2 className="text-2xl font-semibold text-heading">{title}</h2>
      {action && <div className="ml-auto">{action}</div>}
    </div>
  );
}
