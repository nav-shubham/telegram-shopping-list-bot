from src.parser.parser import parse_item_line, parse_multi_line

def test_parse_item_line_standard():
    # Test cases with quantity and unit
    res1 = parse_item_line("Tomato 2kg")
    assert res1 == {"name": "Tomato", "quantity": 2.0, "unit": "kg"}
    
    res2 = parse_item_line("Rice 10kg")
    assert res2 == {"name": "Rice", "quantity": 10.0, "unit": "kg"}

def test_parse_item_line_no_unit():
    # Test cases with quantity but no unit
    res1 = parse_item_line("Milk 2")
    assert res1 == {"name": "Milk", "quantity": 2.0, "unit": None}
    
    res2 = parse_item_line("Soap 3")
    assert res2 == {"name": "Soap", "quantity": 3.0, "unit": None}

def test_parse_item_line_with_decimals():
    # Test decimal values
    res1 = parse_item_line("Oil 1.5L")
    assert res1 == {"name": "Oil", "quantity": 1.5, "unit": "L"}

def test_parse_item_line_no_quantity():
    # Test cases with no quantity (default to 1.0)
    res = parse_item_line("Bread")
    assert res == {"name": "Bread", "quantity": 1.0, "unit": None}

def test_parse_item_line_empty():
    assert parse_item_line("") is None
    assert parse_item_line("   ") is None

def test_parse_multi_line():
    input_text = """Tomato 2kg
Potato 5kg
Onion 3kg
Rice 10kg
Milk 2
Bread
Soap 3"""
    
    expected = [
        {"name": "Tomato", "quantity": 2.0, "unit": "kg"},
        {"name": "Potato", "quantity": 5.0, "unit": "kg"},
        {"name": "Onion", "quantity": 3.0, "unit": "kg"},
        {"name": "Rice", "quantity": 10.0, "unit": "kg"},
        {"name": "Milk", "quantity": 2.0, "unit": None},
        {"name": "Bread", "quantity": 1.0, "unit": None},
        {"name": "Soap", "quantity": 3.0, "unit": None},
    ]
    
    assert parse_multi_line(input_text) == expected
