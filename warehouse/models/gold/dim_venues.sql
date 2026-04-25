{{ config(materialized='view') }}

-- One row per canonical Wikipedia venue page. Joins venue aliases
-- so Cricsheet's various spellings of "Wankhede" all map to the same
-- canonical wiki_title.

SELECT
    v.wiki_title,
    v.display_title,
    v.description,
    v.latitude,
    v.longitude,
    v.wikipedia_url
FROM {{ ref('silver__venues') }} v
ORDER BY v.display_title
