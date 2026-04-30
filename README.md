# Why do we need a master file?

We have been re-creating bibliographies (and making the same mistakes) again and again for every paper. Instead of having new versions of the same papers that need to be fixed, we can maintain one master file and only need to fix it once.

# How to use?

In your local development setup, you can clone this repository and soft-link it in the project you are using.

In Overleaf, you can add the file from the project `cv-ml master bib` into your project and refresh it when changes are made.  

You should also set up the `journal-list` file in your project (either locally or in Overleaf).

# How to contribute?

> **WARNING:** This GitHub repository is the single source of truth. Any modifications made directly to the `.bib` file inside Overleaf will be **overwritten and lost** automatically whenever changes are pushed to this repository. Always make your updates here!


Follow this checklist when adding a new entry:
1. Make sure that the paper doesn't exist already. If there are discrepancies, review the original source and fix any issues on the existing entries. If you find a preprint version on the master list, verify that it hasn't been published.
2. When adding a new entry, **do not trust the BibTeX entries on the internet**. More often than not, they are wrong. Fix them following the conventions below.
3. If you find an arXiv paper, verify that it hasn't been published already. Prefer the version with a proper venue over the preprints.
4. Make sure that the entry is sorted and the key is standardized.

# Conventions

- **Escape only proper names in titles or societies**. You need to use curly braces inside the BibTeX fields to escape proper names (e.g., you will write "{ViT}" instead of "ViT" in the titles; similarly, you must use "{IEEE}" instead of the one without curly braces).

  **Do not** escape the first letters of words to force a camel case setup, unless the capital letter is part of the proper name.

  **Do not** escape the whole title, i.e., put curly braces over the whole title field. The different styles used will have different rules that this usage will violate.

- **Use JabRef to sort and standardize keys**. Currently, all the keys are standardized using JabRef's citation key generation pattern "[auth:lower][year][veryshorttitle:lower]". You can emulate this by manually setting the key following this pattern:
  - First author's last name in lowercase
  - Year of publication
  - The first word of the title, ignoring any function words. For example, "An awesome paper on JabRef" becomes "Awesome". Then, lowercase it.

- **Use bibstrings for the journal or venue name**.  To standardize the names and allow for flexible typesetting, use the bibstrings from [journal-list](https://gitlab.com/adin/journal-list/).