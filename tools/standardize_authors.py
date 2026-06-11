import argparse
import re
import os
import logging
from typing import List, Tuple

logger = logging.getLogger(__name__)
from bibtex_utils import extract_field, get_bibtex_blocks


def has_top_level_comma(text: str) -> bool:
  """Check if text has a comma outside of braces."""
  depth = 0
  for char in text:
    if char == '{':
      depth += 1
    elif char == '}':
      depth -= 1
    elif char == ',' and depth == 0:
      return True
  return False


def tokenize_name(name: str) -> List[str]:
  """Split a name into whitespace-separated tokens, treating braced groups as atomic."""
  tokens = []
  current = []
  depth = 0
  for char in name:
    if char == '{':
      depth += 1
      current.append(char)
    elif char == '}':
      depth -= 1
      current.append(char)
    elif char.isspace() and depth == 0:
      if current:
        tokens.append(''.join(current))
        current = []
    else:
      current.append(char)
  if current:
    tokens.append(''.join(current))
  return tokens


def get_plain_letters(text: str) -> str:
  """Extract only plain letter characters, stripping LaTeX commands and braces."""
  clean = re.sub(r'\\[a-zA-Z]+\s*', '', text)
  clean = re.sub(r"""[{}\\'"`~^]""", '', clean)
  return re.sub(r'[^a-zA-Z]', '', clean)


def has_latex_commands(text: str) -> bool:
  """Check if text contains LaTeX accent commands or macros."""
  return bool(re.search(r'\\[a-zA-Z]+', text)) or bool(re.search(r"""\\['"`~^]""", text))


def title_case_word(word: str) -> str:
  """Convert a plain word to Title Case, respecting hyphens."""
  return '-'.join(part.capitalize() for part in word.split('-'))


def fix_name_casing(name_part: str) -> str:
  """Fix ALL CAPS or all-lowercase name parts to Title Case.

  Only modifies parts that contain no LaTeX commands and are
  uniformly uppercase or lowercase. Mixed-case names (e.g., LeCun,
  McCartney) are left untouched.
  """
  if has_latex_commands(name_part):
    return name_part

  letters = get_plain_letters(name_part)
  if not letters:
    return name_part

  if letters == letters.upper() or letters == letters.lower():
    words = name_part.split()
    return ' '.join(title_case_word(w) for w in words)

  return name_part


def replace_author_field(block_text: str, new_author_value: str) -> str:
  """Replace the author field value in a block, preserving surrounding formatting."""
  field_pattern = re.compile(r'\bauthor\s*=\s*', re.IGNORECASE)
  match = field_pattern.search(block_text)
  if not match:
    return block_text

  # Skip whitespace after '='
  pos = match.end()
  while pos < len(block_text) and block_text[pos].isspace():
    pos += 1

  if pos >= len(block_text) or block_text[pos] != '{':
    return block_text

  # Find matching closing brace
  brace_start = pos
  depth = 0
  brace_end = None
  for i in range(brace_start, len(block_text)):
    if block_text[i] == '{':
      depth += 1
    elif block_text[i] == '}':
      depth -= 1
      if depth == 0:
        brace_end = i
        break

  if brace_end is None:
    return block_text

  return block_text[:brace_start + 1] + new_author_value + block_text[brace_end:]


def standardize_author_field(author_value: str, key: str) -> Tuple[str, int]:
  """Standardize a single author field value.

  Returns (new_value, error_count).
  Errors indicate issues requiring manual intervention.
  """
  error_count = 0

  # Check for 'et al.' anywhere in the raw string (may appear without 'and')
  if re.search(r'\bet\s*al\.?', author_value, re.IGNORECASE):
    logger.error(
      f"Entry '{key}': Author field contains 'et al.' — "
      f"please replace with the actual author names."
    )
    error_count += 1

  # Normalize whitespace around 'and' separators
  normalized = re.sub(r'\s+and\s+', ' and ', author_value, flags=re.IGNORECASE)

  # Split into individual authors
  authors = re.split(r'\s+and\s+', normalized, flags=re.IGNORECASE)

  new_authors = []

  for author in authors:
    author = author.strip()
    if not author:
      continue

    # Check for 'others'
    stripped = author.strip('{}').strip().lower()
    if stripped in ['others']:
      logger.error(
        f"Entry '{key}': Author field contains 'and others' — "
        f"please replace with the actual author names."
      )
      error_count += 1
      new_authors.append(author)
      continue

    if has_top_level_comma(author):
      # Already in "Lastname, Firstname" format — just fix casing
      comma_idx = None
      depth = 0
      for i, char in enumerate(author):
        if char == '{':
          depth += 1
        elif char == '}':
          depth -= 1
        elif char == ',' and depth == 0:
          comma_idx = i
          break

      if comma_idx is not None:
        lastname = author[:comma_idx].strip()
        firstname = author[comma_idx + 1:].strip()

        fixed_last = fix_name_casing(lastname)
        fixed_first = fix_name_casing(firstname)

        if fixed_last != lastname or fixed_first != firstname:
          logger.info(f"Entry '{key}': Fixed casing: '{author}' -> '{fixed_last}, {fixed_first}'")

        new_authors.append(f"{fixed_last}, {fixed_first}")
      else:
        new_authors.append(author)
    else:
      # No comma — need to convert from "Firstname Lastname" format
      tokens = tokenize_name(author)

      if len(tokens) == 1:
        # Mononym or institutional author
        new_authors.append(fix_name_casing(tokens[0]))

      elif len(tokens) == 2:
        # Unambiguous: "Firstname Lastname" -> "Lastname, Firstname"
        firstname, lastname = tokens[0], tokens[1]
        fixed_first = fix_name_casing(firstname)
        fixed_last = fix_name_casing(lastname)
        new_name = f"{fixed_last}, {fixed_first}"
        logger.info(f"Entry '{key}': Converted author format: '{author}' -> '{new_name}'")
        new_authors.append(new_name)

      else:
        # 3+ tokens without comma — ambiguous compound name
        logger.error(
          f"Entry '{key}': Ambiguous author name '{author}' has {len(tokens)} "
          f"name parts but no comma. Cannot determine the lastname automatically. "
          f"Please fix manually to 'Lastname, Firstname' format."
        )
        error_count += 1
        new_authors.append(author)

  new_value = ' and '.join(new_authors)
  return new_value, error_count


def standardize_authors(input_file: str, output_file: str) -> None:
  if not os.path.exists(input_file):
    raise FileNotFoundError(f"Input file '{input_file}' not found.")

  with open(input_file, 'r', encoding='utf-8') as f:
    content = f.read()

  blocks = get_bibtex_blocks(content)
  final_lines = []

  fixed_count = 0
  total_errors = 0

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

    author = extract_field(block_text, 'author')

    if not author:
      final_lines.extend(block)
      continue

    new_author, error_count = standardize_author_field(author, key)
    total_errors += error_count

    if new_author != author:
      new_block_text = replace_author_field(block_text, new_author)
      if new_block_text != block_text:
        fixed_count += 1
      final_lines.extend(new_block_text.split('\n'))
    else:
      final_lines.extend(block)

  logger.info(f"Author standardization complete. Fixed {fixed_count} entries.")

  with open(output_file, 'w', encoding='utf-8') as f:
    f.write('\n'.join(final_lines))

  if total_errors > 0:
    logger.error(
      f"Found {total_errors} author issue(s) requiring manual fixes. "
      f"Please correct them and re-run."
    )
    raise SystemExit(1)


def main() -> None:
  parser = argparse.ArgumentParser(description="Standardize author fields in a BibTeX file.")

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

  standardize_authors(in_file, out_file)
  logger.info(f"Successfully processed entries from {in_file} and saved to {out_file}.")


if __name__ == "__main__":
  main()
