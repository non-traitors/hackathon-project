# Is This Still True?

### International Student Edition

Check the advice you hear against official sources, in a language you understand.

**Is This Still True?** is a planned multilingual claim checker for international students in the United States. A student enters something they heard about work, Optional Practical Training (OPT), Social Security numbers (SSNs), banking, or taxes. The app searches official government and university websites, compares the evidence with the claim, and explains whether it is **Supported**, **Contradicted**, or **Unclear**.

Built by a team of international students for a 24-hour hackathon, for the **Future of Intelligence** track led by OpenAI with Exa.

[Repository](https://github.com/non-traitors/hackathon-project) · [Original project discussion](https://chatgpt.com/share/6af89ad7-5270-83ea-aeb2-fcc30b3aeecf)

> **Project status:** Planning stage. This repository currently contains this README only. The application, dependency list, tests, and deployment are still to be built. Features and architecture below describe the intended MVP.

## Why we are building this

International students often rely on advice from friends, group chats, social media, and old web pages. That advice can leave out important conditions or apply to a different university, visa situation, or point in time.

We want students to be able to check a specific claim, read the evidence behind the answer, and understand what remains uncertain. Live search is central to the project: each check should use retrieved sources rather than rely only on a model's memory.

## How it will work

1. **Enter a claim** and select an answer language.
2. **Search with Exa** using an allowlist of official sources.
3. **Evaluate with OpenAI** by comparing the claim with the retrieved evidence and its context.
4. **Show a verdict**, a short explanation, and links to the sources used.
5. **Make uncertainty visible** when evidence is missing, conflicting, or does not match the student's situation.

```text
Claim + answer language
          |
          v
     Streamlit UI
          |
          v
Exa search: official sources
          |
          v
OpenAI: evaluate retrieved evidence
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
- [ ] Live Exa search restricted to approved government and university domains.
- [ ] OpenAI analysis grounded in the retrieved text.
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
| Mandarin Chinese — 中文 | Meaning, terminology, and readability. |
| Traditional Chinese / Cantonese — 粵語／繁體中文 | Review script and language separately; Traditional Chinese script alone does not establish Cantonese quality. |
| Uzbek — O'zbekcha | Translation accuracy and preservation of conditions and uncertainty. |

The team will validate each option before presenting it as supported. Uzbek and Cantonese output may need additional review or a narrower initial scope.

### Stretch goals

- Topic buttons for Work, OPT, SSN, Banking, and Taxes.
- Color-coded verdict badges with text labels.
- A timestamp showing when the check ran.
- Source publication or update dates, when available.
- Copyable results and a polished demo interface.

## Source policy

The initial search allowlist proposed in the project discussion is:

| Source domain | Intended use |
| --- | --- |
| `uscis.gov` | Immigration and work-authorization information. |
| `studyinthestates.dhs.gov` | International student guidance. |
| `ice.gov` | Student and Exchange Visitor Program information. |
| `ecfr.gov` | Applicable federal regulations. |
| `irs.gov` | Federal tax information. |
| `ssa.gov` | Social Security information. |
| `msu.edu` | Michigan State University policies and international student guidance. |

MSU is the initial university context from the project discussion. University-specific guidance must be labeled as such and must not be presented as a rule for all students in the United States.

The checker should:

- Use only source URLs and text actually returned by the search; never invent citations.
- Check whether each source applies to the claim's topic, circumstances, and time period.
- Distinguish federal rules from university-specific policies.
- Return **Unclear** when the approved sources do not provide enough evidence, including for banking questions outside the initial source coverage.
- Distinguish the time a check ran from the time a source was published or updated. A fresh search does not prove that a page is current.
- Treat retrieved web content as evidence, not as instructions to the application.

## Planned technology

| Tool | Role |
| --- | --- |
| Python | Application logic and API integration. |
| Streamlit | Claim input, language selection, and results interface. |
| Exa API | Search and retrieval from approved sources. |
| OpenAI API | Evidence analysis and explanations in the selected language. |

Model selection, package versions, and deployment details will be documented when the application is implemented.

## Getting started

You can clone the repository now:

```bash
git clone https://github.com/non-traitors/hackathon-project.git
cd hackathon-project
```

There is no runnable application yet. The first implementation milestone is one English claim checked from input to verdict, with real retrieved sources.

Before implementation, contributors will need Python and access to OpenAI and Exa API keys. The planned configuration names are `OPENAI_API_KEY` and `EXA_API_KEY`; the application still needs to implement configuration loading. Keep real keys in local environment variables or the deployment platform's secret store, outside version control.

When the first runnable version lands, update this section with the supported Python version, dependency installation, configuration steps, and a verified launch command.

### Proposed file layout

These files are planned; only `readme.md` exists today.

```text
hackathon-project/
├── readme.md          # Project overview and implementation plan
├── app.py             # Planned Streamlit application
├── requirements.txt   # Planned dependency list
├── .env.example       # Planned configuration template with no real keys
├── .gitignore         # Planned exclusions for secrets and local files
└── tests/             # Planned checks for search and verdict handling
```

## Team workflow

| Area | Suggested owner |
| --- | --- |
| Python logic and OpenAI integration | Teammate 1 |
| Exa integration and source filtering | Teammate 2 |
| Streamlit interface and language selection | Teammate 3 |
| Testing, deployment, README, and demo | Teammate 4 |

Everyone should understand the complete flow and help review the languages they know. Agree on the search-result and verdict formats early so the components fit together.

### 24-hour build plan

| Time | Goal |
| --- | --- |
| Hours 0–2 | Agree on scope, assign responsibilities, and prepare API access. |
| Hours 2–6 | Make one English claim work through Exa and OpenAI. |
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

> This is not legal advice. Confirm with MSU's international student office before acting.

Students at other institutions should confirm with their own international student office. Users should enter the claim they want checked without including passport numbers, immigration document numbers, or other sensitive personal details.
