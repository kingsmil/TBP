-- ============================================================================
-- HDB Town Enum Verification SQL Queries
-- ============================================================================
-- Run these queries against your PostgreSQL database to verify that
-- the HDBTown enum matches the actual town values in your data.
-- ============================================================================

-- Query 1: Get all distinct towns (should match the 26 enum values)
-- ============================================================================
SELECT DISTINCT town
FROM hdb_blocks
ORDER BY town;

-- Expected Result: 26 rows matching the HDBTown enum values
-- If you get different results, the enum needs to be updated


-- Query 2: Count how many blocks per town
-- ============================================================================
SELECT
    town,
    COUNT(*) as block_count,
    MIN(lease_commencement_year) as oldest_lease,
    MAX(lease_commencement_year) as newest_lease
FROM hdb_blocks
GROUP BY town
ORDER BY block_count DESC;

-- This helps verify that all towns have data and shows the distribution


-- Query 3: Find any towns that DON'T match the enum
-- ============================================================================
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

-- Expected Result: 0 rows
-- If you get any rows, those towns are in your DB but NOT in the enum


-- Query 4: Find enum values that DON'T appear in database
-- ============================================================================
WITH enum_towns AS (
    SELECT 'ANG MO KIO' as town UNION ALL
    SELECT 'BEDOK' UNION ALL
    SELECT 'BISHAN' UNION ALL
    SELECT 'BUKIT BATOK' UNION ALL
    SELECT 'BUKIT MERAH' UNION ALL
    SELECT 'BUKIT PANJANG' UNION ALL
    SELECT 'BUKIT TIMAH' UNION ALL
    SELECT 'CENTRAL AREA' UNION ALL
    SELECT 'CHOA CHU KANG' UNION ALL
    SELECT 'CLEMENTI' UNION ALL
    SELECT 'GEYLANG' UNION ALL
    SELECT 'HOUGANG' UNION ALL
    SELECT 'JURONG EAST' UNION ALL
    SELECT 'JURONG WEST' UNION ALL
    SELECT 'KALLANG/WHAMPOA' UNION ALL
    SELECT 'MARINE PARADE' UNION ALL
    SELECT 'PASIR RIS' UNION ALL
    SELECT 'PUNGGOL' UNION ALL
    SELECT 'QUEENSTOWN' UNION ALL
    SELECT 'SEMBAWANG' UNION ALL
    SELECT 'SENGKANG' UNION ALL
    SELECT 'SERANGOON' UNION ALL
    SELECT 'TAMPINES' UNION ALL
    SELECT 'TOA PAYOH' UNION ALL
    SELECT 'WOODLANDS' UNION ALL
    SELECT 'YISHUN'
)
SELECT e.town
FROM enum_towns e
LEFT JOIN hdb_blocks h ON e.town = h.town
WHERE h.town IS NULL;

-- Expected Result: 0 rows (all enum towns should exist in DB)
-- If you get rows, those towns are in the enum but not in your data
-- This is OK if you have limited/sample data


-- Query 5: Verify town names have correct formatting (no typos, correct case)
-- ============================================================================
SELECT DISTINCT town
FROM hdb_blocks
WHERE
    town != UPPER(TRIM(town))  -- Should be uppercase and trimmed
    OR town LIKE '%  %'        -- Should not have double spaces
ORDER BY town;

-- Expected Result: 0 rows
-- All town names should be UPPERCASE and properly trimmed


-- Query 6: Check for potential data quality issues
-- ============================================================================
SELECT
    town,
    COUNT(*) as block_count,
    COUNT(DISTINCT postal_code) as unique_postcodes,
    COUNT(*) FILTER (WHERE planning_area_id IS NULL) as missing_planning_area
FROM hdb_blocks
GROUP BY town
ORDER BY town;

-- Review: Each town should have multiple blocks and postcodes
-- planning_area_id might be NULL if not yet geocoded


-- ============================================================================
-- Summary Query: Overall Statistics
-- ============================================================================
SELECT
    COUNT(DISTINCT town) as total_towns,
    COUNT(*) as total_blocks,
    MIN(lease_commencement_year) as oldest_block,
    MAX(lease_commencement_year) as newest_block
FROM hdb_blocks;

-- Expected:
--   total_towns: 26 (matching HDBTown enum)
--   total_blocks: depends on your data
--   oldest_block: ~1960s-1970s
--   newest_block: ~2020s


-- ============================================================================
-- How to Run These Queries
-- ============================================================================
--
-- Option 1: Using psql command line
--   psql -U postgres -d your_database -f SQL_VERIFY_TOWNS.sql
--
-- Option 2: Using pgAdmin or other GUI tool
--   Copy and paste each query individually
--
-- Option 3: Using Python script
--   python verify_town_enum.py
--
-- ============================================================================
