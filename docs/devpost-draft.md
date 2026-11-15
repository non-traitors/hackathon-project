# Is This Still True?

**Tagline (short field):** Check the rumor before you act on it. Answers for international students, quoted from official sources, in your language.

---

## Inspiration

Every international student has a group chat. Every few weeks, that chat panics.

"OPT is cancelled." "You can work 30 hours now." "The fee is $70,000."

Some of it is half true. Some of it is true for a different school or a different visa. Some of it is a proposal that never became a rule. Acting on the wrong one can cost you your status.

We are four international students from four universities. We have all received those messages. We wanted one place to ask: is this still true?

## What it does

You type what you heard, or say it out loud. You get one of three answers.

**Supported. Contradicted. Unclear.**

Each answer comes with the exact sentence from the official page that settles it, a link to that page, and who the rule applies to. If the rumor is about a rule change, it also says whether the rule is in effect, only proposed, or blocked.

Three things make it different.

**It cannot bluff.** Every quote is checked word for word against the page we fetched. If the quote is not there, the answer drops to Unclear. A confident verdict without a verified quote is not possible.

**It only reads official sources.** USCIS, DHS, ICE, the IRS, the Social Security Administration, the Federal Register, and your own school's international student office. Nothing else.

**It speaks your language.** Answers come in English, Arabic, Mandarin, Cantonese and Russian. The quote stays in the original English, with a translation beside it, so nothing is lost. You can also ask by voice and listen to the answer.

When the answer is Unclear, it does not leave you there. It writes the question you should send to your school's office, in English, ready to copy.

## How we built it

**The checker.** Python and Streamlit. For each claim we fetch a small set of curated official pages, give Gemini that exact text, and ask for a verdict with quotes. Then our own code verifies every quote against the text we hold. The model proposes. The code decides what is allowed on screen.

**The agent.** On top of the checker we built a bounded agent. It plans which official pages to read, follows links that stay on the allowlist, and decides when it has enough. It works within fixed limits: 8 pages and 4 model calls per claim. It can choose what to read. It cannot choose the answer without a verified quote. If anything fails, it falls back to the simple checker.

**The harness.** The agent only answers questions about being an international student in the United States. Off topic requests stop before a single page is read, and the reply is fixed text the model cannot change. Every prompt treats the claim, the pasted message and the web pages as untrusted.

**Voice.** ElevenLabs turns a spoken question into text and reads the answer back. A spoken question goes through the same checks as a typed one.

**Languages.** One registry file holds the interface text, a glossary of key terms, and routing keywords for each language.

**Tests.** 189 automated tests run without any API key. They cover the quote check, the allowlist, the limits, the fallback, and the scope gate.

## Challenges we ran into

**Our track changed mid hackathon.** We planned around live web search. The search credits fell through, so we rebuilt retrieval around curated official pages. It turned out stricter and more trustworthy than open search.

**The app could freeze for six hours.** When the model's rate limit was hit, the SDK quietly waited for the retry time the server gave it. That time was about six hours. We found it by dumping the stack of a stuck call, and now a rate limit fails in seconds with a clear message.

**One school's pages leaked into another's.** An independent review of our agent found that a shared cache could let a page fetched for one university be cited for another. We now check the allowlist on every fetch, before the cache.

**A one word quote proved nothing.** A quote like "on" appears on every page. A quote now needs at least four words to carry a verdict.

## Accomplishments that we're proud of

- A verdict that is impossible to show without a verified quote from an official page.
- A golden set of real rumors that passes against live official pages, in English and Arabic.
- An agent that is bounded by code, not by hope: fixed limits, a fixed allowlist, and a scope gate that fails closed.
- Voice that works in both directions: ask out loud, and listen to the answer.
- 189 tests written in 24 hours, and a review that found real bugs before the judges did.

## What we learned

Trust is a design choice. The useful question was never "how smart is the model". It was "what is the model not allowed to do". Almost every good decision we made was a limit: only these sites, only quotes we can find, only this topic, only this many steps.

We also learned that "Unclear" is a feature. For a student deciding whether to book a flight or take a job, an honest "we could not confirm this, here is who to ask" beats a confident guess.

## What's next

- More schools. Adding one is a few lines in a config file.
- Watch a claim. Save a check and get told when the answer changes.
- Where did this rumor come from. Show the proposal or news story that started it.
- Review of every language by native speakers before it leaves beta.

## Built with

Python, Streamlit, Gemini API, ElevenLabs (speech to text and text to speech), pydantic, pytest

## AI tools we used

The rules ask us to say which AI tools we used and how.

- **Gemini API** is part of the product. It reads the official pages and writes the explanation.
- **ElevenLabs** is part of the product. It transcribes spoken questions and reads answers aloud.
- **Claude Code** helped audit the repository and write the agent, the scope gate, the voice module and their tests, from a design and plan the team reviewed.
- **ChatGPT** was used for the first project discussion.
- [Team: add any other tools here.]

---

# Not for pasting: check these before the final submission

These lines in the draft are ahead of what is verified or shipped right now. Fix the product or soften the sentence.

1. **"You can also ask by voice and listen to the answer."** The voice module works live, but the mic and Listen buttons are not in `app.py` yet.
2. **The agent.** It is built and passes its offline tests, but it has not completed a live run, and `app.py` still uses the simple checker. If that is still true at noon, change "we built a bounded agent" to say it ships behind a switch, and do not demo it as the default.
3. **"A golden set that passes in English and Arabic."** This comes from the readme's note on the earlier live run. Rerun it after the merge before repeating the claim.
4. **Languages.** The registry marks the non English languages as drafts not yet reviewed by a native speaker. "What's next" says so, but make sure the app shows its beta notice in the demo.
5. **Voice in other languages.** The audio round trip was verified in English. Arabic, Mandarin, Cantonese and Russian audio has not been checked by a speaker.
6. **Test count.** 189 on the `feature/agent` branch. Update the number if it changes.
7. **Required attachments:** a public GitHub link and a demo video of 3 minutes or less.
