# Configurable variables
BIB_FILE ?= cv-ml-master.bib
PYTHON ?= python
OPTS ?= -v

.PHONY: help sanitize sort keys duplicates standardize

help:
	@echo "Available commands:"
	@echo "  make sanitize   - Sanitize LaTeX macros, months, and page ranges"
	@echo "  make sort       - Sort entries by author, year, and title"
	@echo "  make keys       - Standardize citation keys"
	@echo "  make duplicates - Find and merge duplicate entries"
	@echo "  make standardize- Run the full pipeline sequentially"
	@echo ""
	@echo "Options:"
	@echo "  make standardize BIB_FILE=other.bib OPTS=-vv"

sanitize:
	$(PYTHON) tools/sanitize_bibtex.py -r $(BIB_FILE) $(OPTS)

sort:
	$(PYTHON) tools/sort_bibtex.py -r $(BIB_FILE) $(OPTS)

keys:
	$(PYTHON) tools/standardize_keys.py -r $(BIB_FILE) $(OPTS)

duplicates:
	$(PYTHON) tools/find_duplicates.py -r $(BIB_FILE) $(OPTS)

standardize: sanitize sort keys duplicates
	@echo "========================================"
	@echo " Pipeline complete for $(BIB_FILE)!"
	@echo "========================================"
