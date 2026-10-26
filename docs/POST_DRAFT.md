# Repu: a Telugu/Tenglish class-group task extractor that never leaves my laptop
*(DEV "Slow and Steady" entry — DRAFT. Replace every [MEASURED] with numbers from `evaluation/reports/`. Delete lines you cannot back up.)*

## The problem
My class group sends hundreds of messages a night: "repu 10 ki DBMS lab record submit cheyyali". (*repu* = tomorrow, *ki* = at, *submit cheyyali* = must submit.) Is "10 ki" 10 AM or 10 PM? Is it for me? Reading all of it is the chore I wanted to hand off — like a sloth, while I rest.

## Why open and local
Class chats contain names and phone numbers of real people. Repu runs an open-weight model (Gemma 3 4B (`gemma3:4b`) through Ollama) on my own machine: no API key, no per-token cost, works offline after the one-time model download. [MEASURED: RAM used / seconds per batch on my laptop]

## The key design decision: the model is not allowed to do date math
The model only copies phrases ("repu", "10 ki") and an exact evidence quote. Plain Python then:
1. checks the quote really exists in the message (`verified_exact` / `verified_normalized`),
2. resolves "repu" relative to the *message's own timestamp* (not import time),
3. refuses to guess AM/PM or ownership — it asks me,
4. exports to `.ics` only tasks where I ticked four boxes (real / mine / deadline correct / approve), re-checked by the backend.
Prompt injection ("ignore all previous instructions…") is treated as data; [MEASURED: injection examples that produced tasks, k/n].

## Results (synthetic, author-written, template-generated set — treat with caution)
- Deterministic resolver on gold phrases: date/time/ambiguity accuracy [MEASURED test: 83/83] — **this only shows my rules agree with my own templates; it says nothing about real chats.**
- Real model pipeline, frozen test split n=110: detection P/R/F1 [MEASURED], evidence verified [MEASURED], false positives on chatter [MEASURED], valid JSON first try [MEASURED]. Wilson 95% intervals are in the report; with n≈110 differences of a few points are noise.
- Failure case I found: [WRITE ONE REAL FAILURE FROM YOUR RUN, e.g. a Telugu-script message the model missed].

## Sloth features (all verified by tests, mocked inference)
- **Morning brief:** a code-built headline plus an optional two-line local-model summary, labelled "AI summary · unverified".
- **Overnight mode:** `python -m backend.app.watch ~/repu-inbox` turns dropped exports into `brief-*.md` files while you sleep. It never creates calendar files.
- **One-tap AM/PM** instead of typing times, and a real batch-by-batch progress bar.

## Limitations
Templated synthetic data, one author, no real chats; images/audio ignored; no fine-tuning done; Telugu quality of a 4B-parameter model is unmeasured beyond the numbers above.

## Where open beat closed
[Only claim what you measured: offline use, zero marginal cost, chats never uploaded.]

Code: [GitHub link]
