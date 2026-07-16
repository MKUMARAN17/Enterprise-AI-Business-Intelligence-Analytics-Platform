"""A ready-to-use enterprise BI catalog so the app can boot with an index.

Rather than force every deployment to wire up schema introspection before the
SQL agent can answer anything, :func:`default_catalog` ships a realistic,
hand-authored snapshot of the platform's core MySQL schema plus the business
glossary the product team maintains. It is deliberately hard-coded (not read
from a live database) so unit tests and local development have a stable,
network-free corpus, and so the retrieval behaviour under test is reproducible.

All table and column names are UPPERCASE to match the production MySQL
convention; foreign keys are rendered as directed edges so the retriever can
hand the SQL agent join hints verbatim.
"""

from __future__ import annotations

from .models import ColumnDoc, GlossaryDoc, TableDoc


def default_catalog() -> tuple[list[TableDoc], list[GlossaryDoc]]:
    """Return ``(tables, glossary)`` describing the core BI schema.

    The lists are freshly built on each call so callers can safely mutate the
    returned Python lists (e.g. append site-specific tables) without touching a
    shared module-level object. The dataclasses themselves are frozen.
    """
    tables: list[TableDoc] = [
        TableDoc(
            name="BRANCHES",
            description=(
                "Physical branch/office locations of the organization; the "
                "geographic and organizational dimension most reports slice by."
            ),
            columns=(
                ColumnDoc("BRANCH_ID", "INT", "Primary key identifying the branch."),
                ColumnDoc("BRANCH_NAME", "VARCHAR(128)", "Human-readable branch name."),
                ColumnDoc("REGION", "VARCHAR(64)", "Region or zone the branch belongs to."),
                ColumnDoc("CITY", "VARCHAR(64)", "City where the branch operates."),
                ColumnDoc("MANAGER_ID", "INT", "EMPLOYEE_ID of the branch manager."),
                ColumnDoc("OPENED_ON", "DATE", "Date the branch was opened."),
                ColumnDoc("IS_ACTIVE", "TINYINT", "1 if the branch is currently operating."),
            ),
            relationships=("BRANCHES.MANAGER_ID -> EMPLOYEES.EMPLOYEE_ID",),
            business_terms=("branch", "location", "office", "region performance"),
        ),
        TableDoc(
            name="COLLECTIONS",
            description=(
                "Amounts collected against outstanding invoices/receivables, "
                "used to measure collection performance and recovery per branch."
            ),
            columns=(
                ColumnDoc("COLLECTION_ID", "BIGINT", "Primary key for the collection record."),
                ColumnDoc("BRANCH_ID", "INT", "Branch that made the collection."),
                ColumnDoc("INVOICE_ID", "BIGINT", "Invoice the collection is applied to."),
                ColumnDoc("CUSTOMER_ID", "BIGINT", "Customer the amount was collected from."),
                ColumnDoc("AMOUNT_COLLECTED", "DECIMAL(14,2)", "Amount actually collected."),
                ColumnDoc("AMOUNT_DUE", "DECIMAL(14,2)", "Amount that was due on the invoice."),
                ColumnDoc("COLLECTED_ON", "DATE", "Date the collection was recorded."),
                ColumnDoc("COLLECTOR_ID", "INT", "Employee who performed the collection."),
            ),
            relationships=(
                "COLLECTIONS.BRANCH_ID -> BRANCHES.BRANCH_ID",
                "COLLECTIONS.CUSTOMER_ID -> CUSTOMERS.CUSTOMER_ID",
                "COLLECTIONS.COLLECTOR_ID -> EMPLOYEES.EMPLOYEE_ID",
                "COLLECTIONS.INVOICE_ID -> PAYMENTS.INVOICE_ID",
            ),
            business_terms=(
                "collection performance",
                "collections",
                "recovery rate",
                "amount collected",
                "receivables",
            ),
        ),
        TableDoc(
            name="REVENUE",
            description=(
                "Recognized revenue by branch and period; the primary fact "
                "table for revenue trend and growth analysis."
            ),
            columns=(
                ColumnDoc("REVENUE_ID", "BIGINT", "Primary key for the revenue record."),
                ColumnDoc("BRANCH_ID", "INT", "Branch the revenue is attributed to."),
                ColumnDoc("PRODUCT_ID", "INT", "Product line generating the revenue."),
                ColumnDoc("PERIOD_MONTH", "DATE", "First day of the accounting month."),
                ColumnDoc("GROSS_REVENUE", "DECIMAL(16,2)", "Gross revenue before adjustments."),
                ColumnDoc("NET_REVENUE", "DECIMAL(16,2)", "Net revenue after discounts/refunds."),
            ),
            relationships=(
                "REVENUE.BRANCH_ID -> BRANCHES.BRANCH_ID",
                "REVENUE.PRODUCT_ID -> PRODUCTS.PRODUCT_ID",
            ),
            business_terms=("revenue", "revenue trend", "topline", "net revenue", "growth"),
        ),
        TableDoc(
            name="SALES",
            description=(
                "Individual sales transactions (order lines) capturing what was "
                "sold, to whom, by which employee, and for how much."
            ),
            columns=(
                ColumnDoc("SALE_ID", "BIGINT", "Primary key for the sale."),
                ColumnDoc("BRANCH_ID", "INT", "Branch where the sale occurred."),
                ColumnDoc("CUSTOMER_ID", "BIGINT", "Customer who purchased."),
                ColumnDoc("PRODUCT_ID", "INT", "Product that was sold."),
                ColumnDoc("EMPLOYEE_ID", "INT", "Salesperson credited with the sale."),
                ColumnDoc("QUANTITY", "INT", "Units sold."),
                ColumnDoc("UNIT_PRICE", "DECIMAL(12,2)", "Price per unit at time of sale."),
                ColumnDoc("SALE_AMOUNT", "DECIMAL(14,2)", "Total transaction amount."),
                ColumnDoc("SOLD_ON", "DATE", "Date of the sale."),
            ),
            relationships=(
                "SALES.BRANCH_ID -> BRANCHES.BRANCH_ID",
                "SALES.CUSTOMER_ID -> CUSTOMERS.CUSTOMER_ID",
                "SALES.PRODUCT_ID -> PRODUCTS.PRODUCT_ID",
                "SALES.EMPLOYEE_ID -> EMPLOYEES.EMPLOYEE_ID",
            ),
            business_terms=("sales", "orders", "transactions", "units sold", "sales volume"),
        ),
        TableDoc(
            name="EMPLOYEES",
            description=(
                "Master record of staff, their role, branch assignment, and "
                "reporting line; the people dimension for workforce reporting."
            ),
            columns=(
                ColumnDoc("EMPLOYEE_ID", "INT", "Primary key identifying the employee."),
                ColumnDoc("FULL_NAME", "VARCHAR(128)", "Employee's full name."),
                ColumnDoc("BRANCH_ID", "INT", "Branch the employee is assigned to."),
                ColumnDoc("ROLE", "VARCHAR(64)", "Job role/title."),
                ColumnDoc("DEPARTMENT", "VARCHAR(64)", "Department the employee works in."),
                ColumnDoc("MANAGER_ID", "INT", "EMPLOYEE_ID of the direct manager."),
                ColumnDoc("HIRED_ON", "DATE", "Date the employee was hired."),
                ColumnDoc("IS_ACTIVE", "TINYINT", "1 if currently employed."),
            ),
            relationships=(
                "EMPLOYEES.BRANCH_ID -> BRANCHES.BRANCH_ID",
                "EMPLOYEES.MANAGER_ID -> EMPLOYEES.EMPLOYEE_ID",
            ),
            business_terms=("employee", "staff", "headcount", "workforce", "salesperson"),
        ),
        TableDoc(
            name="EMPLOYEE_PERFORMANCE",
            description=(
                "Periodic performance metrics per employee (targets vs. actuals, "
                "scores, rankings) used for employee performance comparison."
            ),
            columns=(
                ColumnDoc("PERFORMANCE_ID", "BIGINT", "Primary key for the review record."),
                ColumnDoc("EMPLOYEE_ID", "INT", "Employee being evaluated."),
                ColumnDoc("BRANCH_ID", "INT", "Branch at time of evaluation."),
                ColumnDoc("PERIOD_MONTH", "DATE", "First day of the evaluation month."),
                ColumnDoc("SALES_TARGET", "DECIMAL(14,2)", "Sales target for the period."),
                ColumnDoc("SALES_ACTUAL", "DECIMAL(14,2)", "Actual sales achieved."),
                ColumnDoc("PERFORMANCE_SCORE", "DECIMAL(5,2)", "Composite performance score."),
                ColumnDoc("RANK_IN_BRANCH", "INT", "Rank within the branch for the period."),
            ),
            relationships=(
                "EMPLOYEE_PERFORMANCE.EMPLOYEE_ID -> EMPLOYEES.EMPLOYEE_ID",
                "EMPLOYEE_PERFORMANCE.BRANCH_ID -> BRANCHES.BRANCH_ID",
            ),
            business_terms=(
                "employee performance",
                "performance comparison",
                "target vs actual",
                "top performer",
                "productivity",
            ),
        ),
        TableDoc(
            name="CLAIMS",
            description=(
                "Insurance/warranty claims raised against products or accounts, "
                "including status and settlement amounts."
            ),
            columns=(
                ColumnDoc("CLAIM_ID", "BIGINT", "Primary key for the claim."),
                ColumnDoc("CUSTOMER_ID", "BIGINT", "Customer who filed the claim."),
                ColumnDoc("BRANCH_ID", "INT", "Branch handling the claim."),
                ColumnDoc("PRODUCT_ID", "INT", "Product the claim relates to."),
                ColumnDoc("CLAIM_AMOUNT", "DECIMAL(14,2)", "Amount claimed."),
                ColumnDoc("SETTLED_AMOUNT", "DECIMAL(14,2)", "Amount finally settled."),
                ColumnDoc("STATUS", "VARCHAR(32)", "Claim status (OPEN/APPROVED/REJECTED/PAID)."),
                ColumnDoc("FILED_ON", "DATE", "Date the claim was filed."),
            ),
            relationships=(
                "CLAIMS.CUSTOMER_ID -> CUSTOMERS.CUSTOMER_ID",
                "CLAIMS.BRANCH_ID -> BRANCHES.BRANCH_ID",
                "CLAIMS.PRODUCT_ID -> PRODUCTS.PRODUCT_ID",
            ),
            business_terms=("claim", "claims", "settlement", "claim ratio", "rejected claims"),
        ),
        TableDoc(
            name="PAYMENTS",
            description=(
                "Customer payments and invoicing, including method and whether "
                "the customer paid directly (self-pay) or via a third party."
            ),
            columns=(
                ColumnDoc("PAYMENT_ID", "BIGINT", "Primary key for the payment."),
                ColumnDoc("INVOICE_ID", "BIGINT", "Invoice the payment settles."),
                ColumnDoc("CUSTOMER_ID", "BIGINT", "Customer making the payment."),
                ColumnDoc("BRANCH_ID", "INT", "Branch that raised the invoice."),
                ColumnDoc("AMOUNT", "DECIMAL(14,2)", "Payment amount."),
                ColumnDoc("PAYMENT_METHOD", "VARCHAR(32)", "CASH/CARD/BANK/INSURANCE etc."),
                ColumnDoc("PAYER_TYPE", "VARCHAR(32)", "SELF_PAY or THIRD_PARTY payer."),
                ColumnDoc("PAID_ON", "DATE", "Date the payment was made."),
            ),
            relationships=(
                "PAYMENTS.CUSTOMER_ID -> CUSTOMERS.CUSTOMER_ID",
                "PAYMENTS.BRANCH_ID -> BRANCHES.BRANCH_ID",
            ),
            business_terms=("payment", "invoice", "self-pay", "payer", "payment method"),
        ),
        TableDoc(
            name="INVENTORY",
            description=(
                "Current stock levels of products per branch, including reorder "
                "thresholds used for stock-out and replenishment analysis."
            ),
            columns=(
                ColumnDoc("INVENTORY_ID", "BIGINT", "Primary key for the stock record."),
                ColumnDoc("BRANCH_ID", "INT", "Branch holding the stock."),
                ColumnDoc("PRODUCT_ID", "INT", "Product being stocked."),
                ColumnDoc("QUANTITY_ON_HAND", "INT", "Units currently in stock."),
                ColumnDoc("REORDER_LEVEL", "INT", "Threshold that triggers reordering."),
                ColumnDoc("LAST_RESTOCKED_ON", "DATE", "Date of the last restock."),
            ),
            relationships=(
                "INVENTORY.BRANCH_ID -> BRANCHES.BRANCH_ID",
                "INVENTORY.PRODUCT_ID -> PRODUCTS.PRODUCT_ID",
            ),
            business_terms=("inventory", "stock", "stock-out", "reorder", "on hand"),
        ),
        TableDoc(
            name="PROCUREMENT",
            description=(
                "Purchase orders raised to suppliers to replenish inventory, "
                "with ordered/received quantities and costs."
            ),
            columns=(
                ColumnDoc("PROCUREMENT_ID", "BIGINT", "Primary key for the purchase order."),
                ColumnDoc("BRANCH_ID", "INT", "Branch that raised the order."),
                ColumnDoc("PRODUCT_ID", "INT", "Product being procured."),
                ColumnDoc("SUPPLIER_NAME", "VARCHAR(128)", "Supplier fulfilling the order."),
                ColumnDoc("QUANTITY_ORDERED", "INT", "Units ordered."),
                ColumnDoc("QUANTITY_RECEIVED", "INT", "Units received."),
                ColumnDoc("UNIT_COST", "DECIMAL(12,2)", "Cost per unit."),
                ColumnDoc("ORDERED_ON", "DATE", "Date the order was placed."),
            ),
            relationships=(
                "PROCUREMENT.BRANCH_ID -> BRANCHES.BRANCH_ID",
                "PROCUREMENT.PRODUCT_ID -> PRODUCTS.PRODUCT_ID",
            ),
            business_terms=("procurement", "purchase order", "supplier", "replenishment"),
        ),
        TableDoc(
            name="PRODUCTS",
            description=(
                "Product master catalog with category, price, and cost; the "
                "product dimension joined by sales, revenue, and inventory."
            ),
            columns=(
                ColumnDoc("PRODUCT_ID", "INT", "Primary key identifying the product."),
                ColumnDoc("PRODUCT_NAME", "VARCHAR(128)", "Product name."),
                ColumnDoc("CATEGORY", "VARCHAR(64)", "Product category/line."),
                ColumnDoc("LIST_PRICE", "DECIMAL(12,2)", "Standard list price."),
                ColumnDoc("UNIT_COST", "DECIMAL(12,2)", "Standard unit cost."),
                ColumnDoc("IS_ACTIVE", "TINYINT", "1 if the product is currently sold."),
            ),
            relationships=(),
            business_terms=("product", "catalog", "category", "product line", "sku"),
        ),
        TableDoc(
            name="CUSTOMERS",
            description=(
                "Customer master record with demographics and the branch that "
                "owns the relationship; the customer dimension for segmentation."
            ),
            columns=(
                ColumnDoc("CUSTOMER_ID", "BIGINT", "Primary key identifying the customer."),
                ColumnDoc("CUSTOMER_NAME", "VARCHAR(128)", "Customer's name."),
                ColumnDoc("SEGMENT", "VARCHAR(64)", "Customer segment (RETAIL/CORPORATE/...)."),
                ColumnDoc("BRANCH_ID", "INT", "Home branch of the customer."),
                ColumnDoc("CITY", "VARCHAR(64)", "Customer's city."),
                ColumnDoc("ONBOARDED_ON", "DATE", "Date the customer was onboarded."),
            ),
            relationships=("CUSTOMERS.BRANCH_ID -> BRANCHES.BRANCH_ID",),
            business_terms=("customer", "client", "segment", "customer base"),
        ),
        TableDoc(
            name="CUSTOMER_ACCOUNTS",
            description=(
                "Financial accounts held by customers, tracking balances and "
                "outstanding dues used in receivables and credit-risk reports."
            ),
            columns=(
                ColumnDoc("ACCOUNT_ID", "BIGINT", "Primary key for the account."),
                ColumnDoc("CUSTOMER_ID", "BIGINT", "Owning customer."),
                ColumnDoc("BRANCH_ID", "INT", "Branch that manages the account."),
                ColumnDoc("ACCOUNT_TYPE", "VARCHAR(32)", "Type of account (CREDIT/PREPAID/...)."),
                ColumnDoc("CURRENT_BALANCE", "DECIMAL(16,2)", "Current account balance."),
                ColumnDoc("OUTSTANDING_DUE", "DECIMAL(16,2)", "Amount overdue on the account."),
                ColumnDoc("OPENED_ON", "DATE", "Date the account was opened."),
            ),
            relationships=(
                "CUSTOMER_ACCOUNTS.CUSTOMER_ID -> CUSTOMERS.CUSTOMER_ID",
                "CUSTOMER_ACCOUNTS.BRANCH_ID -> BRANCHES.BRANCH_ID",
            ),
            business_terms=("account", "balance", "outstanding", "dues", "credit"),
        ),
    ]

    glossary: list[GlossaryDoc] = [
        GlossaryDoc(
            term="collection performance",
            definition=(
                "How effectively a branch converts amounts due into amounts "
                "collected, typically AMOUNT_COLLECTED / AMOUNT_DUE over a period."
            ),
            related_tables=("COLLECTIONS", "BRANCHES"),
        ),
        GlossaryDoc(
            term="underperforming branch",
            definition=(
                "A branch whose revenue, sales, or collection metrics fall below "
                "target or below the peer-branch median for the period."
            ),
            related_tables=("BRANCHES", "REVENUE", "SALES", "COLLECTIONS"),
        ),
        GlossaryDoc(
            term="revenue trend",
            definition=(
                "The month-over-month movement of NET_REVENUE (or GROSS_REVENUE), "
                "usually per branch or product line, to reveal growth or decline."
            ),
            related_tables=("REVENUE", "BRANCHES", "PRODUCTS"),
        ),
        GlossaryDoc(
            term="self-pay",
            definition=(
                "Payments where the customer settles the invoice directly rather "
                "than through insurance or a third party (PAYMENTS.PAYER_TYPE = 'SELF_PAY')."
            ),
            related_tables=("PAYMENTS", "CUSTOMERS"),
        ),
        GlossaryDoc(
            term="employee performance comparison",
            definition=(
                "Ranking employees against each other by PERFORMANCE_SCORE or "
                "SALES_ACTUAL vs SALES_TARGET within a branch or period."
            ),
            related_tables=("EMPLOYEE_PERFORMANCE", "EMPLOYEES", "BRANCHES"),
        ),
        GlossaryDoc(
            term="recovery rate",
            definition=(
                "The share of outstanding dues that has been recovered through "
                "collections, i.e. total AMOUNT_COLLECTED over total AMOUNT_DUE."
            ),
            related_tables=("COLLECTIONS", "CUSTOMER_ACCOUNTS"),
        ),
        GlossaryDoc(
            term="stock-out risk",
            definition=(
                "Products whose QUANTITY_ON_HAND has fallen to or below their "
                "REORDER_LEVEL at a branch, indicating imminent stock-out."
            ),
            related_tables=("INVENTORY", "PRODUCTS", "PROCUREMENT"),
        ),
        GlossaryDoc(
            term="claim ratio",
            definition=(
                "The proportion of sales or accounts that result in a claim, or "
                "settled vs. filed claim amounts, used to gauge product/branch risk."
            ),
            related_tables=("CLAIMS", "SALES", "PRODUCTS"),
        ),
    ]

    return tables, glossary
