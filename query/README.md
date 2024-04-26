# ELAN Clause Structure Query Tool

This module requires [Grew-match](https://match.grew.fr) to be installed.

It also requires files named `data.conllu` and `data.json` in this directory.

```bash
$ for fname in elan_files/*.eaf; do ./elan2conllu.py "$fname" >> data.conllu; done
$ ./conllu2json.py data.conllu data.json
```
