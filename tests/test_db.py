import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.database.models import Base
from src.services.db_service import DBService, DuplicateListNameError

# Setup in-memory database for testing
@pytest.fixture(name="db_session")
def fixture_db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    # Seed list types for test run
    from src.database.models import ListType
    predefined_types = [
        ("Groceries", "🛒"),
        ("Vegetables", "🥬"),
        ("Medical", "💊"),
    ]
    for name, emoji in predefined_types:
        session.add(ListType(name=name, emoji=emoji))
    session.commit()
    
    yield session
    session.close()

def test_user_creation(db_session):
    service = DBService(db_session)
    user = service.get_or_create_user(12345)
    assert user.telegram_id == 12345
    
    # Retrieve existing
    user_existing = service.get_or_create_user(12345)
    assert user_existing.telegram_id == 12345

def test_list_creation_and_duplicates(db_session):
    service = DBService(db_session)
    service.get_or_create_user(12345)
    
    # Successful creation
    lst1 = service.create_shopping_list(user_id=12345, type_id=1, name="Weekly Groceries")
    assert lst1.name == "Weekly Groceries"
    assert lst1.type_id == 1
    
    # Try duplicate name for same user
    with pytest.raises(DuplicateListNameError):
        service.create_shopping_list(user_id=12345, type_id=2, name="Weekly Groceries")
        
    # Successful creation for a different user
    service.get_or_create_user(67890)
    lst2 = service.create_shopping_list(user_id=67890, type_id=1, name="Weekly Groceries")
    assert lst2.name == "Weekly Groceries"

def test_items_crud(db_session):
    service = DBService(db_session)
    service.get_or_create_user(123)
    lst = service.create_shopping_list(user_id=123, type_id=1, name="My List")
    
    # Bulk add
    parsed = [
        {"name": "Apple", "quantity": 5.0, "unit": "pcs"},
        {"name": "Milk", "quantity": 1.0, "unit": "L"}
    ]
    items = service.add_items_to_list(lst.id, parsed)
    assert len(items) == 2
    assert items[0].name == "Apple"
    assert items[0].quantity == 5.0
    
    # Get items sorted
    items_in_list = service.get_items_in_list(lst.id)
    assert len(items_in_list) == 2
    
    # Toggle complete
    service.toggle_item_completed(items_in_list[0].id)
    # Check that sorting puts incomplete first
    items_sorted = service.get_items_in_list(lst.id)
    assert items_sorted[0].name == "Milk"  # Incomplete
    assert items_sorted[1].name == "Apple"  # Completed
    
    # Update item
    service.update_item(items_in_list[0].id, name="Green Apple", quantity=6.0, unit="kg")
    updated = service.get_item(items_in_list[0].id)
    assert updated.name == "Green Apple"
    assert updated.quantity == 6.0
    assert updated.unit == "kg"
    
    # Delete item
    service.delete_item(items_in_list[1].id)
    assert len(service.get_items_in_list(lst.id)) == 1

def test_shopping_completion_and_history(db_session):
    service = DBService(db_session)
    service.get_or_create_user(123)
    lst = service.create_shopping_list(user_id=123, type_id=1, name="My List")
    
    parsed = [
        {"name": "Bread", "quantity": 1.0, "unit": None},
        {"name": "Eggs", "quantity": 12.0, "unit": "pcs"}
    ]
    service.add_items_to_list(lst.id, parsed)
    
    # Check one item complete
    items = service.get_items_in_list(lst.id)
    service.toggle_item_completed(items[0].id) # Bread is completed
    
    # Complete shopping
    history = service.complete_shopping_session(lst.id)
    assert history is not None
    assert history.list_name == "My List"
    assert history.list_type == "Groceries"
    assert history.total_items == 2
    
    # Check original items are reset
    reset_items = service.get_items_in_list(lst.id)
    for item in reset_items:
        assert not item.is_completed
        
    # Check history entries
    user_history = service.get_shopping_history(123)
    assert len(user_history) == 1
    assert user_history[0].id == history.id
    
    details = service.get_history_details(history.id)
    assert len(details.items) == 2
    assert details.items[0].name == "Bread"
    
    # Delete history record
    service.delete_history_record(history.id)
    assert len(service.get_shopping_history(123)) == 0

def test_shopping_completion_no_reset(db_session):
    service = DBService(db_session)
    service.get_or_create_user(123)
    lst = service.create_shopping_list(user_id=123, type_id=1, name="My List")
    
    parsed = [{"name": "Bread", "quantity": 1.0, "unit": None}]
    service.add_items_to_list(lst.id, parsed)
    
    items = service.get_items_in_list(lst.id)
    service.toggle_item_completed(items[0].id)
    
    # Complete shopping without reset
    history = service.complete_shopping_session(lst.id, reset_items=False)
    assert history is not None
    
    # Check item is still completed in original list
    original_items = service.get_items_in_list(lst.id)
    assert original_items[0].is_completed == True

def test_list_counts_and_clear_items(db_session):
    service = DBService(db_session)
    service.get_or_create_user(123)
    
    lst1 = service.create_shopping_list(user_id=123, type_id=1, name="List 1")
    lst2 = service.create_shopping_list(user_id=123, type_id=1, name="List 2")
    service.create_shopping_list(user_id=123, type_id=2, name="List 3")
    
    # Verify counts
    counts = service.get_list_count_by_type(123)
    assert counts.get(1) == 2
    assert counts.get(2) == 1
    
    # Add items to clear
    parsed = [
        {"name": "Bread", "quantity": 1.0, "unit": None},
        {"name": "Eggs", "quantity": 12.0, "unit": "pcs"}
    ]
    service.add_items_to_list(lst1.id, parsed)
    
    items = service.get_items_in_list(lst1.id)
    service.toggle_item_completed(items[0].id) # Bread completed
    
    # Clear completed
    service.clear_completed_items_in_list(lst1.id)
    remaining = service.get_items_in_list(lst1.id)
    assert len(remaining) == 1
    assert remaining[0].name == "Eggs"
    
    # Clear all
    service.clear_all_items_in_list(lst1.id)
    assert len(service.get_items_in_list(lst1.id)) == 0

def test_custom_presets(db_session):
    service = DBService(db_session)
    service.get_or_create_user(123)
    
    from src.database.models import PresetItem
    default_preset = PresetItem(user_id=None, type_id=1, name="Default Bread", quantity=1.0)
    db_session.add(default_preset)
    db_session.commit()
    
    # Retrieve presets (user 123, type 1)
    presets = service.get_presets_for_category(123, type_id=1)
    assert len(presets) == 1
    assert presets[0].name == "Default Bread"
    
    # Create custom preset
    custom = service.create_custom_preset(user_id=123, type_id=1, name="Custom Butter", quantity=2.0, unit="pcs")
    assert custom.name == "Custom Butter"
    assert custom.quantity == 2.0
    assert custom.unit == "pcs"
    
    # Retrieve presets again (should have default + custom)
    presets_new = service.get_presets_for_category(123, type_id=1)
    assert len(presets_new) == 2
    assert presets_new[0].name == "Default Bread"
    assert presets_new[1].name == "Custom Butter"
    
    # Verify another user does NOT see user 123's custom preset
    presets_other = service.get_presets_for_category(456, type_id=1)
    assert len(presets_other) == 1
    assert presets_other[0].name == "Default Bread"

def test_custom_preset_update_and_delete(db_session):
    service = DBService(db_session)
    service.get_or_create_user(123)
    
    # Create
    custom = service.create_custom_preset(user_id=123, type_id=1, name="Custom Butter", quantity=2.0, unit="pcs")
    
    # Update
    updated = service.update_preset_item(custom.id, name="Special Butter", quantity=3.5, unit="g")
    assert updated is not None
    assert updated.name == "Special Butter"
    assert updated.quantity == 3.5
    assert updated.unit == "g"
    
    # Verify retrieval
    retrieved = service.get_preset_item(custom.id)
    assert retrieved.name == "Special Butter"
    
    # Delete
    success = service.delete_preset_item(custom.id)
    assert success is True
    
    # Verify deleted
    assert service.get_preset_item(custom.id) is None


