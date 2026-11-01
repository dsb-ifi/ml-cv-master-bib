import argparse
import logging
import re
import sys
from typing import List, NamedTuple, Optional

from bibtex_utils import get_bibtex_blocks

logger = logging.getLogger(__name__)

# Placeholder for any brace-protected group or inline math; styles never change its case.
PROTECTED = "#"


class Group(NamedTuple):
  start: int
  end: int  # index of the closing brace
  depth: int  # 1 for top-level groups
  latex: bool  # accent or command group, e.g. `{\'e}`, `\v{c}`, or anything inside one


def brace_groups(title: str) -> List[Group]:
  """Lists every brace group in the title with its depth and whether it is LaTeX markup."""
  groups, stack = [], []
  for index, char in enumerate(title):
    if char == "{" and not (index > 0 and title[index - 1] == "\\"):
      command_arg = re.search(r"\\(?:[a-zA-Z]+|[^a-zA-Z\s])\s*$", title[:index]) is not None
      starts_command = title[index + 1:index + 2] == "\\"
      inside_latex = bool(stack) and stack[-1][1]
      stack.append((index, command_arg or starts_command or inside_latex))
    elif char == "}" and stack and title[index - 1] != "\\":
      start, latex = stack.pop()
      groups.append(Group(start, index, len(stack) + 1, latex))
  return groups


def extract_title(block_text: str) -> Optional[str]:
  """Returns the raw title value without its outer delimiters; braces inside quotes do not end it."""
  match = re.search(r'(?<![\w\-])title\s*=\s*', block_text, flags=re.IGNORECASE)
  if not match:
    return None

  start = match.end()
  if start >= len(block_text) or block_text[start] not in '{"':
    return None

  close = '}' if block_text[start] == '{' else '"'
  depth = 0
  for index in range(start, len(block_text)):
    char = block_text[index]
    if char == '{' and block_text[index - 1] != '\\':
      depth += 1
    elif char == '}' and block_text[index - 1] != '\\':
      depth -= 1
    if (close == '}' and depth == 0) or (close == '"' and char == '"' and index > start and depth == 0):
      return block_text[start + 1:index]
  return block_text[start + 1:]


def is_balanced(title: str) -> bool:
  depth = 0
  for index, char in enumerate(title):
    if index > 0 and title[index - 1] == '\\':
      continue
    if char == '{':
      depth += 1
    elif char == '}':
      depth -= 1
      if depth < 0:
        return False
  return depth == 0


def wraps_whole_title(title: str) -> bool:
  """True if one brace group spans a multi-word title, e.g. `{{Whole title}}`; `{{DINOv3}}` protects one word."""
  title = title.strip()
  if not re.search(r"\s", title):
    return False
  return any(g.start == 0 and g.end == len(title) - 1 and g.depth == 1 for g in brace_groups(title))


def nested_groups(title: str) -> List[str]:
  """Returns protection braces nested inside other braces, e.g. `{{DINO}}`."""
  return [title[g.start:g.end + 1] for g in brace_groups(title) if g.depth > 1 and not g.latex]


def split_word_groups(title: str) -> List[str]:
  """Returns top-level protection groups that start or end inside a word, e.g. `{DINO}v3`."""
  groups = []
  for g in brace_groups(title):
    if g.depth != 1 or g.latex:
      continue
    before = title[g.start - 1] if g.start > 0 else " "
    after = title[g.end + 1] if g.end + 1 < len(title) else " "
    if before.isalnum() or after.isalnum():
      groups.append(title[g.start:g.end + 1])
  return groups


# Letter-like commands keep their letter so case checks still see it, e.g. `{\\L}ukasz` -> `Lukasz`
LETTER_COMMANDS = re.compile(r"\\(AA|aa|AE|ae|OE|oe|ss|L|l|O|o|i|j)(?![a-zA-Z])")


def strip_latex(text: str) -> str:
  text = LETTER_COMMANDS.sub(lambda m: m.group(1), text)
  text = re.sub(r"\\[a-zA-Z]+\s*|\\.", "", text)
  return text.replace("{", "").replace("}", "")


def mask_title(title: str) -> str:
  """Returns the text a style could recase, with protected groups and math replaced by a placeholder.

  A top-level group that starts with a backslash is a BibTeX special character (`{\\'E}`, `{\\em X}`), and styles
  still change the case of its letters, so its letters stay visible. Short command arguments such as the `c`
  in `\\v{c}` are kept so warnings show whole words.
  """
  title = re.sub(r"\$[^$]*\$", PROTECTED, title)
  top = {g.start: g for g in brace_groups(title) if g.depth == 1}

  out, outside, index = [], [], 0
  while index < len(title):
    group = top.get(index)
    if group is None:
      outside.append(title[index])
      index += 1
      continue

    out.append(strip_latex("".join(outside)))
    outside = []

    content = title[group.start + 1:group.end]
    if content.startswith("\\"):
      out.append(strip_latex(content))
    elif group.latex and len(strip_latex(content)) <= 1:
      out.append(strip_latex(content))
    else:
      out.append(PROTECTED)
    index = group.end + 1

  out.append(strip_latex("".join(outside)))
  return "".join(out)


def check_entry(key: str, title: str) -> int:
  """Logs problems in one title and returns the number of errors."""
  if not is_balanced(title):
    logger.error(f"{key}: the title has unbalanced braces")
    return 1

  if wraps_whole_title(title):
    logger.error(f"{key}: the whole title is wrapped in braces; brace only names and acronyms")
    return 1

  errors = 0
  for group in nested_groups(title):
    logger.error(f"{key}: '{group}' is inside other braces; use a single pair")
    errors += 1

  for group in split_word_groups(title):
    logger.error(f"{key}: '{group}' braces part of a word; brace the whole word")
    errors += 1

  words = re.findall(r"[A-Za-z0-9#']+", mask_title(title))

  for index, word in enumerate(words):
    letters = word.replace(PROTECTED, "")
    if not re.search(r"[A-Za-z]", letters):
      continue

    if re.search(r".[A-Z]", letters):
      logger.error(f"{key}: '{word}' has capitals after its first letter; wrap it in braces")
      errors += 1
    elif re.match(r"[A-Z]", letters) and index > 0:
      logger.warning(f"{key}: '{word}' is capitalized; brace it if it is a proper name, otherwise lowercase it")

  return errors


def check_file(bib_file: str) -> int:
  with open(bib_file, "r", encoding="utf-8") as f:
    content = f.read()

  errors = 0
  for block in get_bibtex_blocks(content):
    header = re.match(r"^\s*@([a-zA-Z]+)\{([^,]*),", block[0])
    if not header or header.group(1).lower() in ("comment", "string", "preamble"):
      continue

    title = extract_title("\n".join(block))
    if title:
      errors += check_entry(header.group(2), title)

  return errors


def main() -> None:
  parser = argparse.ArgumentParser(description="Check that acronyms and mixed-case names in titles are protected with braces.")
  parser.add_argument("-r", "--replace", dest="bib_file", required=True, help="BibTeX file to check (never modified)")
  parser.add_argument("-v", "--verbose", action="count", default=0, help="Increase output verbosity (-v for INFO, -vv for DEBUG)")

  args = parser.parse_args()

  levels = [logging.WARNING, logging.INFO, logging.DEBUG]
  logging.basicConfig(level=levels[min(args.verbose, len(levels) - 1)], format="%(levelname)s: %(message)s")

  errors = check_file(args.bib_file)
  if errors:
    logger.error(f"Found {errors} unprotected title problems in {args.bib_file}.")
    sys.exit(1)

  logger.info(f"All titles in {args.bib_file} are protected.")


if __name__ == "__main__":
  main()
