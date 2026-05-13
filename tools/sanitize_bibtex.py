import argparse
import re
import os
import logging
from typing import Set

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

def load_macros(texmf_dir: str) -> Set[str]:
  macros = set()
  target_dir = os.path.join(texmf_dir, 'bibtex', 'bib', 'journal-list')
    
  if not os.path.exists(target_dir):
    logger.warning(f"Could not find 'journal-list' in '{os.path.join(texmf_dir, 'bibtex', 'bib')}'. Macro verification skipped.")
    return macros
    
  bib_file_path = os.path.join(target_dir, 'abrv.bib')
  if not os.path.exists(bib_file_path):
    bib_file_path = os.path.join(target_dir, 'full.bib')
    
  if not os.path.exists(bib_file_path):
    logger.warning(f"Could not find 'abrv.bib' or 'full.bib' in '{target_dir}'. Macro verification skipped.")
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

def sanitize_block(block_text: str, valid_macros: Set[str], key: str) -> str:
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
  
  # 5. Verify unquoted macros
  if valid_macros:
    for match in re.finditer(r'^( *[a-zA-Z0-9_\-]+\s*=\s*)(.+?)(,?\s*)$', block_text, flags=re.MULTILINE):
      field_name = match.group(1).split('=')[0].strip()
      
      if field_name.lower() not in ['journal', 'booktitle', 'series']:
        continue
        
      val = match.group(2).strip()
      if not val or val.isdigit() or val.startswith('{') or val.startswith('"'):
        continue
      
      # Handles concatenated macros like: booktitle = W_CVPR # " 2024"
      parts = [p.strip() for p in val.split('#')]
      for part in parts:
        if not part or part.isdigit() or part.startswith('{') or part.startswith('"'):
          continue
        if part.lower() not in valid_macros:
          logger.error(f"Entry '{key}': Unknown bibstring macro '{part}' in field '{field_name}'.")

  return block_text

def sanitize_bibtex(input_file: str, output_file: str, texmf_dir: str) -> None:
  if not os.path.exists(input_file):
    raise FileNotFoundError(f"Input file '{input_file}' not found.")
    
  valid_macros = load_macros(texmf_dir)

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
      
    new_block_text = sanitize_block(block_text, valid_macros, key)
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
  parser.add_argument("-t", "--texmf", default=os.path.expanduser("~/texmf"), help="Path to the local texmf directory (default: ~/texmf)")
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
  
  sanitize_bibtex(in_file, out_file, args.texmf)

if __name__ == "__main__":
  main()
