-- Normalize inconsistent opportunity/agency names in prompts table

-- Trim trailing whitespace from opportunity and agency
UPDATE prompts SET opportunity = TRIM(opportunity) WHERE opportunity != TRIM(opportunity);
UPDATE prompts SET agency = TRIM(agency) WHERE agency IS NOT NULL AND agency != TRIM(agency);

-- Trim trailing whitespace from prompt names
UPDATE prompts SET name = TRIM(name) WHERE name != TRIM(name);

-- Standardize "US Regional News Networks" variants to singular hyphen form
-- Covers: em dash, en dash, regular hyphen, plural/singular, encoding artifacts
UPDATE prompts SET opportunity = 'US Regional News Network - Baseline'
WHERE LOWER(TRIM(opportunity)) LIKE 'us regional news network%baseline';

UPDATE prompts SET agency = 'US Regional News Network - Baseline'
WHERE LOWER(TRIM(agency)) LIKE 'us regional news network%baseline';

-- Fix double-space in names caused by trailing space in opportunity
UPDATE prompts SET name = REPLACE(name, '  - ', ' - ') WHERE name LIKE '%  - %';
