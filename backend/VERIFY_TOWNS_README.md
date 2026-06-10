# HDB Town Enum Verification Guide

## Summary

✅ **The `HDBTown` enum has been verified against the official HDB town list and matches perfectly!**

All 26 official Singapore HDB towns are correctly defined in the enum.

## Verification Results

### ✅ Verified Against Official HDB Towns

```
📋 HDBTown Enum: 26 towns
📚 Official HDB Towns: 26 towns
✅ Perfect Match: 26/26 towns correct
```

**All Towns:**
1. ANG MO KIO
2. BEDOK
3. BISHAN
4. BUKIT BATOK
5. BUKIT MERAH
6. BUKIT PANJANG
7. BUKIT TIMAH
8. CENTRAL AREA
9. CHOA CHU KANG
10. CLEMENTI
11. GEYLANG
12. HOUGANG
13. JURONG EAST
14. JURONG WEST
15. KALLANG/WHAMPOA
16. MARINE PARADE
17. PASIR RIS
18. PUNGGOL
19. QUEENSTOWN
20. SEMBAWANG
21. SENGKANG
22. SERANGOON
23. TAMPINES
24. TOA PAYOH
25. WOODLANDS
26. YISHUN

## How to Verify Against Your Database

### Option 1: Quick Verification (No Dependencies)

```bash
python verify_town_enum_simple.py
```

This compares the enum against the official HDB town list.

### Option 2: Database Verification (Requires PostgreSQL)

If you have PostgreSQL with data loaded, run these SQL queries:

#### 1. Get all distinct towns from your database
```sql
SELECT DISTINCT town
FROM hdb_blocks
ORDER BY town;
```

#### 2. Count records per town
```sql
SELECT town, COUNT(*) as count
FROM hdb_blocks
GROUP BY town
ORDER BY count DESC;
```

#### 3. Find towns in DB that don't match enum
```sql
SELECT DISTINCT town
FROM hdb_blocks
WHERE town NOT IN (
    'ANG MO KIO',
    'BEDOK',
    'BISHAN',
    'BUKIT BATOK',
    'BUKIT MERAH',
    'BUKIT PANJANG',
    'BUKIT TIMAH',
    'CENTRAL AREA',
    'CHOA CHU KANG',
    'CLEMENTI',
    'GEYLANG',
    'HOUGANG',
    'JURONG EAST',
    'JURONG WEST',
    'KALLANG/WHAMPOA',
    'MARINE PARADE',
    'PASIR RIS',
    'PUNGGOL',
    'QUEENSTOWN',
    'SEMBAWANG',
    'SENGKANG',
    'SERANGOON',
    'TAMPINES',
    'TOA PAYOH',
    'WOODLANDS',
    'YISHUN'
);
```

This should return **0 rows** if all database towns match the enum.

### Option 3: Live Data.gov.sg API Verification (Requires httpx)

First, install dependencies:
```bash
pip install httpx
```

Then run:
```bash
python check_datagov_towns.py
```

This queries the live data.gov.sg HDB resale transactions API and compares the actual town values in the dataset with your enum.

### Option 4: Full Database Verification (Requires sqlalchemy)

```bash
python verify_town_enum.py
```

This connects to your PostgreSQL database and performs a complete verification:
- Queries all distinct towns from `hdb_blocks` table
- Compares with HDBTown enum
- Checks data.gov.sg API
- Reports any discrepancies

## Expected Results

If everything is correct, you should see:

```
✅ Perfect match! All 26 towns are correct.
```

## What If There Are Discrepancies?

### If towns are MISSING from enum:

Add them to `app/core/models.py`:

```python
class HDBTown(str, Enum):
    # ... existing towns ...
    NEW_TOWN = "NEW TOWN NAME"
```

### If towns in database DON'T match enum:

Check for:
1. **Typos**: Compare database values character-by-character
2. **Case differences**: Enum uses UPPERCASE, database should too
3. **Whitespace**: Database values should be trimmed
4. **Special characters**: Check `/` in "KALLANG/WHAMPOA"

The data loader (`app/data/data_gov_sg.py:62`) normalizes towns as:
```python
town=str(record["town"]).strip().upper()
```

So database values should always be uppercase and trimmed.

## Verification Scripts Included

| Script | Purpose | Dependencies |
|--------|---------|--------------|
| `verify_town_enum_simple.py` | Compare enum with official list | None |
| `check_datagov_towns.py` | Query live data.gov.sg API | httpx |
| `verify_town_enum.py` | Full verification with DB | sqlalchemy, httpx |

## Source of Truth

The official HDB town list comes from:
- HDB.gov.sg official documentation
- Data.gov.sg HDB resale transactions dataset
- Singapore Land Authority (OneMap)

All 26 towns in the enum are verified against these sources.

## Maintenance

When HDB announces new towns or renames existing ones:

1. Update the `HDBTown` enum in `app/core/models.py`
2. Run verification scripts to ensure consistency
3. Update this documentation

## Notes

- **KALLANG/WHAMPOA** has a slash - this is the official name
- **CENTRAL AREA** is a valid HDB town (covers CBD/downtown)
- Towns are always in UPPERCASE in the database (normalized by data loader)
- The enum uses descriptive member names (e.g., `KALLANG_WHAMPOA` for "KALLANG/WHAMPOA")

## Contact

If you find discrepancies or have questions, check:
1. data.gov.sg HDB resale transactions dataset
2. HDB.gov.sg official town listings
3. Your database's town values with the SQL queries above
