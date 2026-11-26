-- dim_seller: one row per seller, with zip-prefix centroid coordinates.
CREATE OR REPLACE TABLE marts.dim_seller AS
SELECT
    s.seller_id,
    s.seller_zip_code_prefix AS zip_code_prefix,
    s.seller_city            AS city,
    s.seller_state           AS state,
    g.lat,
    g.lng
FROM staging.sellers AS s
LEFT JOIN staging.geolocation AS g ON g.zip_code_prefix = s.seller_zip_code_prefix;
