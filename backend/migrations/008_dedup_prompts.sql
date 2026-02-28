-- Remove duplicate prompts, keeping the lowest ID for each (name, prompt_type) pair.
-- Reassign FK references in stories and pipeline_runs before deleting.

-- Reassign stories FK references from duplicates to keepers
UPDATE stories SET source_list_prompt_id = keeper.keep_id
FROM (SELECT MIN(id) as keep_id, name, prompt_type FROM prompts GROUP BY name, prompt_type) keeper
JOIN prompts p ON p.name = keeper.name AND p.prompt_type = keeper.prompt_type AND p.id != keeper.keep_id
WHERE stories.source_list_prompt_id = p.id;

UPDATE stories SET refinement_prompt_id = keeper.keep_id
FROM (SELECT MIN(id) as keep_id, name, prompt_type FROM prompts GROUP BY name, prompt_type) keeper
JOIN prompts p ON p.name = keeper.name AND p.prompt_type = keeper.prompt_type AND p.id != keeper.keep_id
WHERE stories.refinement_prompt_id = p.id;

UPDATE stories SET amy_bot_prompt_id = keeper.keep_id
FROM (SELECT MIN(id) as keep_id, name, prompt_type FROM prompts GROUP BY name, prompt_type) keeper
JOIN prompts p ON p.name = keeper.name AND p.prompt_type = keeper.prompt_type AND p.id != keeper.keep_id
WHERE stories.amy_bot_prompt_id = p.id;

-- Reassign pipeline_runs FK references
UPDATE pipeline_runs SET prompt_id = keeper.keep_id
FROM (SELECT MIN(id) as keep_id, name, prompt_type FROM prompts GROUP BY name, prompt_type) keeper
JOIN prompts p ON p.name = keeper.name AND p.prompt_type = keeper.prompt_type AND p.id != keeper.keep_id
WHERE pipeline_runs.prompt_id = p.id;

-- Now safe to delete duplicates
DELETE FROM prompts
WHERE id NOT IN (
    SELECT MIN(id) FROM prompts GROUP BY name, prompt_type
);
