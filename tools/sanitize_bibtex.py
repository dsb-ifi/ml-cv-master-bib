import argparse
import re
import os
import logging
import subprocess
from typing import Dict, List, Set

logger = logging.getLogger(__name__)
from bibtex_utils import get_bibtex_blocks

LATEX_MACROS = {
  'á': "\\'a", 'é': "\\'e", 'í': "\\'i", 'ó': "\\'o", 'ú': "\\'u",
  'Á': "\\'A", 'É': "\\'E", 'Í': "\\'I", 'Ó': "\\'O", 'Ú': "\\'U",
  'ñ': "\\~n", 'Ñ': "\\~N",
  'ä': '\\"a', 'ë': '\\"e', 'ï': '\\"i', 'ö': '\\"o', 'ü': '\\"u',
  'Ä': '\\"A', 'Ë': '\\"E', 'Ï': '\\"I', 'Ö': '\\"O', 'Ü': '\\"U',
  'ç': '\\c{c}', 'Ç': '\\c{C}',
  'ß': '\\ss',
  'ø': '\\o', 'Ø': '\\O',
  'å': '\\aa', 'Å': '\\AA',
  'æ': '\\ae', 'Æ': '\\AE',
  'œ': '\\oe', 'Œ': '\\OE',
  '—': '---', '–': '--', '’': "'", '‘': "`", '“': "``", '”': "''",
  '…': '\\dots'
}

MONTH_MAP = {
  'jan': 'jan', 'january': 'jan',
  'feb': 'feb', 'february': 'feb',
  'mar': 'mar', 'march': 'mar',
  'apr': 'apr', 'april': 'apr',
  'may': 'may',
  'jun': 'jun', 'june': 'jun',
  'jul': 'jul', 'july': 'jul',
  'aug': 'aug', 'august': 'aug',
  'sep': 'sep', 'september': 'sep',
  'oct': 'oct', 'october': 'oct',
  'nov': 'nov', 'november': 'nov',
  'dec': 'dec', 'december': 'dec'
}

def find_journal_list_file(search_dir: str = "") -> str:
  filenames = ['journal-list/abrv.bib', 'journal-list/full.bib']

  # If a search directory is given, look there first
  if search_dir:
    for filename in filenames:
      path = os.path.join(search_dir, filename)
      if os.path.exists(path):
        return path
    logger.warning(f"No journal-list files found under '{search_dir}'.")

  # Fall back to kpsewhich
  for filename in filenames:
    try:
      result = subprocess.run(['kpsewhich', filename], stdout=subprocess.PIPE, text=True, check=True)
      path = result.stdout.strip()
      if path and os.path.exists(path):
        return path
    except (subprocess.CalledProcessError, FileNotFoundError):
      continue
  return ""

def load_macros(search_dir: str = "") -> Set[str]:
  macros = set()
  bib_file_path = find_journal_list_file(search_dir)
    
  if not bib_file_path:
    logger.warning("Could not find 'journal-list/abrv.bib' or 'journal-list/full.bib' using kpsewhich. Macro verification skipped.")
    return macros

  logger.info(f"Loading bibstrings from: {bib_file_path}")
  try:
    with open(bib_file_path, 'r', encoding='utf-8') as bib_file:
      content = bib_file.read()
      matches = re.finditer(r'@string\s*[\{\(]\s*([a-zA-Z0-9_\-]+)\s*=', content, flags=re.IGNORECASE)
      for m in matches:
        macros.add(m.group(1).lower())
  except Exception as e:
    logger.debug(f"Failed to read {bib_file_path}: {e}")

  return macros

VENUE_FIELDS = ('journal', 'journaltitle', 'booktitle', 'series')


def normalize_venue(name: str, strip_prefixes: bool = True) -> str:
  """Reduces a venue name to a comparable form: no braces, accents, acronyms in parentheses and, optionally, no leading boilerplate."""
  name = re.sub(r'\\[a-zA-Z]+\s*|\\.', '', name)
  name = re.sub(r'[{}]', '', name).lower()
  name = re.sub(r'\([^)]*\)', ' ', name)
  name = re.sub(r'[^a-z0-9]+', ' ', name).strip()

  prefix = re.compile(r'^(proceedings of|proc of|the|ieee cvf|ieee|cvf|acm)\s+')
  while strip_prefixes and prefix.match(name):
    name = prefix.sub('', name, count=1)
  return name


def load_venue_names(search_dir: str = "") -> Dict[str, Set[str]]:
  """Maps each normalized full and abbreviated journal-list name to the bibstrings that define it.

  Keys are stored twice: as is (`exact:`) and without leading publisher boilerplate (`loose:`).
  """
  names: Dict[str, Set[str]] = {}
  found = find_journal_list_file(search_dir)
  if not found:
    return names

  for filename in ('full.bib', 'abrv.bib'):
    path = os.path.join(os.path.dirname(found), filename)
    if not os.path.exists(path):
      continue
    with open(path, 'r', encoding='utf-8') as bib_file:
      for m in re.finditer(r'@string\s*[\{\(]\s*([a-zA-Z0-9_\-]+)\s*=\s*"(.*)"\s*[\}\)]', bib_file.read(), flags=re.IGNORECASE):
        names.setdefault('exact:' + normalize_venue(m.group(2), strip_prefixes=False), set()).add(m.group(1))
        names.setdefault('loose:' + normalize_venue(m.group(2)), set()).add(m.group(1))
  return names


def read_value(text: str, start: int) -> List[str]:
  """Splits the field value starting at `start` into its `#`-joined parts, keeping delimiters."""
  parts, i = [], start
  while i < len(text):
    while i < len(text) and text[i] in ' \t\r\n':
      i += 1
    if i >= len(text):
      break

    if text[i] in '{"':
      close = '}' if text[i] == '{' else '"'
      depth, j = 0, i
      while j < len(text):
        char = text[j]
        if char == '{':
          depth += 1
        elif char == '}':
          depth -= 1
        if (close == '}' and depth == 0) or (close == '"' and char == '"' and j > i and depth == 0):
          break
        j += 1
      parts.append(text[i:j + 1])
      i = j + 1
    else:
      m = re.match(r'[^\s,#}]+', text[i:])
      if not m:
        break
      parts.append(m.group(0))
      i += m.end()

    while i < len(text) and text[i] in ' \t\r\n':
      i += 1
    if i < len(text) and text[i] == '#':
      i += 1
      continue
    break
  return parts


def check_venues(block_text: str, key: str, valid_macros: Set[str], venue_names: Dict[str, Set[str]]) -> None:
  """Reports unknown macros and literal venue names that should be bibstrings."""
  pattern = r'(?<![\w\-])(' + '|'.join(VENUE_FIELDS) + r')\s*=\s*'
  for match in re.finditer(pattern, block_text, flags=re.IGNORECASE):
    field_name = match.group(1)
    parts = read_value(block_text, match.end())
    literals = [p for p in parts if p[0] in '{"']
    macros = [p for p in parts if p[0] not in '{"' and not p.isdigit()]

    for macro in macros:
      if macro.lower() not in valid_macros:
        logger.error(f"Entry '{key}': Unknown bibstring macro '{macro}' in field '{field_name}'.")

    if macros or not literals:
      continue

    value = ' '.join(re.sub(r'\s+', ' ', p) for p in literals)
    matches = venue_names.get('exact:' + normalize_venue(value, strip_prefixes=False)) or venue_names.get('loose:' + normalize_venue(value))
    if matches:
      logger.error(f"Entry '{key}': Literal venue {value} in field '{field_name}' matches bibstring {', '.join(sorted(matches))}; use the bibstring.")
    elif field_name.lower() != 'series':
      logger.warning(f"Entry '{key}': Literal venue {value} in field '{field_name}' has no bibstring; consider adding one to journal-list.")


def sanitize_block(block_text: str, valid_macros: Set[str], key: str, venue_names: Dict[str, Set[str]]) -> str:
  # 1. Non-standard characters -> LaTeX macros
  for char, macro in LATEX_MACROS.items():
    if char in block_text:
      block_text = block_text.replace(char, macro)
      
  # 2. Remove double curly braces over entire fields
  def remove_double_braces(match):
    inner = match.group(2)
    # Abort if the inner content looks like it contains another field definition entirely
    if re.search(r'^\s*[a-zA-Z0-9_\-]+\s*=', inner, flags=re.MULTILINE):
      return match.group(0)

    # Keep single-word values such as `{{DINOv3}}`, where the inner braces protect one word
    if not re.search(r'\s', inner):
      return match.group(0)

    # Abort if braces are unbalanced or depth drops below 0.
    # This preserves outer braces for `{{BEGIN} words {END}}` (depth drops < 0)
    # but successfully simplifies `{{{BEGIN} words {END}}}` (depth stays >= 0).
    depth = 0
    escaped = False
    for char in inner:
      if escaped:
        escaped = False
        continue
      if char == '\\':
        escaped = True
      elif char == '{':
        depth += 1
      elif char == '}':
        depth -= 1
        if depth < 0:
          return match.group(0)
    if depth != 0:
      return match.group(0)

    return f"{match.group(1)}{{{inner}}}{match.group(3)}"
    
  block_text = re.sub(r'^( *[a-zA-Z0-9_\-]+\s*=\s*)\{\{([\s\S]*?)\}\}(,?\s*)$', remove_double_braces, block_text, flags=re.MULTILINE)
  
  # 3. Fix months
  def fix_month(match):
    val = match.group(2).strip('{"} \t').lower()
    if val in MONTH_MAP:
      return f"{match.group(1)}{MONTH_MAP[val]}{match.group(3)}"
    return match.group(0)
    
  block_text = re.sub(r'^( *month\s*=\s*)(.+?)(,?\s*)$', fix_month, block_text, flags=re.MULTILINE | re.IGNORECASE)
  
  # 4. Fix page ranges
  def fix_pages(match):
    val = match.group(2)
    val = re.sub(r'(?<=\d)\s*-+\s*(?=\d)', '--', val)
    return f"{match.group(1)}{val}{match.group(3)}"
    
  block_text = re.sub(r'^( *pages\s*=\s*)(.+?)(,?\s*)$', fix_pages, block_text, flags=re.MULTILINE | re.IGNORECASE)
  
  # 5. Verify venue macros and literal venue names
  if valid_macros:
    check_venues(block_text, key, valid_macros, venue_names)

  return block_text

def sanitize_bibtex(input_file: str, output_file: str, journal_dir: str = "") -> None:
  if not os.path.exists(input_file):
    raise FileNotFoundError(f"Input file '{input_file}' not found.")
    
  valid_macros = load_macros(journal_dir)
  venue_names = load_venue_names(journal_dir)

  with open(input_file, 'r', encoding='utf-8') as f:
    content = f.read()

  blocks = get_bibtex_blocks(content)
  final_lines = []
  
  sanitized_count = 0

  for block in blocks:
    first_line = block[0] if block else ""
    if not re.match(r'^\s*@[a-zA-Z]+\{', first_line):
      final_lines.extend(block)
      continue
      
    block_text = "\n".join(block)
    match = re.match(r'^\s*@([a-zA-Z]+)\{([^,]*)', block_text)
    
    if not match:
      final_lines.extend(block)
      continue
      
    etype = match.group(1).lower()
    key = match.group(2).strip()
    
    if etype in ['comment', 'string', 'preamble']:
      final_lines.extend(block)
      continue
      
    new_block_text = sanitize_block(block_text, valid_macros, key, venue_names)
    if new_block_text != block_text:
      logger.info(f"Sanitized formatting for entry: '{key}'")
      sanitized_count += 1
      
    final_lines.extend(new_block_text.split('\n'))

  logger.info(f"Sanitization complete. Updated {sanitized_count} entries.")

  with open(output_file, 'w', encoding='utf-8') as f:
    f.write('\n'.join(final_lines))

def main() -> None:
  parser = argparse.ArgumentParser(description="Sanitize a BibTeX file and verify macros.")
  
  group = parser.add_mutually_exclusive_group(required=True)
  group.add_argument("-i", "--input", help="Path to the input BibTeX file")
  group.add_argument("-r", "--replace", help="Path to the BibTeX file to process and replace in-place")
  
  parser.add_argument("-o", "--output", help="Path to the output BibTeX file")
  parser.add_argument("-j", "--journal-dir", default="", help="Base directory to search for journal-list/*.bib files")
  parser.add_argument("-v", "--verbose", action="count", default=0, help="Increase output verbosity (-v for INFO, -vv for DEBUG)")
  
  args = parser.parse_args()
  
  levels = [logging.WARNING, logging.INFO, logging.DEBUG]
  logging_level = levels[min(args.verbose, len(levels) - 1)]
  logging.basicConfig(level=logging_level, format="%(levelname)s: %(message)s")

  if args.input and not args.output:
    parser.error("The -i/--input option requires -o/--output.")
  if args.replace and args.output:
    parser.error("The -r/--replace option cannot be used with -o/--output.")
    
  in_file = args.replace if args.replace else args.input
  out_file = args.replace if args.replace else args.output
  
  sanitize_bibtex(in_file, out_file, journal_dir=args.journal_dir)

if __name__ == "__main__":
  main()
