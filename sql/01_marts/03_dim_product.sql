-- dim_product: one row per product, English category names.
CREATE OR REPLACE TABLE marts.dim_product AS
SELECT
    product_id,
    product_category,
    product_category_pt,
    product_name_length,
    product_description_length,
    product_photos_qty,
    product_weight_g,
    product_length_cm,
    product_height_cm,
    product_width_cm,
    product_volume_cm3,
    has_missing_dims
FROM staging.products;
