# Chat engine design

Date: 2026-11-15. Short design, written under the noon deadline.

## Why

The app checks one rumor and stops. Students do not think in single rumors. They ask a
question, then a follow up, then "what about STEM students?". The team wants a real chat
with the agent, and every reply must be facts from official pages, never free text.

## Goals

- A back and forth conversation that remembers earlier turns.
- Two kinds of reply, both made of verified quotes:
  - a rumor gets the existing verdict card (Supported, Contradicted, Unclear);
  - a question gets a list of facts, each one a sentence with the exact quote and link
    that backs it.
- The harness applies to every turn: topic gate, allowlist, page and call limits.

## Not goals

- No free chat. No greetings beyond one fixed line. No opinions or advice beyond what a
  quote supports.
- No saved conversations. History lives in memory for the session only.
- No new retrieval. The chat reads the same curated official pages as the agent.

## What would make it a failure

A sentence on screen that no official page says. If the model writes a fact and the
quote is not found word for word on the page we fetched, that fact is dropped. If no
fact survives, the student sees fixed text saying we could not confirm it, plus the
question to send to their school office.

## Approaches

1. **A chat layer on top of the existing agent (picked).** New `chat.py`. It turns each
   message into a standalone question using the history, sends rumors to `agent.run`
   unchanged, and answers questions with a new facts mode that reuses the agent's
   fetch, allowlist, page views and quote check. All limits stay in code.
2. **Gemini's own chat with tool calling.** The model decides when to fetch. Rejected:
   the bounds move from code into the model's choices, and prose replies cannot be
   checked sentence by sentence.
3. **Feed the history into the claim checker as it is.** Rejected: a question has no
   Supported or Contradicted verdict, so "how do I apply for OPT?" would always come
   back Unclear.

## How a turn works

1. **Limits first, no model.** Message at most 600 characters. At most 20 student turns
   per conversation, then fixed text asking to start a new chat. The keyword scope gate
   runs here.
2. **Route (one small model call).** Input: the last 6 turns and the new message, all
   marked untrusted. Output: `in_scope`, `kind` (claim, question, greeting) and
   `standalone`, the message rewritten so it makes sense alone. If the call fails or
   `in_scope` is missing, the turn fails closed with fixed text. Out of scope and
   greeting replies are fixed text from `languages.yaml`. Only the student's own words
   and our verified facts go into the history given to the model, never raw page text.
3. **Claim.** `agent.run(standalone, ...)`, first result. Same card as today.
4. **Question.** Plan pages (the agent's plan call, which is a second scope gate), read
   up to 4, one model call that returns up to 5 facts as `{statement, url, quote,
   quote_translation}` and may ask for 2 more pages once. Code keeps a fact only when
   its quote has at least 4 words and appears word for word on that page. Statements are
   in the student's language, quotes stay in English.
5. **Reply.** Built by code from what survived: the facts, their sources, and the
   question for the office when nothing survived.

Budget per turn: at most 4 model calls and 6 pages for a question. Claims keep the
agent's own limits.

## Interface

The home screen stays as it is. After the first answer, the page becomes a thread:
each student message, then the answer under it, then a box to ask a follow up (with the
microphone). "Start over" clears the thread. Listen works on every answer.

The chat is the default path. `USE_AGENT` goes away. If the engine fails on a claim, the
existing fallback to the simple checker still applies.

## Left to the builder

Prompt wording, the exact look of a fact row (reuse the highlighted quote style), and
the new interface strings in five languages (drafts until reviewed).

## Tests

Offline, with the model and fetch stubbed: follow up is rewritten using history; out of
scope and greeting return fixed text and read nothing; route failure fails closed; a
fact with a made up quote is dropped; no surviving facts gives the fixed "could not
confirm" reply; turn limit; history never contains page text; injected instructions in
history do not change `in_scope` handling in code.
