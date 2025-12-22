"""Category Agent - handles custom category management."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.database import crud


class CategoryAgent:
    """Agent for managing expense categories."""

    async def list_categories(self, db: AsyncSession, user) -> str:
        """List all categories for a user.

        Args:
            db: Database session
            user: User model instance

        Returns:
            Formatted list of categories
        """
        categories = await crud.get_user_categories(db, user.id)

        if not categories:
            return "No categories found. This shouldn't happen!"

        response = ["*Your Categories*\n"]

        # Separate default and custom
        default_cats = [c for c in categories if c.is_default]
        custom_cats = [c for c in categories if not c.is_default]

        if default_cats:
            response.append("*Default:*")
            for cat in default_cats:
                response.append(f"- {cat.name}")

        if custom_cats:
            response.append("\n*Custom:*")
            for cat in custom_cats:
                response.append(f"- {cat.name}")

        return "\n".join(response)

    async def add_category(
        self,
        db: AsyncSession,
        user,
        name: str,
        icon: str | None = None,
    ) -> str:
        """Add a new custom category.

        Args:
            db: Database session
            user: User model instance
            name: Category name
            icon: Optional emoji icon

        Returns:
            Response message
        """
        # Check if category already exists
        existing = await crud.get_category_by_name(db, user.id, name)
        if existing:
            return f"Category '{name}' already exists!"

        category = await crud.create_category(
            db=db,
            user_id=user.id,
            name=name.title(),
            icon=icon,
        )

        return f"Added category: {category.name}"

    async def delete_category(self, db: AsyncSession, user, name: str) -> str:
        """Delete a custom category.

        Args:
            db: Database session
            user: User model instance
            name: Category name

        Returns:
            Response message
        """
        category = await crud.get_category_by_name(db, user.id, name)

        if not category:
            return f"Category '{name}' not found."

        if category.is_default:
            return f"Cannot delete default category '{name}'."

        await db.delete(category)
        return f"Deleted category: {category.name}"

    def extract_category_name(self, text: str) -> str | None:
        """Extract category name from text like 'add category Subscriptions'.

        Args:
            text: Input text

        Returns:
            Extracted category name or None
        """
        import re

        # Patterns to extract category name
        patterns = [
            r"add\s+category\s+(.+)",
            r"new\s+category\s+(.+)",
            r"create\s+category\s+(.+)",
        ]

        text_lower = text.lower().strip()
        for pattern in patterns:
            match = re.search(pattern, text_lower)
            if match:
                name = match.group(1).strip()
                # Capitalize properly
                return name.title()

        return None
