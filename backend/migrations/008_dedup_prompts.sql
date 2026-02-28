-- Remove duplicate prompts, keeping the lowest ID for each (name, prompt_type) pair
DELETE FROM prompts
WHERE id NOT IN (
    SELECT MIN(id) FROM prompts GROUP BY name, prompt_type
);
