WITH base AS (
  SELECT
    *,
    TO_DATE(accounting_date, 'MM/DD/YYYY') AS acct_date
  FROM stage_1
),
with_lag AS (
  SELECT
    *,
    LAG(accounting_date_balance) OVER (PARTITION BY worktag_id ORDER BY acct_date) AS prev_balance
  FROM base
),
recursive_avg AS (
  SELECT
    worktag_id,
    acct_date,
    accounting_date,
    accounting_date_balance,
    CAST(accounting_date_balance AS FLOAT) AS running_average_daily_balance,
    ROW_NUMBER() OVER (PARTITION BY worktag_id ORDER BY acct_date) AS rn
  FROM with_lag
  WHERE rn = 1

  UNION ALL

  SELECT
    curr.worktag_id,
    curr.acct_date,
    curr.accounting_date,
    curr.accounting_date_balance,
    /* 
    Whenever there is a new value in the accounting_date_balance which is different from the previous days accounting_date_balance, then average them together into the new column running_average_daily_balance.
    */
    CASE 
      WHEN curr.accounting_date_balance = prev.accounting_date_balance THEN prev.running_average_daily_balance
      ELSE (curr.accounting_date_balance + prev.running_average_daily_balance) / 2.0
    END AS running_average_daily_balance,
    curr.rn
  FROM with_lag curr
  JOIN recursive_avg prev
    ON curr.worktag_id = prev.worktag_id AND curr.rn = prev.rn + 1
)
SELECT
  worktag_id,
  accounting_date,
  accounting_date_balance,
  running_average_daily_balance
FROM recursive_avg
ORDER BY worktag_id, acct_date;