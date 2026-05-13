import argparse
import re
import os
import logging
from typing import Set

logger = logging.getLogger(__name__)
from bibtex_utils import extract_field

def standardize_entry(entry_text: str, stopwords: Set[str], seen_keys: Set[str]) -> str:
  """Takes raw string of a bibtex entry and standardizes its key."""
  match = re.search(r'^(\s*@[a-zA-Z]+\{)([^,]+)(,)', entry_text)
  if not match:
    return entry_text
    
  entry_type = match.group(1)
  old_key = match.group(2)
  
  # Ignore comments, strings, and preambles
  if entry_type.lower().strip() in ['@comment{', '@string{', '@preamble{']:
    return entry_text
    
  author = extract_field(entry_text, 'author')
  year = extract_field(entry_text, 'year')
  title = extract_field(entry_text, 'title')
  
  if author and year and title:
    # 1. Parse Lastname
    first_author = re.split(r'\s+and\s+', author, flags=re.IGNORECASE)[0].strip()
    if ',' in first_author:
      lastname = first_author.split(',')[0]
    else:
      lastname = first_author.split()[-1]
      
    lastname = re.sub(r'[^a-z]', '', lastname.lower())
    
    # 2. Parse Year
    year_match = re.search(r'\d{4}', year)
    year_str = year_match.group() if year_match else ""
    
    # 3. Parse First Title Word
    title_clean = re.sub(r'\\[a-zA-Z]+\s*', '', title) # Remove basic LaTeX commands
    title_clean = re.sub(r'[^\w\s]', ' ', title_clean) # Space out punctuation 
    words = title_clean.split()
    
    title_word = ""
    for w in words:
      w_clean = w.lower()
      if w_clean and w_clean not in stopwords:
        title_word = w_clean
        break
        
    if not title_word and words:
      title_word = words[0].lower()
      
    if lastname and year_str and title_word:
      base_key = f"{lastname}{year_str}{title_word}"
      new_key = base_key
      suffix = 97  # ASCII code for 'a'
      while new_key in seen_keys:
        new_key = f"{base_key}{chr(suffix)}"
        suffix += 1
      seen_keys.add(new_key)

      if old_key != new_key:
        logger.info(f"Updated entry: '{old_key}' -> '{new_key}'")
        entry_text = entry_text.replace(f"{entry_type}{old_key},", f"{entry_type}{new_key},", 1)
      else:
        logger.debug(f"Entry unchanged: '{old_key}'")
    else:
      logger.debug(f"Could not parse valid lastname/year/title for entry: '{old_key}'")
  else:
    logger.info(f"Missing author/year/title fields for entry: '{old_key}'")

  return entry_text


def process_bibtex(input_file: str, output_file: str, stopwords_file: str) -> None:
  if not os.path.exists(stopwords_file):
    raise FileNotFoundError(f"Stopwords file '{stopwords_file}' not found. Please provide a text file containing function words.")
      
  with open(stopwords_file, 'r') as f:
    stopwords = set(word.strip().lower() for word in f.read().split() if word.strip())

  with open(input_file, 'r') as f:
    content = f.read()

  lines = content.split('\n')
  new_lines = []
  current_entry = []
  in_entry = False
  seen_keys = set()

  for line in lines:
    if re.match(r'^\s*@[a-zA-Z]+\{', line):
      if current_entry:
        new_lines.append(standardize_entry("\n".join(current_entry), stopwords, seen_keys))
      current_entry = [line]
      in_entry = True
    elif in_entry:
      current_entry.append(line)
    else:
      new_lines.append(line)
      
  if current_entry:
    new_lines.append(standardize_entry("\n".join(current_entry), stopwords, seen_keys))

  with open(output_file, 'w') as f:
    f.write("\n".join(new_lines))


def main() -> None:
  parser = argparse.ArgumentParser(description="Standardize BibTeX keys to lastnameYYYYfirstTitleWord format.")
  
  group = parser.add_mutually_exclusive_group(required=True)
  group.add_argument("-i", "--input", help="Path to the input BibTeX file")
  group.add_argument("-r", "--replace", help="Path to the BibTeX file to process and replace in-place")
  
  parser.add_argument("-o", "--output", help="Path to the output BibTeX file")
  
  default_stopwords = os.path.join(os.path.dirname(os.path.abspath(__file__)), "function_words.txt")
  parser.add_argument("-s", "--stopwords", default=default_stopwords, help="Path to the txt file containing function words")
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
  
  process_bibtex(in_file, out_file, args.stopwords)
  logger.info(f"Successfully processed entries from {in_file} and saved to {out_file}.")

if __name__ == "__main__":
  main()