/*
Problem : Recursive CTE SQLs have performance issues over large datasets.

Solution: Implement the same logic without recursion.

Assigns change groups : group numbers to balance streaks.
Averages new balance with previous running average only on change.
Carries that average forward over the group.

Take the average of the current balance 
and the previous day's running average.
*/


could you explain the logic behind the  "change_group" column in this SQL?  

WITH base AS (
    SELECT *,
        TO_DATE(accounting_date, 'MM/DD/YYYY') AS acct_date
    FROM stage_1
),
mark_changes AS (
    SELECT *,
        CASE 
            WHEN accounting_date_balance = LAG(accounting_date_balance) OVER (
                PARTITION BY worktag_id ORDER BY acct_date
            ) THEN 0
            ELSE 1
        END AS change_flag
    FROM base
),
grouped_changes AS (
    SELECT *,
        SUM(change_flag) OVER (
            PARTITION BY worktag_id ORDER BY acct_date
        ) AS change_group
    FROM mark_changes
),
group_with_seq AS (
    SELECT *,
        ROW_NUMBER() OVER (PARTITION BY worktag_id, change_group ORDER BY acct_date) AS row_in_group
    FROM grouped_changes
),
group_starting_balances AS (
    SELECT
        worktag_id,
        change_group,
        accounting_date_balance AS balance_value,
        acct_date AS group_start_date
    FROM group_with_seq
    WHERE row_in_group = 1
),
group_seq AS (
    SELECT *,
        ROW_NUMBER() OVER (PARTITION BY worktag_id ORDER BY group_start_date) AS group_seq
    FROM group_starting_balances
),
final_avgs AS (
    SELECT
        gws.worktag_id,
        gwc.accounting_date,
        gwc.acct_date,
        gwc.accounting_date_balance,
        gwc.change_group,
        gws.group_seq,
        gws.balance_value,
        LAG(gws.balance_value) OVER (
            PARTITION BY gws.worktag_id ORDER BY gws.group_seq
        ) AS prev_avg
    FROM group_with_seq gwc
    JOIN group_seq gws
      ON gwc.worktag_id = gws.worktag_id
     AND gwc.change_group = gws.change_group
),
final_result AS (
    SELECT
        worktag_id,
        accounting_date,
        accounting_date_balance,
        /* 
		Compute the average of the current row and the previous row's 
		accounting_date_balance.

		If it's different, take the average of the current balance 
		and the previous running average.
        */
        FIRST_VALUE(
            CASE 
                WHEN prev_avg IS NULL THEN balance_value
                WHEN balance_value = -prev_avg THEN 0
                ELSE (balance_value + prev_avg) / 2.0
            END
        ) OVER (
            PARTITION BY worktag_id, change_group ORDER BY acct_date
        ) AS daily_running_average_bal
    FROM final_avgs
)
SELECT *
FROM final_result
ORDER BY worktag_id, TO_DATE(accounting_date, 'MM/DD/YYYY');