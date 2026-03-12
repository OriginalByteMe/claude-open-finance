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


SETUP_AUTOMATION_TEMPLATE = """You are helping set up an automation rule in Firefly III.

Follow these steps:

1. Ask the user what they want to automate in plain language.
   Examples: "Tag all Starbucks transactions as coffee", "Categorize GRAB as Transport",
   "Set budget to 'Eating Out' for any restaurant transactions".

2. Call get_automation_context() to see available trigger keywords, action keywords,
   and existing rule groups.

3. Call get_financial_context("all") to know existing categories, tags, budgets, accounts.

4. Translate the user's intent into a rule definition:
   - Choose appropriate trigger type(s) (description_contains, amount_more, etc.)
   - Choose appropriate action(s) (set_category, add_tag, set_budget, etc.)
   - Decide if triggers should use AND logic (strict=true) or OR logic (strict=false)
   - Pick or create a rule group for organization

5. Present the proposed rule to the user in a clear format:
   ```
   Rule: "Starbucks → Coffee"
   Group: Auto-categorize
   When: Transaction is created
   If ALL match:
     - Description contains "STARBUCKS"
     - Type is withdrawal
   Then:
     - Set category to "Food & Dining"
     - Add tag "coffee"
   ```

6. Once confirmed, call manage_automations(action="create", ...) to create the rule.

7. Call test_automation(rule_id=X) to show which existing transactions would match.
   Present the results: "This rule would match 12 existing transactions."

8. Ask if the user wants to fire the rule on existing transactions:
   - If yes, call test_automation(rule_id=X, execute=true)
   - Report how it went

Tips:
- If the user needs a category/tag/budget that doesn't exist, create it first via manage_metadata
- Use strict=true (AND) by default — it's safer
- Prefer description_contains over description_is for flexibility
- Suggest grouping related rules (e.g., all food rules in "Food & Dining" group)
"""
