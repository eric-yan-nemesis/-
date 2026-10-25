# Vocabulary source and attribution

The bundled C1/C2 reference is **Octanove Vocabulary Profile C1/C2, version 1.0**, created by **Octanove Labs**, distributed by [Open Language Profiles](https://github.com/openlanguageprofiles/olp-en-cefrj). The vocabulary profile is licensed under [Creative Commons Attribution-ShareAlike 4.0 International](https://creativecommons.org/licenses/by-sa/4.0/).

This is an open vocabulary profile. It is not an official Cambridge word list, an English Vocabulary Profile export, or an authoritative certification of every meaning or occurrence of a word. CEFR itself does not prescribe a universal exhaustive English vocabulary list. No proprietary Cambridge dictionary definitions or examples are bundled.

## Pinned files and integrity

Source repository commit: `d4e45b75b38f27b30dfc5c44d8c571aec7e7092f`. Retrieved 25 October 2026 over verified HTTPS.

| Local file | Pinned source | SHA-256 |
| --- | --- | --- |
| `octanove-vocabulary-profile-c1c2-1.0.csv` | [Original CSV](https://raw.githubusercontent.com/openlanguageprofiles/olp-en-cefrj/d4e45b75b38f27b30dfc5c44d8c571aec7e7092f/octanove-vocabulary-profile-c1c2-1.0.csv) | `18c33a407f2f89f7b8de9671c6d45fe3ea0bce45e7d2d7dcaab48d73e0f7b380` |
| `UPSTREAM_README.md` | [Upstream terms and attribution](https://raw.githubusercontent.com/openlanguageprofiles/olp-en-cefrj/d4e45b75b38f27b30dfc5c44d8c571aec7e7092f/README.md) | `8b69f7366fa3c7be328cb9ba02ceb7b3725697f36125bb75b85131d664b5e359` |
| `CC-BY-SA-4.0.txt` | [SPDX copy of the license](https://raw.githubusercontent.com/spdx/license-list-data/31ba1a50e5397e00a304dbadc76531740e89ee48/text/CC-BY-SA-4.0.txt) | `cde7883b9050a1104f4ac19a1572aafd6e5d7323b68351aaf51fbf4beba54966` |

The original CSV and upstream README are preserved byte-for-byte. The upstream README explicitly states: “The Octanove Vocabulary Profile for C1/C2 levels can be used under a Creative Commons Attribution-ShareAlike 4.0 International License.” There is no separate upstream LICENSE file; the README is the evidence of the source's licensing. The bundled license text is a separate, pinned SPDX copy.

## Reuse obligations

Retain attribution to Octanove Labs and Open Language Profiles, the source link, the CC BY-SA 4.0 link, and an indication of modifications when sharing or displaying this vocabulary data. Preserve existing notices. Share adapted vocabulary data under CC BY-SA 4.0 or a license permitted by its terms, without added restrictions. This notice does not grant rights to third-party dictionaries or their definitions/examples. The license applies to the vocabulary data and adaptations; application code and separately authored teaching annotations have their own provenance.

The raw CSV is unchanged. `reference-evidence.json` contains a factual coverage summary, ten selected original source rows, seven lookup checks, and attribution metadata; selection and formatting of that companion file are adaptations of the profile licensed under CC BY-SA 4.0. Application transformations such as normalization and deduplication must be described where used.

## Exact reference coverage

| Measure | Count |
| --- | ---: |
| Raw CSV rows | 2,136 |
| Raw C1 rows | 1,111 |
| Raw C2 rows | 1,025 |
| Unique headwords across both levels | 1,955 |
| Unique C1 headwords | 1,009 |
| Unique C2 headwords | 972 |
| Unique headword/POS pairs across both levels | 2,076 |
| Distinct complete rows, including level and notes | 2,108 |
| Exact duplicate rows | 28 |
| Rows containing notes | 45 |

Columns are `headword`, `pos`, `CEFR`, and `notes`. Raw POS counts are noun 834, adjective 561, verb 460, adverb 273, preposition 5, conjunction 1, blank 1, and `vern` 1. Known anomalies include `batter` with a blank POS and the note “one who bats”, `remonstrate` with `vern`, and `enviable` marked adverb. The source is preserved rather than silently corrected.

These are lexical entries, not full sense inventories. Occasional notes distinguish senses, such as `cast` noun “plaster cast, mold” and `brief` noun “legal term”; most rows have no note, no sense identifier, and no definition. A surface match alone cannot resolve part of speech or sense in an uploaded passage. Keep POS/sense uncertainty visible and do not label an arbitrary passage occurrence as a verified C1/C2 meaning solely because its spelling appears here. Do not infer that an absent word has a particular level.

## Lower-level checks and sample rows

`reference-evidence.json` includes ten exact C1/C2 source records: `concur`, `alleviate`, `candid`, `resilient`, and `cast` noun at C1; `exude`, `pervasive`, `ephemeral`, `meticulous`, and `brief` noun at C2. Preserve the notes for the two meaning-specific examples.

All seven requested lookup examples are absent from the Octanove C1/C2 source. A read-only comparison with the same pinned repository's [CEFR-J Vocabulary Profile v1.5](https://raw.githubusercontent.com/openlanguageprofiles/olp-en-cefrj/d4e45b75b38f27b30dfc5c44d8c571aec7e7092f/cefrj-vocabulary-profile-1.5.csv) found:

| Headword | CEFR-J v1.5 result |
| --- | --- |
| substantial | B1, adjective |
| ambiguous | B2, adjective |
| facilitate | B2, verb |
| assess | B2, verb |
| ubiquitous | No match |
| nuance | No match |
| carry out | No match |

These findings are limited evidence for those exact lexical entries. They are not a universal classification of all senses. In particular, unknown words must remain unknown or explicitly estimated; absence from either profile does not validate a fallback C1/C2 label.

CEFR-J citation: **The CEFR-J Wordlist Version 1.5. Compiled by Yukio Tono, Tokyo University of Foreign Studies. Retrieved from http://www.cefr-j.org/download.html by Open Language Profiles on 20 January 2020.** Copyright belongs to Tono Laboratory at TUFS. The upstream README permits research and commercial use at no charge with proper citation; it provides no separate standard license or explicit redistribution statement for that dataset. Accordingly, the complete A1–B2 dataset is not bundled. Only the limited lookup findings are recorded here and in `reference-evidence.json`.
