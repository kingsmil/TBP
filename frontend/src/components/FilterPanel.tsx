import { X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { SearchFilters } from "../types";
import { MAP_SEARCH_LIMIT } from "../lib/mapConfig";

const FLAT_TYPES = ["2 ROOM", "3 ROOM", "4 ROOM", "5 ROOM", "EXECUTIVE"];

interface Props {
  filters: SearchFilters;
  onChange: (next: SearchFilters) => void;
}

const DEFAULT_FILTERS: SearchFilters = { limit: MAP_SEARCH_LIMIT };
const ANY = "__any__";

export default function FilterPanel({ filters, onChange }: Props) {
  function set<K extends keyof SearchFilters>(key: K, value: SearchFilters[K]) {
    onChange({ ...filters, [key]: value });
  }

  const numberOrUndefined = (v: string) => (v === "" ? undefined : Number(v));

  const hasActiveFilters =
    filters.flat_type !== undefined ||
    filters.max_psf !== undefined ||
    filters.max_mrt_distance_m !== undefined ||
    filters.min_schools_within_1km !== undefined;

  return (
    <div className="space-y-4 px-5 py-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-foreground">Filters</h2>
        {hasActiveFilters && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onChange(DEFAULT_FILTERS)}
            className="h-7 gap-1 px-2 text-xs text-muted-foreground hover:text-foreground"
          >
            <X className="h-3 w-3" />
            Clear
          </Button>
        )}
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="flat-type">Flat type</Label>
        <Select
          value={filters.flat_type ?? ANY}
          onValueChange={(v) => set("flat_type", v === ANY ? undefined : v)}
        >
          <SelectTrigger id="flat-type">
            <SelectValue placeholder="Any" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ANY}>Any</SelectItem>
            {FLAT_TYPES.map((ft) => (
              <SelectItem key={ft} value={ft}>
                {ft}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="max-psf">Max PSF (S$)</Label>
        <Input
          id="max-psf"
          type="number"
          placeholder="e.g. 600"
          value={filters.max_psf ?? ""}
          onChange={(e) => set("max_psf", numberOrUndefined(e.target.value))}
        />
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="max-mrt">Max walk to MRT (m)</Label>
        <Input
          id="max-mrt"
          type="number"
          placeholder="e.g. 500"
          value={filters.max_mrt_distance_m ?? ""}
          onChange={(e) =>
            set("max_mrt_distance_m", numberOrUndefined(e.target.value))
          }
        />
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="min-schools">Min schools within 1km</Label>
        <Input
          id="min-schools"
          type="number"
          placeholder="e.g. 2"
          value={filters.min_schools_within_1km ?? ""}
          onChange={(e) =>
            set("min_schools_within_1km", numberOrUndefined(e.target.value))
          }
        />
      </div>
    </div>
  );
}
