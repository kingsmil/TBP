import { useQuery } from "@tanstack/react-query";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "./ui/select";
import { getModels } from "@/lib/api";

interface ModelSelectorProps {
  value: string;
  onChange: (model: string) => void;
}

export default function ModelSelector({ value, onChange }: ModelSelectorProps) {
  const { data, isLoading } = useQuery({
    queryKey: ["models"],
    queryFn: getModels,
    staleTime: 1000 * 60 * 60, // 1 hour
  });

  if (isLoading || !data) {
    return null;
  }

  return (
    <div className="flex items-center gap-2">
      <label className="text-xs text-muted-foreground whitespace-nowrap">
        Model:
      </label>
      <Select value={value} onValueChange={onChange}>
        <SelectTrigger className="h-8 w-[200px] text-xs">
          <SelectValue placeholder="Select model..." />
        </SelectTrigger>
        <SelectContent>
          {data.models.map((model) => (
            <SelectItem key={model.id} value={model.id} className="text-xs">
              <span className="font-medium">{model.name}</span>
              <span className="ml-2 text-muted-foreground">
                ({model.provider})
              </span>
            </SelectItem>
          ))}
          <div className="border-t border-border mt-1 px-2 py-1.5 text-[10px] leading-snug text-muted-foreground">
            Explore different models for different opinions.
          </div>
        </SelectContent>
      </Select>
    </div>
  );
}
