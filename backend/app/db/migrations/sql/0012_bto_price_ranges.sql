-- BTO selling-price ranges by financial year / town / room type, from
-- data.gov.sg collection 177 ("Price Range of HDB Flats Offered").
-- Ingested by app.data.bto, refreshed in the background.

CREATE TABLE IF NOT EXISTS bto_price_ranges (
    id                   SERIAL PRIMARY KEY,
    financial_year       INT NOT NULL,
    town                 TEXT NOT NULL,
    room_type            TEXT NOT NULL,
    min_selling_price    INT,
    max_selling_price    INT,
    min_price_less_grant INT,   -- after AHG/SHG grants
    max_price_less_grant INT,
    UNIQUE (financial_year, town, room_type)
);

CREATE INDEX IF NOT EXISTS idx_bto_price_year ON bto_price_ranges(financial_year);
CREATE INDEX IF NOT EXISTS idx_bto_price_town ON bto_price_ranges(town);
