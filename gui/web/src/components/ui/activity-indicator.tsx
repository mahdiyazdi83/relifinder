import { LoaderCircle } from "lucide-react";

import { cn } from "../../lib/utils";

export function ActivityIndicator({
  className,
  label = "Working",
}: {
  className?: string;
  label?: string;
}) {
  return (
    <span className={cn("inline-flex items-center gap-2", className)}>
      <LoaderCircle
        aria-hidden="true"
        className="size-4 animate-spin text-accent motion-reduce:animate-none"
      />
      <span className="sr-only">{label}</span>
    </span>
  );
}
