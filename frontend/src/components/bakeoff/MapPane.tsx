import { Suspense, lazy } from "react";
import type { BlockSummary } from "../../types";

// Reuse the existing (heavy) MapView untouched — wrap, don't rewrite.
const MapView = lazy(() => import("../MapView"));

interface Props {
  blocks: BlockSummary[];
  selectedId: number | null;
  onSelectBlock: (id: number) => void;
}

export default function MapPane({ blocks, selectedId, onSelectBlock }: Props) {
  return (
    <div className="relative h-full w-full overflow-hidden">
      <Suspense fallback={<div className="flex h-full items-center justify-center bg-muted/40 text-sm text-muted-foreground">Loading map…</div>}>
        <MapView
          blocks={blocks}
          selectedBlockId={selectedId}
          onSelectBlock={onSelectBlock}
          hasSelectedProperty={selectedId != null}
        />
      </Suspense>
    </div>
  );
}
