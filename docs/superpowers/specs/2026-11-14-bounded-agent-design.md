# Bounded agent for the claim checker

Date: 2026-11-14. Deadline: Sunday 2026-11-15, 12:00 PM ET.

## Why

The Future of Intelligence track dropped its OpenAI and Exa requirement on
2026-11-14 at 7:40 PM. The updated rubric scores creativity, innovation,
technical implementation, real-world impact and meaningful AI integration, and
the organizers said agentic systems will be an important part of it.

Today the backend picks pages by keyword, makes one Gemini call, and checks the
quotes. It is safe but it is not an agent, and a rumor outside the fixed page
list just returns Unclear.

## Goals

- The checker decides for itself what to read, and can read further when the
  first pages do not answer the claim.
- Every step is visible in the UI while it runs.
- The citation guarantee does not change: a verdict other than Unclear needs a
  quote that appears word for word in a page we fetched from the allowlist.
- A pasted group chat message with several rumors is checked claim by claim.

## Non-goals

- Open web search. Pages stay inside the allowlist in `sources.yaml`.
- Memory, accounts, saved history, multi-agent setups.
- Sending anything on the student's behalf. The agent only drafts.

## Anti-goals

- An agent that is slower and less reliable than the current checker in the
  live demo. "Does it work" is still a judging criterion.
- The model deciding a fact without a verified quote.

## Approaches considered

1. **Our own loop over structured JSON calls (chosen).** Each step is one Gemini
   call that returns JSON, the same call shape `pipeline.analyze` already uses
   and has been run live. Python owns the loop, the limits and the fetching.
   Trade-off: we write the loop ourselves, about 200 lines.
2. **Native function calling in the Interactions API.** Closer to a textbook
   agent, but it is an API surface nobody on the team has run yet, on a model
   released recently. Too risky with one night left.
3. **Gemini's built-in search or URL tools.** Least code, but the readme already
   notes results cannot be limited to chosen domains, and we would not hold the
   page text, so quotes could not be verified. This breaks the core guarantee.

## Design

### Where the code goes

A new file, `agent.py`, that imports helpers from `pipeline.py`
(`_fetch_one`, `select_passages`, `validate_output`, `_host_allowed`,
`CheckResult`, `SYSTEM_PROMPT`). `pipeline.py` gets one small refactor: the
Gemini call inside `analyze` moves into a helper `_generate(system, prompt,
schema)` so `agent.py` can reuse it. Nothing else in `pipeline.py` changes, and
`pipeline.check_claim` keeps working exactly as now.

### The loop, per claim

| Step | Who decides | What happens |
| --- | --- | --- |
| Split | model | A pasted message becomes up to 3 separate claims. A short single claim skips this step. |
| Plan | model | Given the claim and a catalog of every curated page for this school (URL, topic, federal or school), pick up to 4 pages and give English search terms for the claim. |
| Read | code | Fetch the picked pages. Collect the links on each page that stay inside the allowlist. |
| Judge | model | Given the passages and the list of candidate links, either return the final answer or ask to read up to 2 more pages from that list. |
| Read more | code | Fetch the requested pages, then Judge again. At most 2 extra rounds. |
| Verify | code | `pipeline.validate_output` over every page fetched in this run. Unchanged rules. |

The English search terms from Plan are also passed to `select_passages`, which
fixes passage picking for claims written in Arabic or Chinese.

### Limits

- At most 8 pages and 4 model calls per claim.
- A 45 second budget per claim. When it runs out, Judge is forced to answer with
  what it has.
- The model can only name URLs from the catalog or from the candidate link list
  it was shown. Anything else is dropped before fetching.
- Plan runs at low thinking, Judge at medium (the level already benchmarked).

### Fallback

If any agent step raises, times out, or returns unusable JSON, the claim is
handed to `pipeline.check_claim` and the trace records that the fallback ran.
The student still gets an answer.

### Output

```python
class Step(BaseModel):
    kind: Literal["split", "scope", "plan", "read", "judge", "verify", "fallback"]  # "scope" added with the scope gate
    label: str          # short, student-facing, English
    detail: list[str]   # e.g. page titles read, or quotes verified

class AgentResult(CheckResult):
    claim: str
    trace: list[Step]
```

Two entry points:

- `run(text, school_key, context, language)` is a generator. It yields each
  `Step` as it happens and finally a list of `AgentResult`, so Streamlit can
  show progress live.
- `check(text, school_key, context, language)` drains the generator and returns
  the list, for tests and scripts.

### UI bridge

`backend.py` exposes `check_claim(claim, language, school)` in the exact shape
the `frontend` branch's stub uses, so the frontend swaps one import. It maps
school display names to keys, native language names to English ones, fills
`headline` from the first sentence of the explanation, and turns a missing date
into an empty string. It also exposes `stream(...)` for the live step display.

The pill shows the rule status when it is set, otherwise Supported,
Contradicted or Unclear. The frontend needs two extra pill colors for that.

### Tests

Offline, with a fake model and a fake fetcher, no key needed:

- A URL the model names that is not in the catalog or link list is never fetched.
- Links that leave the allowlist are never offered to the model.
- The page and call limits hold when the model keeps asking for more.
- A quote from a page that was never fetched is rejected and the verdict drops
  to Unclear.
- Any agent error ends in the single-pass fallback, and the trace says so.
- A three-rumor message yields three results.

`tests/live_golden.py` gains an agent run of the same golden claims.

## Calls made without asking

- New file `agent.py` instead of rewriting `pipeline.py`, to stay out of
  Isaac's way.
- The numeric limits above (3 claims, 4 picked pages, 2 extra rounds, 8 pages,
  45 seconds). They are constants and easy to tune after a live run.
- English-only step labels in the trace for now.

## Open

- Isaac owns `pipeline.py`. The `_generate` refactor needs their OK.
- A Gemini key in `.env` is needed for any live run.
- Latency is unmeasured. If a full agent run exceeds about 30 seconds in live
  tests, drop the extra rounds to 1.
