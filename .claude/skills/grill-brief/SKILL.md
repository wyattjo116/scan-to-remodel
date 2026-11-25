---
name: grill-brief
description: Interview the owner relentlessly about what the remodel must do, until every branch of the brief is settled or knowingly left open, writing the brief, glossary and decisions as you go. Use at the start of a project, before drawing any variant, when the owner says "grill me", when a review of a variant shows the brief is unclear or contradicts itself, or when a new person (partner, architect) brings requirements.
---

# Grill the brief

Adapted for home-remodel briefs from Matt Pocock's `grilling` and `grill-with-docs` skills (MIT; see [CREDITS.md](CREDITS.md)). The method is his: a design tree worked in rounds, a recommended answer with every question, facts looked up and decisions asked. The remodel tree and the three documents are this repo's.

## The method

Interview the owner relentlessly until you reach a shared understanding. Map the brief as a **design tree**: every decision branches into the decisions that hang off it. "Add a second floor" opens stair position, which rooms go up, and what the street sees; "keep it single storey" closes all three and opens lot coverage.

Work the tree in **rounds**. The **frontier** is every decision whose prerequisites are already settled: the questions you can ask now without guessing at answers you have not heard yet. Ask the whole frontier in one round. Number each question and give your recommended answer. Then wait for the answers before the next round.

Format a round like this:

```
❓ **Q1 - <short title>**: <the question, with the choices if there are any, and what each choice costs or rules out>

➡ <your recommended answer, and the one fact or reason behind it>

---

❓ **Q2 - <short title>**: ...

➡ ...
```

Word each question so that "yes" accepts your recommended answer. Keep a round to what a person can answer in one sitting: about five to eight questions. If the frontier is wider, ask the questions that unblock the most first.

Each round the owner answers reshapes the tree: settled decisions push the frontier outward and unblock the questions that depended on them. Recompute the frontier and ask the next round. A question whose answer depends on another question still open in this round belongs to a later round.

**Finding facts is your job, never the owner's.** When a question needs a fact, look it up before asking: room sizes and areas from `existing/summary.json`, what a wall is doing from `existing/house.json`, lot coverage from `project.json`, sun from the latitude and which way the house faces. Do not ask the owner anything the files can tell you. If a fact needs outside research (a zoning limit, a typical cost), say you are checking, carry on with the questions that do not depend on it, and bring the answer to the next round with its source. Never present a zoning or cost figure as confirmed when it was only read or estimated.

**Decisions are the owner's.** Put each one to them and wait. "Not sure yet" is an answer: record it as Open and move on. Do not turn an Open line into a goal by guessing.

**More than one owner.** A household often disagrees. When two people's answers conflict, do not pick: record both, name the conflict as its own question, and put it on the next round.

The session is done when the frontier is empty: every branch visited, each one Stated or knowingly left Open, nothing silently assumed. Do not start drawing variants until the owner confirms the brief reads right.

## The remodel tree

Start at the root and let the answers decide the order. These are branches to visit, not a script to read out.

1. **Why and for whom.** Who lives here, for how long, what is wrong with the house today, what must not be lost. Resale or forever.
2. **Money.** Target, hard ceiling, what the figure includes (construction only, or fees, permits, contingency and finishes too), and what gives way first if it runs over.
3. **Programme.** Rooms and counts; which must be on the ground floor; who needs to be near or far from whom; work from home; guests; storage; laundry; a mudroom. For each room that matters: what happens there on an ordinary day.
4. **Size and massing.** Stay in the footprint, extend, or go up. How visible new work may be from the street. Limits: lot coverage, floor area, height, setbacks (look these up; flag as unconfirmed until the city says so).
5. **The existing house.** What stays untouched, what may be gutted, what has character worth keeping. Known problems: structure, wiring, plumbing, damp.
6. **Arrival and movement.** Which door is the everyday door, where the car goes, what you see when you walk in, paths between kitchen, table, garden and bedrooms.
7. **The main room.** Open, partly divided or separate rooms; where the table is; what the cook sees; noise; television.
8. **Light, heat and outlook.** Which rooms get morning or evening light; overheating; views to keep or block; privacy from neighbours.
9. **Outside.** Porches, garden, trees to keep, parking, bins, a shed.
10. **Character and style.** What the street looks like; fit in or stand apart; materials and colours they like; reference photos (ask for them; they stay out of git).
11. **Systems.** Heating and cooling, all-electric or not, solar, insulation, accessibility now or later.
12. **Process.** Who else decides; when an architect and an engineer come in; whether the household lives there during the work; deadlines.

## Write the documents as you go

After every round, before asking the next, update these in `<project>/brief/`. Do not save it for the end: a session can stop at any time.

**`brief.md`** - the standing brief. One line per requirement, each marked:

- **Stated** - the owner said it. Add the date.
- **Working** - you inferred it from their choices; confirm before relying on it.
- **Open** - asked and not answered, or not asked yet.

Group lines under the tree's headings. When an answer replaces an earlier one, change the line and say what it replaces. Keep the owner's own words where you can. Start from `templates/house/brief/brief.md`.

**`glossary.md`** - the words this household uses, pinned to one meaning each. "The sunroom" is which room in `house.json`? Is "the office" his or hers? Does "budget" include fees? Every time a word turns out to mean two things, settle it and write it down, with the room `id` where there is one. Use these words, and only these, in every later plan and summary.

**`decisions.md`** - numbered, dated, newest first. A decision is recorded when the owner chooses between real alternatives, rules something out, or reverses an earlier choice. Use the `record-decision` skill for the format.

## Rules

- One recommended answer per question, with its reason. A list of options with no recommendation hands the work back to the owner.
- Say plainly when a requirement cannot fit with another one (four bedrooms upstairs inside a height limit, a budget below the programme). That conflict is a question for the next round, not something to smooth over.
- Money, zoning and structure: always say what a figure is (an estimate, a reading of the code, a guess) and who confirms it (a builder, the city, an engineer).
- Personal details stay in the project folder. Nothing from the brief goes to an outside service.
- End each round by saying how much of the tree is settled and what the next round will cover.

Next: the `plan-variant` skill.
