import argparse
import re
import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)
from bibtex_utils import extract_field, get_bibtex_blocks

def clean_title(title: Optional[str]) -> str:
  """Cleans a title for robust comparison."""
  if not title:
    return ""
  t = re.sub(r'\\[a-zA-Z]+\s*', '', title) # Remove basic LaTeX commands
  t = re.sub(r'[{}]', '', t)        # Remove braces
  t = re.sub(r'[^\w\s]', ' ', t)      # Replace punctuation with spaces
  return " ".join(t.split()).lower()

def clean_authors(author_str: Optional[str]) -> str:
  """Cleans and sorts author lists for robust comparison regardless of order."""
  if not author_str:
    return ""
  a = re.sub(r'\\[a-zA-Z]+\s*', '', author_str)
  a = re.sub(r'[{}]', '', a)
  a = re.sub(r'[^\w\s]', ' ', a)
  
  # Split, clean whitespace, and sort to handle arbitrarily ordered author lists
  authors = [x.strip() for x in re.split(r'\s+and\s+', a, flags=re.IGNORECASE) if x.strip()]
  authors.sort()
  return " and ".join(authors).lower()

def find_and_deduplicate(input_file: str, output_file: str) -> None:
  if not os.path.exists(input_file):
    raise FileNotFoundError(f"Input file '{input_file}' not found.")

  with open(input_file, 'r', encoding='utf-8') as f:
    content = f.read()

  blocks = get_bibtex_blocks(content)

  header_blocks = []
  footer_blocks = []
  
  seen_entries = []
  final_blocks = []
  dedup_count = 0
  error_count = 0

  for block in blocks:
    first_line = block[0] if block else ""
    block_text = "\n".join(block)
    match = re.match(r'^\s*@([a-zA-Z]+)\{([^,]*)', block_text)
    
    if not match:
      header_blocks.append(block)
      continue
      
    etype = match.group(1).lower()
    key = match.group(2).strip()
    
    if etype in ['comment', 'string', 'preamble']:
      if any("jabref-meta" in line.lower() for line in block):
        footer_blocks.append(block)
      else:
        header_blocks.append(block)
      continue
      
    # Extract all fields for detailed conflict comparisons
    field_matches = re.finditer(r'^\s*([a-zA-Z0-9_\-]+)\s*=\s*', block_text, re.MULTILINE)
    field_names = set(m.group(1).lower() for m in field_matches)
    
    fields = {}
    for fn in field_names:
      val = extract_field(block_text, fn)
      if val is not None:
        fields[fn] = " ".join(val.split())

    raw_title = fields.get('title', '')
    raw_author = fields.get('author', '')
    
    c_title = clean_title(raw_title)
    c_author = clean_authors(raw_author)
    
    is_duplicate = False
    
    for seen in seen_entries:
      title_match = (c_title != "" and c_title == seen['title'])
      author_match = (c_author != "" and c_author == seen['author'])
      key_match = (key == seen['key'])
      
      if title_match and author_match:
        # Check for conflicting properties (only if they appear in both)
        conflicts = []
        for k, v in fields.items():
          if k in seen['fields'] and seen['fields'][k] != v:
            conflicts.append((k, seen['fields'][k], v))
            
        if conflicts:
          logger.error(f"Conflicting fields found between '{seen['key']}' & '{key}' (Title: {raw_title}). Entries will not be merged:")
          for k, v1, v2 in conflicts:
            logger.error(f" - Field '{k}': existing='{v1}' vs new='{v2}'")
          error_count += 1
        else:
          is_duplicate = True
          dedup_count += 1
          logger.info(f"Deduplicated identical entry: '{key}' (merged into '{seen['key']}')")
        break
        
      elif title_match and not author_match:
        logger.warning(f"Title match with differing authors:\n 1) [{seen['key']}] {seen['raw_author']}\n 2) [{key}] {raw_author}")
        error_count += 1
        
      elif key_match:
        logger.warning(f"Duplicate key '{key}' found but refers to different entries! (Titles/Authors differ).")
        error_count += 1
        
    if not is_duplicate:
      seen_entries.append({
        'key': key,
        'title': c_title,
        'author': c_author,
        'raw_author': raw_author,
        'fields': fields
      })
      final_blocks.append(block)

  logger.info(f"Scan complete. Deduplicated {dedup_count} identical entries.")

  if error_count > 0:
    logger.error(f"Found {error_count} unresolved duplicates/conflicts.")

  # Reconstruct the document
  final_lines = []
  for block in header_blocks + final_blocks + footer_blocks:
    final_lines.extend(block)

  with open(output_file, 'w', encoding='utf-8') as f:
    f.write('\n'.join(final_lines))

def main() -> None:
  parser = argparse.ArgumentParser(description="Find and deduplicate entries in a BibTeX file.")
  
  group = parser.add_mutually_exclusive_group(required=True)
  group.add_argument("-i", "--input", help="Path to the input BibTeX file")
  group.add_argument("-r", "--replace", help="Path to the BibTeX file to process and replace in-place")
  
  parser.add_argument("-o", "--output", help="Path to the output BibTeX file")
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
  
  find_and_deduplicate(in_file, out_file)

if __name__ == "__main__":
  main()
