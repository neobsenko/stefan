# Stefan

A local-first text redaction appliance for Swedish SMEs that need to use external AI tools (ChatGPT, Claude, Gemini, Copilot) without leaking personal data, client information, or sensitive business content to third-party servers. Sold as a pre-configured Raspberry Pi 5 that runs entirely on-premise — no data ever leaves the building.

---

## How it works

You paste raw text (or drag a PDF) into Stefan. The system detects sensitive entities — names, personal identification numbers (personnummer), phone numbers, email addresses, organizations, addresses, bank account details, IBANs, URLs, and more — and replaces each one with a numbered placeholder (e.g. `PERSON_1`, `ORG_2`, `SSN_1`, `IBAN_1`).

The redacted text is copied to your clipboard with a system instruction wrapper that tells the receiving AI to preserve placeholders verbatim. You paste it into ChatGPT, get a response, then paste the response back into Stefan. The system detects placeholder tokens and rehydrates them with the original values, producing a final output you can use in your actual workflow.

---

## Why it exists

Under the EU AI Act (Regulation 2024/1689), most obligations for deployers of AI systems take effect on August 2, 2026. Combined with existing GDPR obligations under Article 32 (security of processing) and Article 28 (processor agreements), Swedish SMEs that allow employees to paste personal data into ChatGPT face real legal exposure. Stefan is a one-time-purchase compliance appliance: customers pay roughly 12,900 SEK for hardware plus an annual support contract, and receive a documented technical control they can show to auditors, clients, and regulators.

Stefan is **not** an AI model. It does not generate text or make decisions about people. It is a deterministic, rule-based, auditable technical control under GDPR Article 32 — without triggering provider obligations under the EU AI Act.

---

## Quick start

```bash
# Redact text (reads from stdin, writes redacted text + .stefan_map.json)
echo "Kontakta Johan på 070-123 4567" | stefan redact -o output.txt

# Hydrate text (replace placeholders with original values)
cat ai_response.txt | stefan hydrate -o final.txt

# Start the web UI (http://stefan.local)
stefan serve
```

See `stefan serve --help` for options including `--port 5000` (no admin required) and `--no-spacy` (regex-only, faster startup).

---

## Repository structure

```
stefan/
├── cli.py           # stefan redact / serve / hydrate commands
├── redactor.py      # Core redaction logic
├── hydrator.py      # Placeholder rehydration
├── web.py           # Flask web server
├── detectors/       # Detection modules (regex, dictionary, morphology, etc.)
├── data/            # Dictionary files
└── static/
    └── index.html   # Web UI (single-page app)
```

For details on how detection works, detector priorities, and how to extend the system, see `AGENTS.md`.
