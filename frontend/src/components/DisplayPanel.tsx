import { BusFront } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

interface Props {
  nearbyBusRadiusM: number;
  onNearbyBusRadiusChange: (radiusM: number) => void;
  hasSelectedProperty: boolean;
}

export default function DisplayPanel({
  nearbyBusRadiusM,
  onNearbyBusRadiusChange,
  hasSelectedProperty,
}: Props) {
  return (
    <div className="space-y-3 px-5 py-4">
      <div>
        <h2 className="text-sm font-semibold text-foreground">Display</h2>
        <p className="mt-1 text-xs text-muted-foreground">Choose extra information to draw on the map.</p>
      </div>
      <div className="space-y-3 rounded-lg border border-border p-3">
        <div className="flex items-start gap-3">
          <BusFront className="mt-0.5 h-4 w-4 shrink-0 text-blue-600" />
          <span>
            <span className="block text-sm font-medium">Nearby bus route radius</span>
            <span className="mt-0.5 block text-xs text-muted-foreground">
            {hasSelectedProperty
                ? `Show routes from every bus stop within ${nearbyBusRadiusM} m of the selected property.`
              : "Select a property on the map to display its nearby bus routes."}
            </span>
          </span>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="nearby-bus-radius">Distance (metres)</Label>
          <Input
            id="nearby-bus-radius"
            type="number"
            min={0}
            max={2000}
            step={50}
            value={nearbyBusRadiusM}
            onChange={(event) => {
              const value = Number(event.target.value);
              onNearbyBusRadiusChange(Number.isFinite(value) ? Math.min(2000, Math.max(0, value)) : 0);
            }}
          />
          <p className="text-[11px] text-muted-foreground">Set the distance to 0 to hide this overlay.</p>
        </div>
      </div>
    </div>
  );
}
