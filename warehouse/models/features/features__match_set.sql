{{ config(materialized='view') }}

-- One wide row per match: all features + the label + a walk-forward split
-- assignment. This is the table Phase 6 reads to train and evaluate.
--
-- Split policy (per ADR-004 and ADR-007):
--   - train:   2022 season (74 matches)
--   - val:     2023 season, matches before 2023-05-01 (~early-season)
--   - holdout: 2023 season after 2023-05-01 + all of 2024
--
-- Walk-forward evaluation: model trains on train, hyper-tunes on val,
-- final metrics computed on holdout — strictly later than both.

SELECT
    -- Identifiers and context
    m.match_id,
    m.match_date,
    m.season,
    m.team_home,
    m.team_away,
    m.venue,
    m.city,
    m.toss_winner,
    m.toss_decision,
    m.batting_first,

    -- Features: team form
    tf.team_home_form_5,
    tf.team_away_form_5,

    -- Features: head-to-head
    h2h.h2h_matches_played,
    h2h.team_home_h2h_wins,
    h2h.team_home_h2h_win_rate,

    -- Features: venue
    ve.venue_matches_played,
    ve.venue_bat_first_win_rate,

    -- Features: temporal
    tm.days_since_team_home_last_match,
    tm.days_since_team_away_last_match,
    tm.match_number_in_season,

    -- Label
    m.batting_first_won,

    -- Walk-forward split
    CASE
        WHEN m.season = '2022' THEN 'train'
        WHEN m.season = '2023' AND m.match_date < '2023-05-01' THEN 'val'
        ELSE 'holdout'
    END AS split

FROM {{ ref('fact_matches') }} m
LEFT JOIN {{ ref('features__team_form') }} tf ON m.match_id = tf.match_id
LEFT JOIN {{ ref('features__head_to_head') }} h2h ON m.match_id = h2h.match_id
LEFT JOIN {{ ref('features__venue_effects') }} ve ON m.match_id = ve.match_id
LEFT JOIN {{ ref('features__temporal') }} tm ON m.match_id = tm.match_id
ORDER BY m.match_date
