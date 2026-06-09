import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

interface StatCardProps {
  label: string;
  value: string;
  hint?: string;
  isLoading?: boolean;
}

export default function StatCard({ label, value, hint, isLoading }: StatCardProps) {
  return (
    <Card>
      <CardContent className="p-3">
        <div className="text-xs uppercase tracking-wider text-muted-foreground">{label}</div>
        {isLoading ? (
          <Skeleton className="mt-1.5 h-7 w-16" />
        ) : (
          <div className="mt-1 text-xl font-semibold text-foreground">{value}</div>
        )}
        {hint ? <div className="mt-0.5 text-xs text-muted-foreground">{hint}</div> : null}
      </CardContent>
    </Card>
  );
}
