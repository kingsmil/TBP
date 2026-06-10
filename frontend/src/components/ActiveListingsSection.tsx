import { useEffect, useState } from "react";
import { getBlockListings, prepareOutreachMessage } from "../lib/api";
import { formatSGD } from "../lib/format";
import type { ActiveListing, OutreachMessageResponse } from "../types";

// Photo paths from the portal are relative; this prefix is best-effort and the
// image hides itself on error, so a wrong/missing base never breaks the card.
const PHOTO_BASE = "https://static.homes.hdb.gov.sg/";

interface Props {
  blockId: number;
  caseId?: string;
}

export default function ActiveListingsSection({ blockId, caseId }: Props) {
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
          <ListingCard key={l.listing_id} listing={l} caseId={caseId} />
        ))}
      </div>
    </div>
  );
}

function ListingCard({ listing, caseId }: { listing: ActiveListing; caseId?: string }) {
  const [photoOk, setPhotoOk] = useState(true);
  const [outreach, setOutreach] = useState<OutreachMessageResponse | null>(null);
  const [preparing, setPreparing] = useState(false);
  const [copied, setCopied] = useState(false);

  async function handlePrepare() {
    setPreparing(true);
    try {
      const res = await prepareOutreachMessage(listing.listing_id, { case_id: caseId });
      setOutreach(res);
    } catch {
      setOutreach(null);
    } finally {
      setPreparing(false);
    }
  }

  async function handleCopy() {
    if (!outreach) return;
    await navigator.clipboard.writeText(outreach.message);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

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
      {!outreach && (
        <button
          type="button"
          className="mt-1 w-full rounded-md border border-input px-2 py-1.5 text-xs font-semibold text-foreground hover:bg-muted disabled:opacity-50"
          disabled={preparing}
          onClick={handlePrepare}
        >
          {preparing ? "Preparing…" : "Prepare message"}
        </button>
      )}
      {outreach && (
        <div className="mt-1 space-y-2 rounded border border-emerald-100 bg-emerald-50 p-2">
          <p className="text-xs leading-relaxed text-emerald-900 whitespace-pre-wrap">
            {outreach.message}
          </p>
          <div className="flex flex-wrap gap-1.5">
            {outreach.whatsapp_url && (
              <a
                href={outreach.whatsapp_url}
                target="_blank"
                rel="noreferrer"
                className="rounded bg-emerald-600 px-2 py-1 text-xs font-semibold text-white"
              >
                Open in WhatsApp
              </a>
            )}
            <button
              type="button"
              onClick={handleCopy}
              className="rounded border border-emerald-300 px-2 py-1 text-xs font-semibold text-emerald-800"
            >
              {copied ? "Copied!" : "Copy message"}
            </button>
            {outreach.email_url && (
              <a
                href={outreach.email_url}
                className="rounded border border-emerald-300 px-2 py-1 text-xs font-semibold text-emerald-800"
              >
                Email
              </a>
            )}
          </div>
          {!outreach.whatsapp_url && (
            <p className="text-[11px] text-emerald-700">
              Contact this seller via the HDB Flat Portal and paste this message.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
