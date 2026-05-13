import re
from typing import Optional, List

def extract_field(text: str, field_name: str) -> Optional[str]:
    """Safely extracts field values, handling nested brackets and quotes."""
    pattern = re.compile(rf'\b{field_name}\s*=\s*', re.IGNORECASE)
    match = pattern.search(text)
    if not match:
        return None
    
    value_start = text[match.end():].lstrip()
    
    if value_start.startswith('{'):
        brace_level = 0
        extracted = []
        for char in value_start:
            if char == '{':
                brace_level += 1
            elif char == '}':
                brace_level -= 1
            extracted.append(char)
            if brace_level == 0:
                break
        return "".join(extracted)[1:-1]
        
    elif value_start.startswith('"'):
        extracted = ['"']
        for char in value_start[1:]:
            extracted.append(char)
            if char == '"':
                break
        return "".join(extracted)[1:-1]
        
    else:
        # Handle raw strings like macros or numbers
        return value_start.split(',')[0].strip()

def get_bibtex_blocks(content: str) -> List[List[str]]:
    """Splits BibTeX file content into logical blocks while preserving spacing."""
    lines = content.split('\n')
    blocks = []
    current_block = []
    for line in lines:
        if re.match(r'^\s*@[a-zA-Z]+\{', line):
            if current_block:
                blocks.append(current_block)
            current_block = [line]
        else:
            current_block.append(line)
            
    if current_block:
        blocks.append(current_block)
    return blocks
