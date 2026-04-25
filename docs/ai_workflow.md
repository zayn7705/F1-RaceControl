# AI Workflow: Building RaceControl with Cursor

## Why we used an AI-first workflow

For this project, we intentionally tried to mirror how modern software engineers use AI assistants in real production workflows: move faster on implementation, keep quality high through verification, and stay explicit about requirements.

Our goal was not just to "generate code quickly," but to build a disciplined loop where AI helped with speed while we remained responsible for correctness, design decisions, and final understanding.

## How we worked in practice

### 1) We treated Cursor as a collaborative engineering assistant

We used Cursor for:
- drafting and editing code
- updating docs and tests
- iterating on UI/CLI behavior
- quickly exploring alternative implementations

But we did not treat generated code as automatically correct; it was always reviewed and validated.

### 2) We used a persistent instruction source (`INSTRUCTIONS.md`)

We created and maintained `INSTRUCTIONS.md` so Cursor could reference a stable set of project requirements and constraints while coding.

This acted like a living spec:
- what the project is supposed to do
- what patterns/conventions to follow
- what not to change
- milestone expectations and scope boundaries

That reduced context drift and made sessions more consistent.

### 3) We wrote highly specific prompts

We got the best results when prompts were concrete and constrained (exact file, exact behavior, acceptance criteria, formatting expectations).

We also used external LLMs (including ChatGPT) to improve prompt quality before giving instructions to Cursor. This helped us rewrite vague requests into clearer, implementation-ready prompts with explicit scope and success criteria.

Instead of broad prompts ("make this better"), we used targeted prompts like:
- what to add/remove
- where to modify
- expected output/UX
- how to validate success

This improved first-pass quality and reduced back-and-forth rework.

### 4) We verified functionality after every meaningful change

After Cursor edits, we:
- ran relevant scripts/commands
- checked UI behavior manually
- reviewed outputs/log files
- updated docs to match actual behavior

This ensured the repository stayed runnable and that the final demo reflected real, tested behavior.

### 5) We made sure we understood generated code

A key part of our workflow was reading and understanding code after Cursor wrote it:
- what changed
- why it works
- how it fits existing architecture
- what trade-offs it introduced

That step was necessary for maintainability and confident debugging.

## Benefits we observed

- **Higher implementation speed:** repetitive and boilerplate-heavy tasks were faster.
- **Faster iteration loops:** UI and docs could be adjusted quickly based on feedback.
- **Better momentum:** we could move from idea -> prototype -> validation in shorter cycles.
- **Strong documentation cadence:** it was easier to keep docs aligned with implementation as features evolved.

## Limitations and trade-offs we observed

- **Debugging became harder in some cases:** because we were not always the ones typing every line, root-cause analysis sometimes required extra time to reconstruct intent.
- **Need for stricter review discipline:** AI-generated code can look plausible while still being wrong or incomplete.
- **Risk of shallow understanding if unchecked:** without deliberate code review, it is easy to accept code you do not fully understand.
- **Prompt quality directly affected output quality:** vague prompts produced weaker results and more cleanup work.

## Our operating principle

AI accelerated delivery, but human ownership stayed non-negotiable:
- we set direction,
- we verified behavior,
- we understood the code,
- and we made final engineering decisions.

In short: Cursor was a force multiplier, not a replacement for engineering judgment.
