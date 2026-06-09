import { useEffect, useState } from "react";
import { getBlockListings } from "../lib/api";
import { formatSGD } from "../lib/format";
import type { ActiveListing } from "../types";

// Photo paths from the portal are relative; this prefix is best-effort and the
// image hides itself on error, so a wrong/missing base never breaks the card.
const PHOTO_BASE = "https://static.homes.hdb.gov.sg/";

interface Props {
  blockId: number;
}

export default function ActiveListingsSection({ blockId }: Props) {
  const [listings, setListings] = useState<ActiveListing[] | null>(null);

  useEffect(() => {
    setListings(null);
    getBlockListings(blockId)
      .then((res) => setListings(res.listings))
      .catch(() => setListings([]));
  }, [blockId]);

  if (!listings || listings.length === 0) return null;

  return (
    <div className="p-4 border-b border-border">
      <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-1">
        On the market now
      </p>
      <p className="text-xs text-muted-foreground mb-3">
        {listings.length} unit{listings.length === 1 ? "" : "s"} listed in this block
      </p>
      <div className="space-y-3">
        {listings.map((l) => (
          <ListingCard key={l.listing_id} listing={l} />
        ))}
      </div>
    </div>
  );
}

function ListingCard({ listing }: { listing: ActiveListing }) {
  const [photoOk, setPhotoOk] = useState(true);
  return (
    <div className="rounded-md border border-border bg-background p-3 space-y-1">
      {listing.photo_path && photoOk && (
        <img
          src={`${PHOTO_BASE}${listing.photo_path}`}
          alt=""
          loading="lazy"
          className="mb-1 h-24 w-full rounded object-cover"
          onError={() => setPhotoOk(false)}
        />
      )}
      <p className="text-sm font-bold text-foreground">{formatSGD(listing.price)}</p>
      <p className="text-xs text-muted-foreground">
        {listing.flat_type} · {listing.floor_area_sqm} sqm · {listing.storey_range}
      </p>
      <p className="text-xs text-muted-foreground">Lease left: {listing.remaining_lease}</p>
      {listing.description && (
        <p className="text-xs text-muted-foreground line-clamp-2">{listing.description}</p>
      )}
      {(listing.agent_name || listing.agency_name) && (
        <p className="text-xs font-medium text-foreground">
          {[listing.agent_name, listing.agency_name].filter(Boolean).join(" · ")}
        </p>
      )}
    </div>
  );
}
