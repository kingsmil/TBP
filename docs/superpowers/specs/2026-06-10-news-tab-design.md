# News Tab — Design Spec

**Date:** 2026-06-10  
**Status:** Approved

---

## Overview

Add a "News" tab to the top of the right panel in AI mode, alongside the existing "Display" tab. When active, it shows the 10 most recent Singapore HDB resale and BTO property news items fetched live from Exa's search API.

---

## Architecture & Data Flow

1. User clicks the **News** tab → `rightTab` state in `App.tsx` switches to `"news"`
2. `useQuery(['news'], getNews, { enabled: rightTab === 'news' })` fires on first open; React Query caches the result for the session (no refetch on re-open)
3. Frontend calls `GET /api/news`
4. FastAPI handler calls `https://api.exa.ai/search` via httpx:
   - `query`: `"Latest Singapore resale and BTO HDB property market news"`
   - `numResults`: 10
   - `type`: `"news"`
5. Backend strips the response to `[{ title, url, published_date, domain }]` and returns it
6. `NewsPanel` renders the list

---

## Components

### Backend

**`backend/app/api/schemas.py`**  
Add `NewsItem` Pydantic model:
```python
class NewsItem(BaseModel):
    title: str
    url: str
    published_date: str | None = None
    domain: str | None = None
```

**`backend/app/api/main.py`**  
Add `GET /api/news` route:
- Returns `list[NewsItem]`
- Returns HTTP 503 if `settings.exa_api_key` is `None`
- Returns HTTP 502 on any Exa API error
- Calls Exa via httpx with `Authorization: Bearer {exa_api_key}`

### Frontend

**`frontend/src/types.ts`**  
Add:
```ts
export interface NewsItem {
  title: string;
  url: string;
  published_date: string | null;
  domain: string | null;
}
```

**`frontend/src/lib/api.ts`**  
Add:
```ts
export async function getNews(): Promise<NewsItem[]> {
  return getJSON<NewsItem[]>("/news");
}
```

**`frontend/src/components/NewsPanel.tsx`**  
New component. Renders a scrollable list of news items. Each item:
- Title as `<a href={url} target="_blank" rel="noreferrer">` 
- Muted secondary line: `domain · date` (date formatted as `DD MMM YYYY` if parseable, otherwise raw)

States handled: loading (spinner or "Loading…"), error (message), empty (no results message).

**`frontend/src/App.tsx`**  
- Add `rightTab: "display" | "news"` state, default `"display"`
- Replace the static `DisplayPanel` render in the right `<aside>` with:
  - A two-tab bar at the top ("Display" / "News"), styled consistently with existing panel headers
  - Conditional render: `rightTab === "display"` → `<DisplayPanel .../>`, else `<NewsPanel />`

---

## Error Handling

| Condition | Backend | Frontend display |
|---|---|---|
| `EXA_API_KEY` not set | 503 | "News unavailable — API key not configured" |
| Exa API returns error | 502 | "Failed to load news — try again later" |
| Empty results | 200 `[]` | "No news found" |
| Loading | — | "Loading…" or spinner |

---

## Out of Scope

- Caching / Redis TTL (future enhancement if traffic warrants)
- Exa monitor webhook integration
- News in Explore mode (right panel only exists in AI mode)
- Pagination or infinite scroll
