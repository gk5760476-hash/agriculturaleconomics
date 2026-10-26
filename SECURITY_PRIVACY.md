# Security and privacy

- **No personal data.** All inputs are aggregates (district, state, national). Nothing identifies a farmer, borrower or bank account.
- **One exception, contained.** The DES MSP PDF (`data/raw/prices/msp/*.pdf`) has a cover letter naming a private RTI applicant with contact details. The PDF is git-ignored and never published; only the transcribed MSP values (`des_msp_2004-05_to_2026-27_transcribed.csv`) are used.
- **No credentials** anywhere in the code; every source is public and downloaded without login.
- **No uploads or code execution.** The dashboard reads only data embedded at build time. Embedded JSON is escaped (`</` → `<\/`) so data cannot break out of the script tag.
- **Downloaded files are data, not code.** Scripts live in `src/`, run with `python -I`, and only read `data/raw/`.
- **Provenance.** `data/metadata/download_manifest.csv` records the source URL or Drive ID, size, SHA-256 and retrieval time of every raw file.
- **Redistribution.** Check the licence terms of RBI, IMD, OEA and DES before publishing derived tables beyond coursework.
