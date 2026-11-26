-- Category revenue shares must sum to 100% and the last cumulative share must be 100%.
SELECT round(sum(revenue_share_pct), 1) AS total_share, max(cumulative_share_pct) AS final_cum
FROM analysis.category_pareto
HAVING abs(sum(revenue_share_pct) - 100) > 0.1 OR abs(max(cumulative_share_pct) - 100) > 0.01;
