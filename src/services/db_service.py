from datetime import datetime
from typing import Dict, List, Optional, Any
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from src.database.models import User, ListType, ShoppingList, Item, ShoppingHistory, ShoppingHistoryItem

class DuplicateListNameError(Exception):
    """Exception raised when a user tries to create or rename a list to an existing name."""
    pass

class DBService:
    def __init__(self, db: Session):
        self.db = db

    def get_or_create_user(self, telegram_id: int) -> User:
        """Retrieves user by Telegram ID or creates a new user if not found."""
        user = self.db.query(User).filter(User.telegram_id == telegram_id).first()
        if not user:
            user = User(telegram_id=telegram_id)
            self.db.add(user)
            self.db.commit()
            self.db.refresh(user)
        return user

    def get_list_types(self) -> List[ListType]:
        """Retrieves all predefined list categories."""
        return self.db.query(ListType).all()

    def get_list_type(self, type_id: int) -> Optional[ListType]:
        """Retrieves a specific list category by ID."""
        return self.db.query(ListType).filter(ListType.id == type_id).first()

    def create_shopping_list(self, user_id: int, type_id: int, name: str) -> ShoppingList:
        """Creates a new shopping list. Names must be unique per user."""
        existing = self.db.query(ShoppingList).filter(
            ShoppingList.user_id == user_id,
            ShoppingList.name == name
        ).first()
        if existing:
            raise DuplicateListNameError(f"A list named '{name}' already exists.")
            
        shopping_list = ShoppingList(user_id=user_id, type_id=type_id, name=name)
        self.db.add(shopping_list)
        try:
            self.db.commit()
            self.db.refresh(shopping_list)
            return shopping_list
        except IntegrityError:
            self.db.rollback()
            raise DuplicateListNameError(f"A list named '{name}' already exists.")

    def rename_shopping_list(self, list_id: int, new_name: str) -> Optional[ShoppingList]:
        """Renames an existing shopping list, enforcing name uniqueness per user."""
        shopping_list = self.db.query(ShoppingList).filter(ShoppingList.id == list_id).first()
        if not shopping_list:
            return None
            
        # Check name uniqueness among this user's other lists
        existing = self.db.query(ShoppingList).filter(
            ShoppingList.user_id == shopping_list.user_id,
            ShoppingList.name == new_name,
            ShoppingList.id != list_id
        ).first()
        if existing:
            raise DuplicateListNameError(f"A list named '{new_name}' already exists.")
            
        shopping_list.name = new_name
        try:
            self.db.commit()
            self.db.refresh(shopping_list)
            return shopping_list
        except IntegrityError:
            self.db.rollback()
            raise DuplicateListNameError(f"A list named '{new_name}' already exists.")

    def delete_shopping_list(self, list_id: int) -> bool:
        """Deletes a shopping list and all its items (handled by cascade)."""
        shopping_list = self.db.query(ShoppingList).filter(ShoppingList.id == list_id).first()
        if shopping_list:
            self.db.delete(shopping_list)
            self.db.commit()
            return True
        return False

    def get_shopping_list(self, list_id: int) -> Optional[ShoppingList]:
        """Gets a shopping list by ID."""
        return self.db.query(ShoppingList).filter(ShoppingList.id == list_id).first()

    def get_user_lists(self, user_id: int) -> List[ShoppingList]:
        """Gets all shopping lists belonging to a user."""
        return self.db.query(ShoppingList).filter(ShoppingList.user_id == user_id).all()

    def get_user_lists_grouped_by_type(self, user_id: int) -> Dict[int, Dict[str, Any]]:
        """Returns lists grouped by category ID, including empty categories."""
        lists = self.get_user_lists(user_id)
        types = self.get_list_types()
        
        grouped = {t.id: {"type": t, "lists": []} for t in types}
        for lst in lists:
            if lst.type_id in grouped:
                grouped[lst.type_id]["lists"].append(lst)
        return grouped

    def add_items_to_list(self, list_id: int, parsed_items: List[Dict[str, Any]]) -> List[Item]:
        """Bulk adds items (parsed with name, quantity, unit) to a list."""
        items = []
        for pi in parsed_items:
            item = Item(
                list_id=list_id,
                name=pi["name"],
                quantity=pi["quantity"],
                unit=pi["unit"]
            )
            self.db.add(item)
            items.append(item)
        self.db.commit()
        return items

    def get_items_in_list(self, list_id: int) -> List[Item]:
        """Returns items in list ordered by completion status (incomplete first) and creation time."""
        return self.db.query(Item).filter(Item.list_id == list_id).order_by(
            Item.is_completed.asc(),
            Item.created_at.asc()
        ).all()

    def get_item(self, item_id: int) -> Optional[Item]:
        """Gets an item by ID."""
        return self.db.query(Item).filter(Item.id == item_id).first()

    def toggle_item_completed(self, item_id: int) -> Optional[Item]:
        """Toggles the completion status of an item."""
        item = self.get_item(item_id)
        if item:
            item.is_completed = not item.is_completed
            self.db.commit()
            self.db.refresh(item)
        return item

    def update_item(self, item_id: int, name: Optional[str] = None, quantity: Optional[float] = None, unit: Optional[str] = None) -> Optional[Item]:
        """Updates item fields. To clear a unit, pass an empty string."""
        item = self.get_item(item_id)
        if item:
            if name is not None:
                item.name = name.strip()
            if quantity is not None:
                item.quantity = quantity
            if unit is not None:
                item.unit = unit.strip() if unit.strip() else None
            self.db.commit()
            self.db.refresh(item)
        return item

    def delete_item(self, item_id: int) -> bool:
        """Deletes an item from a list."""
        item = self.get_item(item_id)
        if item:
            self.db.delete(item)
            self.db.commit()
            return True
        return False

    def complete_shopping_session(self, list_id: int, reset_items: bool = True) -> Optional[ShoppingHistory]:
        """
        Finalizes shopping session:
        1. Takes a static snapshot of the current state of list items.
        2. Saves history to shopping_histories and shopping_history_items.
        3. If reset_items is True, resets all list items to is_completed = False.
        """
        shopping_list = self.get_shopping_list(list_id)
        if not shopping_list:
            return None
            
        items = self.db.query(Item).filter(Item.list_id == list_id).all()
        if not items:
            return None
            
        # Create history record
        history = ShoppingHistory(
            user_id=shopping_list.user_id,
            list_name=shopping_list.name,
            list_type=shopping_list.list_type.name,
            list_type_emoji=shopping_list.list_type.emoji,
            total_items=len(items)
        )
        self.db.add(history)
        self.db.flush()  # Populates history.id
        
        # Populate history items and reset original items if requested
        for item in items:
            hist_item = ShoppingHistoryItem(
                history_id=history.id,
                name=item.name,
                quantity=item.quantity,
                unit=item.unit
            )
            self.db.add(hist_item)
            
            # Reset original item for reuse
            if reset_items:
                item.is_completed = False
            
        self.db.commit()
        self.db.refresh(history)
        return history

    def get_shopping_history(self, user_id: int) -> List[ShoppingHistory]:
        """Gets all history records for a user, sorted newest first."""
        return self.db.query(ShoppingHistory).filter(ShoppingHistory.user_id == user_id).order_by(
            ShoppingHistory.completion_date.desc()
        ).all()

    def get_history_details(self, history_id: int) -> Optional[ShoppingHistory]:
        """Gets details of a completed shopping session."""
        return self.db.query(ShoppingHistory).filter(ShoppingHistory.id == history_id).first()

    def delete_history_record(self, history_id: int) -> bool:
        """Deletes a history record and its items (handled by cascade)."""
        history = self.db.query(ShoppingHistory).filter(ShoppingHistory.id == history_id).first()
        if history:
            self.db.delete(history)
            self.db.commit()
            return True
        return False

    def clear_all_items_in_list(self, list_id: int) -> int:
        """Deletes all items in a shopping list. Returns count of deleted items."""
        deleted_count = self.db.query(Item).filter(Item.list_id == list_id).delete()
        self.db.commit()
        return deleted_count

    def clear_completed_items_in_list(self, list_id: int) -> int:
        """Deletes only completed (checked) items in a shopping list. Returns count of deleted items."""
        deleted_count = self.db.query(Item).filter(
            Item.list_id == list_id,
            Item.is_completed == True
        ).delete()
        self.db.commit()
        return deleted_count

    def get_list_count_by_type(self, user_id: int) -> Dict[int, int]:
        """Returns a mapping of list category ID to list count for a specific user."""
        from sqlalchemy import func
        counts = self.db.query(
            ShoppingList.type_id,
            func.count(ShoppingList.id)
        ).filter(ShoppingList.user_id == user_id).group_by(ShoppingList.type_id).all()
        
        return {type_id: count for type_id, count in counts}
