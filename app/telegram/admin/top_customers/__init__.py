"""Top customers stats module package."""

from app.telegram.admin.top_customers.service import build_top_customers_message, top_customers_rich_blocks

__all__ = ["build_top_customers_message", "top_customers_rich_blocks"]
