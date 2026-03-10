from __future__ import annotations

REVIEW_IMPORTS_TEMPLATE = """You are reviewing recently imported bank transactions in Firefly III.

Follow these steps:

1. First, call get_financial_context("all") to learn what categories, tags, and budgets exist.

2. Then call get_review_queue(days_back={days_back}) to see transactions needing review.

3. For each transaction, analyze the description and amount to determine:
   - Category (e.g., Dining, Transport, Shopping, Subscriptions, Groceries)
   - Tags (e.g., restaurant, grab, subscription, online-shopping)
   - Budget (e.g., Eating Out, Transport, Personal Spending, Tech)
   - Notes (optional, for additional context)

4. Present your proposed categorizations to the user in a clear table format.
   Group similar transactions together. Ask the user to confirm or adjust.

5. Once confirmed, call categorize_transactions with all the updates.

6. Report the results: how many succeeded, any failures.

Tips for categorization:
- Look for merchant keywords: GRAB = transport/food delivery, SHOPEE/LAZADA = online shopping
- Recurring similar amounts = likely subscriptions
- If unsure, ask the user rather than guessing
- Create new tags/categories via manage_metadata if needed
"""


MONTHLY_REVIEW_TEMPLATE = """You are conducting a monthly financial review for {month}.

Follow these steps:

1. Call get_spending_summary(period="{start}:{end}", group_by="budget") to see budget performance.

2. Call get_spending_summary(period="{start}:{end}", group_by="category") for category breakdown.

3. Check for uncategorized transactions: get_review_queue(days_back=31, filter="all_unreviewed")

4. Present a summary to the user:
   - Budget performance: which budgets are over/under, remaining amounts
   - Top spending categories
   - Any uncategorized transactions that need attention
   - Notable patterns or anomalies (unusually large transactions, new merchants)

5. Ask if they want to:
   - Categorize remaining transactions
   - Adjust any budget limits for next month
   - Tag specific transactions for tracking
"""
