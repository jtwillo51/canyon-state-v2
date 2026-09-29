import { Badge } from "@/components/ui/badge";
import type { ReferralStatus } from "@/lib/api/types";

const VARIANT: Record<ReferralStatus, "default" | "secondary" | "outline" | "destructive"> = {
  referred: "outline",
  contacted: "outline",
  quoted: "secondary",
  bound: "default",
  lost: "destructive",
};

export function StatusBadge({ status }: { status: ReferralStatus }) {
  return (
    <Badge variant={VARIANT[status]} className="capitalize">
      {status}
    </Badge>
  );
}
