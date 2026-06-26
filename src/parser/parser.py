import re
from typing import Dict, List, Optional, Any

# Regex pattern to match:
# Group 1: Item name (any characters before the space-separated number)
# Group 2: Quantity (integer or decimal number)
# Group 3: Optional unit (letters only, e.g. kg, g, L, ml, pcs, etc.)
ITEM_PATTERN = re.compile(r"^(.*?)\s+(\d+(?:\.\d+)?)\s*([a-zA-Z]+)?$")

def parse_item_line(line: str) -> Optional[Dict[str, Any]]:
    """
    Parses a single line containing an item name and optionally a quantity and unit.
    
    Returns a dictionary with keys:
        - name (str): The name of the item.
        - quantity (float): The quantity of the item (defaults to 1.0 if not found).
        - unit (Optional[str]): The unit of measurement (None if not found).
    
    If the line is empty or whitespace-only, returns None.
    """
    line = line.strip()
    if not line:
        return None
        
    match = ITEM_PATTERN.match(line)
    if match:
        name = match.group(1).strip()
        quantity_str = match.group(2)
        unit = match.group(3)
        
        # Guard against matching digits only if name is completely empty
        # e.g., "5kg" without item name should treat "5kg" as name
        if not name:
            return {
                "name": line,
                "quantity": 1.0,
                "unit": None
            }
            
        try:
            quantity = float(quantity_str)
            # Normalize .0 floats to ints if visually preferred, but database Float is standard.
        except ValueError:
            quantity = 1.0
            
        return {
            "name": name,
            "quantity": quantity,
            "unit": unit if unit else None
        }
    else:
        # Default fallback if pattern doesn't match: Whole line is name, quantity is 1.0
        return {
            "name": line,
            "quantity": 1.0,
            "unit": None
        }

def parse_multi_line(text: str) -> List[Dict[str, Any]]:
    """
    Parses multiple lines of text into a list of parsed items.
    Empty lines are ignored.
    """
    results = []
    if not text:
        return results
        
    for line in text.splitlines():
        parsed = parse_item_line(line)
        if parsed:
            results.append(parsed)
            
    return results
