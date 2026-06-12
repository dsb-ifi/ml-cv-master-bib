import subprocess
import argparse
import os
import sys

def find_journal_list_file():
    for filename in ['journal-list/abrv.bib', 'journal-list/full.bib']:
        try:
            result = subprocess.run(['kpsewhich', filename], stdout=subprocess.PIPE, text=True, check=True)
            path = result.stdout.strip()
            if path and os.path.exists(path):
                return path
        except (subprocess.CalledProcessError, FileNotFoundError):
            continue
    return ""

def load_journal_list_content():
    bib_file_path = find_journal_list_file()
    if bib_file_path:
        with open(bib_file_path, 'r', encoding='utf-8') as f:
            return f.read()
    return ""

def main():
    parser = argparse.ArgumentParser(description='Check BibTeX file validity using biber.')
    parser.add_argument('-r', dest='bib_file', required=True, help='BibTeX file to check')
    parser.add_argument('-v', action='store_true', help='Verbose output')
    args = parser.parse_args()

    bib_file = args.bib_file
    out_bib = 'biber_check_temp.bib'
    temp_input = 'temp_check_input.bib'
    
    # Combine journal-list and the target bib file to resolve macros
    journal_content = load_journal_list_content()
    with open(bib_file, 'r', encoding='utf-8') as f:
        bib_content = f.read()
        
    with open(temp_input, 'w', encoding='utf-8') as f:
        if journal_content:
            f.write(journal_content + '\n\n')
        f.write(bib_content)
    
    # Run biber tool mode without datamodel validation to ignore missing field warnings like journaltitle
    cmd = ['biber', '--tool', temp_input, '--output-file', out_bib]
    if not args.v:
        cmd.append('--quiet')

    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        if result.returncode != 0:
            print("BibTeX check failed!")
            if result.stdout:
                print(result.stdout)
            sys.exit(result.returncode)
        else:
            if args.v and result.stdout:
                print(result.stdout)
            print(f"BibTeX check passed for {bib_file}!")
    finally:
        # Clean up temporary files that might have been created by biber
        temp_files = [out_bib, temp_input, temp_input + '.blg', out_bib + '.blg', 'temp_check_input.blg']
        for f in temp_files:
            if os.path.exists(f):
                try:
                    os.remove(f)
                except OSError:
                    pass

if __name__ == '__main__':
    main()
