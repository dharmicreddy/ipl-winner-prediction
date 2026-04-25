{{ config(materialized='view') }}

SELECT
    venue_alias,
    wiki_title
FROM {{ source('silver_raw', 'venue_aliases') }}
