import argparse
import re
import os
import logging

logger = logging.getLogger(__name__)

def sort_bibtex(input_file, output_file):
  if not os.path.exists(input_file):
    raise FileNotFoundError(f"Input file '{input_file}' not found.")

  with open(input_file, 'r', encoding='utf-8') as f:
    content = f.read()

  # Split exactly by newline to preserve spacing structure when joined later
  lines = content.split('\n')
  blocks = []
  current_block = []

  # Group file lines into individual logical blocks (entries or headers/footers)
  for line in lines:
    if re.match(r'^\s*@[a-zA-Z]+\{', line):
      if current_block:
        blocks.append(current_block)
      current_block = [line]
    else:
      current_block.append(line)
      
  if current_block:
    blocks.append(current_block)

  header_blocks = []
  entries = []
  footer_blocks = []

  # Classify each block to ensure metadata and strings aren't mistakenly sorted into the core list
  for block in blocks:
    first_line = block[0] if block else ""
    
    if not re.match(r'^\s*@[a-zA-Z]+\{', first_line):
      header_blocks.append(block)
      continue
      
    block_text = "\n".join(block)
    match = re.match(r'^\s*@([a-zA-Z]+)\{([^,]*)', block_text)
    
    if match:
      etype = match.group(1).lower()
      key = match.group(2).strip()
      
      # Keep comments, preambles, and strings in their respective locations
      if etype in ['comment', 'string', 'preamble']:
        if any("jabref-meta" in line.lower() for line in block):
          footer_blocks.append(block)
        else:
          header_blocks.append(block)
      else:
        entries.append((key, block))
    else:
      header_blocks.append(block)

  original_keys = [e[0] for e in entries]
  
  # Case-insensitive alphabetical sort
  entries.sort(key=lambda x: x[0].lower())
  sorted_keys = [e[0] for e in entries]

  if original_keys != sorted_keys:
    logger.info(f"Sorted {len(entries)} entries.")
    for i, (orig, new) in enumerate(zip(original_keys, sorted_keys)):
      if orig != new:
        logger.debug(f"Position changed at index {i}: expected '{new}', was '{orig}'")
  else:
    logger.info(f"File is already sorted. Processed {len(entries)} entries.")

  # Reconstruct the document components in order
  sorted_blocks = header_blocks + [e[1] for e in entries] + footer_blocks

  final_lines = []
  for block in sorted_blocks:
    final_lines.extend(block)

  with open(output_file, 'w', encoding='utf-8') as f:
    f.write('\n'.join(final_lines))

def main():
  parser = argparse.ArgumentParser(description="Sort a BibTeX file alphabetically by keys.")
  
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
  
  sort_bibtex(in_file, out_file)
  logger.info(f"Successfully sorted entries from {in_file} and saved to {out_file}.")

if __name__ == "__main__":
  main()