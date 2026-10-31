export function Stamp({ children, tone = "ink", size = "md", className = "" }: {
  children: React.ReactNode;
  tone?: "ink" | "soil" | "muted";
  size?: "sm" | "md" | "lg";
  className?: string;
}) {
  return (
    <span className={`stamp stamp-${tone} stamp-${size} ${className}`}>
      <span className="stamp-inner">{children}</span>
    </span>
  );
}
