-- Populate agency column from opportunity for source-list prompts
UPDATE prompts SET agency = opportunity
WHERE prompt_type = 'source-list' AND opportunity IS NOT NULL AND (agency IS NULL OR agency = '');
