{{ config(materialized='view') }}

SELECT
    wiki_title,
    display_title,
    description,
    extract,
    latitude,
    longitude,
    wikipedia_url,
    content_sha256,
    raw_response_id,
    parsed_at
FROM {{ source('silver_raw', 'venues') }}
