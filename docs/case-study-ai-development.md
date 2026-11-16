# AI-development case study

BatchLens was written by a coding agent (Claude Code) under written rules, directed by one
person with biopharmaceutical manufacturing and software experience. This is an account of
how that went, including where it went wrong. Every count below can be checked in the
repository's history, [devlog.md](devlog.md) and [gaps.md](gaps.md). No productivity or
accuracy claim is made that was not measured.

## The setup

- **A plan, handed over once.** The owner wrote a kickoff document: what BatchLens is, phases
  with a "done when" each, architecture decisions already made, facts marked as verified
  against the template and platform at named commits, things approved in advance, things to
  stop and ask about, and things out of scope. One instruction carried the rest: when the code
  disagrees with this document, the code wins; say so and continue.
- **Rules that outlive the plan** ([`AGENTS.md`](../AGENTS.md)). The platform's rules, then the
  project's: synthetic data only; four things that are not each other (batch and asset, phase
  execution and recipe, assay result and online sample, collection time and availability
  time); no look-ahead; units explicit; ground truth kept out of the app; formulas only in a
  standard-library package, each with a hand-calculated oracle test; prefer `insufficient` to a
  number that is not supported; never claim validation.
- **A trail.** Each working step ends with an entry in the devlog: what was planned, the
  decisions made where the plan was silent ("rulings"), what failed and how it was resolved,
  and the measured check results.

The domain rules did the most work. An agent asked for "IVCD" will produce a trapezoid; the
rules are what made it reject a wrong unit instead of converting it, refuse a gap instead of
bridging it, and keep a result's availability time separate from its sample's collection time.

## What the agent was not allowed to decide

Five decisions went to the owner, each asked as a question with options and a recommendation:

| Question | Why it was the owner's |
|---|---|
| Delete a template test that cannot pass after the template's own rename step? | Removing a test |
| Add two charting packages the interface library needs? | A new dependency |
| A private or a public repository? | Publication |
| What counts as a batch "diverging" from the reference? | A scientific choice |
| A recovery finding on one step or both? | A scientific choice |

Everything else the agent decided and wrote down. There are about thirty such rulings in the
devlog, for example: harvest mass uses the last titer sample collected in the phase and waits
for it rather than falling back to an older one; "volume at the sample's time" is the last
online value at or before it, at most fifteen minutes old, never a later one.

## What testing first did and did not catch

Tests were written before the code and run to see them fail. The record is honest about
exceptions: the first batch of calculation tests was written together with the code and never
seen red (it was checked afterwards by breaking a formula and watching seven tests fail), and
once a design changed mid-step and tests and code were rewritten together.

What the tests caught that reading would not have:

- The trend for the badly recorded batch drew twelve hours of values that were never
  recorded, because the platform's stepped means hold the last value across a gap. A test
  written for the new batch failed, and the trend code was changed.
- A boundary test at "exactly the tolerance" failed because 2.0 - 1.7 is not 0.3 in floating
  point. The test was changed to values a float holds exactly; no margin was added to the code.
- An `as_of` parsed by the web framework turned the text `12` into twelve seconds after 1970.

What they did not catch:

- **The test double cannot show what it does not model.** Against a real PlantCraft, the
  synthetic bioreactor's data landed three hours off, silently, because of how the platform
  reads CSV times. The symptom was a 3 g difference in one metric between the fake and the
  real system. It was found because the agent compared the two and did not accept "close".
- **An independent review** by a second agent with no knowledge of the first one's reasoning
  found a path to a server error that 118 passing tests had missed: a valid `as_of` whose
  offset pushes it outside representable time. A second review, of the unattended night's
  work, found that loading a stale demo batch again could undo a person's correction while
  still marking the sample corrected, and leave two reference batches. 215 tests were
  passing at the time.

## A night without the owner

The first slice was built with the owner present. The rest (the remaining findings, the badly
recorded batch, the benchmark, packaging, the as-of slider, editing, the purification train
and the assistant's tools) was built in one unattended stretch, under one instruction: proceed
on your own judgment, merge each pull request when its checks pass, stop at a set time. Each
item was its own branch and pull request with a devlog entry; nine were merged that night.

What held up without supervision was what had been written down beforehand: the domain rules,
the test-first habit, the list of decisions that were not the agent's, and looking at the
rendered page before calling a step done. Three of the night's fixes came from that last one
(an as-of view that named samples not yet taken, phase ends that had not happened, and a demo
database left stale by a change to the seeding rule). One decision was deliberately not taken:
making the repository public, which is the owner's.

## The day after, with the owner watching

The owner then opened the demo from another machine and steered for a day. What that found
says more than the night's test counts:

- **The app looked empty.** The owner's first report: "There is nothing to do or see except a
  page listing batches." The batch ids were links drawn as plain text. 225 tests passed,
  eight of them in a browser, and each clicked the link by its name; none asked whether a
  person could tell it was one.
- **The switcher did nothing.** Served to another machine, the app sat at a different origin
  from the platform and its entry in the app switcher was dead. Every earlier check had
  opened the app by its address.
- **A rule that held.** The owner asked for the name "PlantCraft BatchLens". The platform's
  own check refuses that name for an app outside the suite, and its trademark notice asks
  first. The agent did not work around the check; it said so and offered the form the check
  accepts.
- **Too many disclaimers.** The owner asked why "synthetic" and "non-GxP" were everywhere.
  The rule said never to let the demo be mistaken for a validated system; the agent had
  applied it to every line instead of once where it cannot be missed.
- **A direction the plan did not have.** Running the suite's modules beside the app showed
  that five finished batches gave them nothing to show. The owner chose a live plant; the
  agent built it by reusing the as-of filter and recorded the price in the gaps.

## Where the agent got it wrong

- **Edit scripts that silently did less than they said.** Four times a scripted edit stopped
  at a text match that did not exist. After the fourth, edits went through a small helper
  that checks every match in a file before writing any of it and names a file it did not
  change; the problem did not recur. Once this was after a commit and a pull request, so
  half the documents arrived in a second commit. The tests staying red caught the code cases;
  nothing caught the documentation case until the next step read the files.
- **A wrong first design for the time zone problem**, built and tested before the real cause
  was found (a separate source file to protect a setting that turned out to have no effect).
  It was removed.
- **A screenshot checked too late.** A display rule (a difference shown with more digits than
  the values beside it) was only noticed when looking at the rendered page.
- **Process slips**: a command that hung on standard input; stale bytecode after two edits in
  one second; killing its own shell while stopping servers.

None of these reached `main` as wrong behaviour, as far as the tests and the review can tell.
They cost time, and they are listed because a trail that only records successes is not
evidence of anything.

## What was measured

| | |
|---|---|
| Python tests | 236 passing |
| Interface tests | 29 passing |
| Browser journeys | 8 passing |
| Benchmark | 380 seeded batches, 1,900 comparisons, a few seconds |
| Pull requests | 21 merged; each of the first 13 with its own devlog entry, the later ones grouped |
| Independent reviews | Two. First slice: 1 important finding and 4 minor (important fixed, 1 minor fixed since, 3 open). The night's work: 1 important and 7 minor, all fixed, each with a failing test first |
| Decisions taken to the owner | 5 in the first slice and the night, then the owner present for the rest; publication is the owner's |
| Known gaps written down | 54, each with a state ([gaps.md](gaps.md)) |

Not measured: how long the same work would have taken without an agent, or with an agent and
no domain rules. An experiment comparing an agent with and without the bioprocess rules on the
same task was proposed in the project's original notes and has not been run.

## What seems to matter

- **Rules about the domain, not about style.** "Collection time is not availability time" is
  one sentence and shaped every route.
- **A plan that says what was verified and when**, and that the code wins when they disagree.
  Three of its "verified" facts turned out to be half true; none of them stopped the work.
- **A short list of decisions the agent may not take**, and questions asked with a
  recommendation.
- **A real system, early.** The two most serious problems were invisible against the test
  double.
- **A second reader with no stake in the first one's reasoning.**
- **Writing down what failed**, at the time, in the same place as what passed.
