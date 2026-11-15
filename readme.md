# Is This Still True?

### International Student Edition

Check the advice you hear against official sources, in a language you understand.

**Is This Still True?** is a planned multilingual claim checker for international students in the United States. A student enters something they heard about work, Optional Practical Training (OPT), Social Security numbers (SSNs), banking, or taxes. The app reads official government and university websites, compares the evidence with the claim, and explains whether it is **Supported**, **Contradicted**, or **Unclear**.

Built by a team of international students for a 24-hour hackathon, for the **Future of Intelligence** track, using the **Gemini API**.

[Repository](https://github.com/non-traitors/hackathon-project) · [Original project discussion](https://chatgpt.com/share/6af89ad7-5270-83ea-aeb2-fcc30b3aeecf)

> **Project status:** Early implementation. The checking backend, source list, language registry and UI adapter are in the repository and have been run live against the Gemini API. The live tests pass: eight golden claims (English and Arabic, MSU and UChicago), a prompt-injection check, and a cross-language check in which Arabic, Mandarin, Cantonese and Russian each kept English's verdict and cited a page in common with it. An uncached check takes about 9 seconds on average and up to about 13 seconds (up to about 19 seconds in some non-English answers); repeat checks are instant. The main interface (`app.py`) still shows a placeholder result and is not yet connected to the backend; `app_prototype.py` is wired to it. All non-English text (interface strings, glossary, routing keywords, starter claims) is a draft that no native speaker has reviewed, so those languages are labeled beta. Fee questions such as "OPT now costs $70,000" correctly return **Unclear** because the fee amounts are in USCIS tables that are not in the page text. Deployment is still to be built.

## Why we are building this

International students often rely on advice from friends, group chats, social media, and old web pages. That advice can leave out important conditions or apply to a different university, visa situation, or point in time.

We want students to be able to check a specific claim, read the evidence behind the answer, and understand what remains uncertain. Retrieved official pages are central to the project: each check uses the text of real source pages rather than relying only on a model's memory.

## How it will work

1. **Enter a claim** and select an answer language.
2. **Retrieve official sources.** The app picks curated official pages for the claim's topic and school and fetches their text.
3. **Evaluate with Gemini** by comparing the claim with that text and the student's context.
4. **Show a verdict**, a short explanation, and links to the sources used.
5. **Make uncertainty visible** when evidence is missing, conflicting, or does not match the student's situation.

```text
Claim + answer language
          |
          v
     Streamlit UI
          |
          v
Fetch curated official pages
 (sources.yaml allowlist)
          |
          v
Gemini API: evaluate the page text
          |
          v
Check every quote against the fetched text
          |
          v
Verdict + explanation + source links
```

| Verdict | Intended meaning |
| --- | --- |
| **Supported** | Retrieved evidence supports the claim within the conditions stated in the explanation. |
| **Contradicted** | Retrieved evidence conflicts with the claim; the explanation identifies the relevant conditions. |
| **Unclear** | Evidence is insufficient, conflicting, outdated, or missing context needed to assess the claim. |

The verdict labels will stay in English across languages. The explanation will use the selected language.

## MVP scope

- [ ] Claim input and answer-language selector.
- [x] Retrieval from curated official pages on approved government and university domains (backend done).
- [x] Gemini analysis grounded in the retrieved text (implemented and run live on six claims).
- [ ] Supported, Contradicted, or Unclear verdict with a short explanation.
- [ ] Clickable links to the sources actually used.
- [ ] Clear handling of empty results, missing API keys, and API failures.
- [ ] A disclaimer under every result.
- [ ] Manual review of multilingual output by the team.

### Planned languages

| Language option | Review focus |
| --- | --- |
| English | Clear explanations and consistent verdicts. |
| Arabic — العربية | Translation accuracy and right-to-left layout. |
| Mandarin Chinese (Simplified) — 中文 | Meaning, terminology, and readability. |
| Cantonese (Traditional Chinese) — 繁體中文 | Review script and language separately; Traditional Chinese script alone does not establish Cantonese quality. |
| Russian — Русский | Translation accuracy and preservation of conditions and uncertainty. |

The team will validate each option before presenting it as supported. Russian and Cantonese output may need additional review or a narrower initial scope.

### Stretch goals

- Topic buttons for Work, OPT, SSN, Banking, and Taxes.
- Color-coded verdict badges with text labels.
- A timestamp showing when the check ran.
- Source publication or update dates, when available.
- Copyable results and a polished demo interface.

## Source policy

The allowlist is the set of domains the checker may cite. The federal domains apply to every school; each school adds its own domain:

| Source domain | Intended use |
| --- | --- |
| `uscis.gov` | Immigration and work-authorization information. |
| `studyinthestates.dhs.gov` | International student guidance. |
| `ice.gov` | Student and Exchange Visitor Program information. |
| `ecfr.gov` | Applicable federal regulations. |
| `irs.gov` | Federal tax information. |
| `ssa.gov` | Social Security information. |
| `dhs.gov` | Department of Homeland Security pages (includes `studyinthestates.dhs.gov`). |
| `federalregister.gov`, `regulations.gov` | Proposed and final federal rules. |
| `oiss.isp.msu.edu`, `isp.msu.edu` | Michigan State University policies and international student guidance. |
| `internationalaffairs.uchicago.edu` | University of Chicago Office of International Affairs guidance. |

**How the allowlist is enforced.** The Gemini API's search tool has no documented way to limit results to chosen domains, so this project does not run an open web search. Instead, `sources.yaml` lists curated official pages (`seeds`) by topic and school. The checker fetches only those pages, gives Gemini their text, and accepts a citation only if its URL is one of the fetched pages and its quote appears word for word in that page's text. Claims are routed to narrow topics by keyword (on-campus work, OPT, STEM OPT, fees, rule changes, SSN, tax), so a check reads about 5–9 pages; long pages are trimmed to the passages most relevant to the claim before they are sent to the model, while quotes are still verified against the full page text. Open search for rumors about brand-new rules is a possible later addition. The page list was checked on 2026-11-14; official sites reorganize pages, so re-check it before the demo.

MSU and the University of Chicago are the supported schools. University-specific guidance must be labeled as such and must not be presented as a rule for all students in the United States.

The checker should:

- Use only source URLs and text the app actually fetched; never invent citations or quotes.
- Check whether each source applies to the claim's topic, circumstances, and time period.
- Distinguish federal rules from university-specific policies.
- Return **Unclear** when the approved sources do not provide enough evidence, including for banking questions outside the initial source coverage.
- Distinguish the time a check ran from the time a source was published or updated. A fresh fetch does not prove that a page is current.
- Treat retrieved web content as evidence, not as instructions to the application.

## Planned technology

| Tool | Role |
| --- | --- |
| Python | Application logic and API integration. |
| Streamlit | Claim input, language selection, and results interface. |
| Requests and pypdf | Fetch official pages and read their text (HTML and PDF). |
| Gemini API (`google-genai`, Interactions API) | Evidence analysis and explanations in the selected language. Default model `gemini-4-hydrogen` at `medium` thinking, overridable with `GEMINI_MODEL` and `GEMINI_THINKING`. In an eight-claim benchmark `low` thinking took about 6 s against about 9 s for `medium`, but cited fewer sources on three claims, so `medium` stays the default. Needs Python 3.10 or newer. |

Deployment details will be documented when the application is deployed.

## Getting started

You can clone the repository now:

```bash
git clone https://github.com/non-traitors/hackathon-project.git
cd hackathon-project
```

Set up and run the offline tests (no API key needed). Use Python 3.10 or newer; on Python 3.9 pip installs an older `google-genai` without the Interactions API.

```bash
python3.13 -m venv .venv313   # any Python 3.10+
.venv313/bin/pip install -r requirements.txt
.venv313/bin/python -m pytest
```

To run the checker against the Gemini API you need a Gemini API key. Copy `.env.example` to `.env` and set `GEMINI_API_KEY`; keep real keys in `.env`, local environment variables, or the deployment platform's secret store, never in version control. `app.py` does not call the backend yet; `app_prototype.py` is a standalone interface that does (`.venv313/bin/streamlit run app_prototype.py`); the pipeline it calls has been tested live, but that interface has not been clicked through with a live key.

The backend milestone is reached: English and Arabic claims were checked end to end with a live key. The next milestone is connecting the main interface (`app.py`); when that is done, update this section with the verified launch command.

### Proposed file layout

Current files:

```text
hackathon-project/
├── readme.md          # Project overview and implementation plan
├── app.py             # Streamlit interface (placeholder result, not yet connected)
├── app_prototype.py   # Standalone interface wired to the backend, in five languages
├── pipeline.py        # Fetch official pages, call Gemini, verify citations, cache
├── languages.py       # Loads the language registry
├── languages.yaml     # Languages: UI strings, glossary, routing keywords, starter claims (non-English drafts)
├── ui_adapter.py      # Turns a result into plain data any frontend can draw
├── sources.yaml       # Allowlist, topic keywords, curated source pages, out-of-scope topics
├── requirements.txt   # Python dependencies
├── .env.example       # Configuration template with no real keys (GEMINI_API_KEY, optional model and thinking level)
├── .gitignore         # Exclusions for secrets and local files
└── tests/             # Offline tests (pytest); live_golden, live_languages and live_sources need internet, and the first two need a key and credits
```

## Team workflow

| Area | Suggested owner |
| --- | --- |
| Python logic and Gemini integration | Teammate 1 |
| Source retrieval and source filtering | Teammate 2 |
| Streamlit interface and language selection | Teammate 3 |
| Testing, deployment, README, and demo | Teammate 4 |

Everyone should understand the complete flow and help review the languages they know. Agree on the search-result and verdict formats early so the components fit together.

### 24-hour build plan

| Time | Goal |
| --- | --- |
| Hours 0–2 | Agree on scope, assign responsibilities, and prepare API access. |
| Hours 2–6 | Make one English claim work through source retrieval and Gemini. |
| Hours 6–10 | Build the interface and display verdicts with source links. |
| Hours 10–14 | Add and review the language options. |
| Hours 14–18 | Test claims, missing evidence, source filtering, and failures. |
| Hours 18–21 | Fix issues and prepare a short demonstration. |
| Hours 21–24 | Deploy, update this README to match the implementation, and submit. |

## Demo and validation plan

Use the following as **test inputs, not statements of fact**. Expected verdicts must be established from the retrieved official evidence when testing.

- "F-1 students can work 30 hours per week on campus."
- "Every international student can get an SSN without a job."
- "International students never need to file US tax forms."
- "OPT now costs $70,000." (a fee rumor)
- "STEM OPT is ending." (a rule-change rumor)

`tests/live_golden.py` runs these against the real pages and the Gemini API, with acceptable verdicts fixed from the official page text rather than from the model, plus a prompt-injection check. `tests/live_languages.py` asks the same claims in every language and requires the same verdict and a shared cited page. `tests/live_sources.py` checks that every curated page still loads (it needs internet but no key). The live tests need a key and available credits.

For the demo, show the claim, search results, verdict, and explanation; switch languages; then show a case that returns **Unclear**. Explain which conditions or evidence affected the outcome.

Before calling the MVP ready, verify that:

- [ ] Every displayed citation matches a retrieved source on the allowlist.
- [ ] Explanations preserve important conditions and exceptions.
- [ ] Missing or conflicting evidence produces an appropriate uncertain result.
- [ ] Empty input and API failures produce understandable messages.
- [ ] Language changes preserve the verdict, evidence, and uncertainty.
- [ ] Arabic text is readable in the interface.
- [ ] Source dates are shown only when available, without fabricated values.
- [ ] No API keys appear in committed files or the interface.

## Limitations and responsible use

This is a hackathon prototype. Verdicts and translations can be wrong, official pages can be outdated, and the initial source list does not cover every university or topic. The tool is intended to help students find and understand evidence, not determine their eligibility or replace advice about their individual situation.

The planned notice under each result is:

> This is not legal advice. Confirm with your school's international student office before acting (the app names it).

Students at other institutions should confirm with their own international student office. Users should enter the claim they want checked without including passport numbers, immigration document numbers, or other sensitive personal details.
