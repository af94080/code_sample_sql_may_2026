# The `change_group` Column Explained

`change_group` is a session/island identifier — it assigns the same number to consecutive rows that share the same `accounting_date_balance`, and increments whenever the balance changes.

It's built across two steps:

## Step 1: `change_flag` (in `mark_changes`)

```sql
CASE 
    WHEN accounting_date_balance = LAG(accounting_date_balance) OVER (
        PARTITION BY worktag_id ORDER BY acct_date
    ) THEN 0
    ELSE 1
END AS change_flag
```

For each row, this looks at the previous row's balance (within the same `worktag_id`). If the balance is the same → `0`. If it changed (or it's the first row, where `LAG` returns `NULL`) → `1`.

| acct_date | balance | change_flag |
|-----------|---------|-------------|
| Jan 1 | 100 | 1 ← first row, no prior |
| Jan 2 | 100 | 0 ← same as before |
| Jan 3 | 200 | 1 ← changed! |
| Jan 4 | 200 | 0 ← same as before |
| Jan 5 | 300 | 1 ← changed! |

## Step 2: `change_group` (in `grouped_changes`)

```sql
SUM(change_flag) OVER (
    PARTITION BY worktag_id ORDER BY acct_date
) AS change_group
```

This takes a running sum of those flags. Because flags only increment on a change, rows with the same balance form a flat plateau in the running sum — giving them identical group numbers.

| acct_date | balance | change_flag | change_group |
|-----------|---------|-------------|--------------|
| Jan 1 | 100 | 1 | 1 |
| Jan 2 | 100 | 0 | 1 |
| Jan 3 | 200 | 1 | 2 |
| Jan 4 | 200 | 0 | 2 |
| Jan 5 | 300 | 1 | 3 |

## Why it matters downstream

`change_group` becomes the backbone for the rest of the query:

- **`group_with_seq`** uses it to number rows within each stable-balance period
- **`group_starting_balances`** uses `row_in_group = 1` to grab just the first row of each group (i.e., the balance at the moment it changed)
- **`final_avgs`** joins on it to pull in each group's starting balance and the previous group's balance — which is what powers the `daily_running_average_bal` calculation at the end

In short, it turns a stream of values into labeled contiguous segments so you can reason about each stable period as a unit.
