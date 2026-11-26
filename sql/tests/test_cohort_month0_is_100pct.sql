-- By definition every cohort is 100% active in its first month.
SELECT cohort_month, retention_pct
FROM analysis.cohort_retention
WHERE months_since_first = 0 AND retention_pct <> 100;
