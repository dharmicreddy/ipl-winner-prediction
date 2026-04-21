-- Migration 002: gold.fact_matches view
-- Phase 2 / Chunk 2.7

CREATE OR REPLACE VIEW gold.fact_matches AS
SELECT
    m.match_id,
    m.season,
    m.match_date,
    m.venue,
    m.city,
    m.team_home,
    m.team_away,
    m.toss_winner,
    m.toss_decision,
    -- Who actually batted first, derived from toss outcome.
    -- If toss winner chose bat, they batted first. If they chose field,
    -- the other team batted first.
    CASE
        WHEN m.toss_decision = 'bat' THEN m.toss_winner
        ELSE CASE WHEN m.toss_winner = m.team_home THEN m.team_away ELSE m.team_home END
    END AS batting_first,
    m.winner,
    m.win_margin_type,
    m.win_margin,
    m.method,
    m.player_of_match,
    -- Convenience flag for ML: did the team batting first win?
    CASE
        WHEN m.winner IS NULL THEN NULL
        WHEN m.winner = (
            CASE
                WHEN m.toss_decision = 'bat' THEN m.toss_winner
                ELSE CASE WHEN m.toss_winner = m.team_home THEN m.team_away ELSE m.team_home END
            END
        ) THEN true
        ELSE false
    END AS batting_first_won,
    m.raw_ingested_at,
    m.parsed_at
FROM silver.matches m
WHERE m.winner IS NOT NULL;  -- exclude rain-affected no-results from the fact table

INSERT INTO public.schema_migrations (version)
VALUES ('002_gold_fact_matches')
ON CONFLICT (version) DO NOTHING;
