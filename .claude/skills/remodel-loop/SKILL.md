---
name: remodel-loop
description: Run the whole design loop for a house - grill the brief, plan a variant, build its design model, render it, review it with the owner, and repeat until they are satisfied, then merge. Use when someone says "let's design the remodel", "next iteration", "try another option", asks where the project stands or what to do next, or when a variant is ready for review or merging.
---

# The loop

```
scan-house -> existing-plan          once per house
        |
        v
grill-brief -> plan-variant -> design-model -> render-pictures -> review
     ^                                                              |
     +-------------------- not yet satisfied ----------------------+
                                                                    |
                                                         satisfied: merge to main
```

Each box is a skill. This one decides which box is next and keeps the record straight.

## Where are we?

Check, in order, and start at the first thing missing:

1. `uv run pipeline.py check` - is there a project, and an `existing/house.json`? If not: `setup`, `scan-house`, `existing-plan`.
2. `brief/brief.md` - does it exist, and how many lines are still Open? A brief that has not been grilled comes first.
3. `variants/` - which exist, which have plans, a model, renders? Read `variants/README.md` for the comparison table.
4. `brief/decisions.md` - the newest entries say what was last decided and what was asked for next.
5. `git status` and `git branch` - is a variant branch open and unmerged?

Tell the owner in a few lines where things stand and what you will do next, then do it.

## One turn of the loop

1. **Branch.** Each variant, or each round of changes to one, gets a branch: `variant-a-rear-wing-up`, `variant-a-round-2`. Dashes only. `main` holds only what the owner has accepted.
2. **Grill** what this round needs (`grill-brief`). First round: the whole tree. Later rounds: only the branches the last review opened. Update the brief before drawing.
3. **Plan** (`plan-variant`). Fix failed checks. One cost figure.
4. **Design** (`design-model`). Model and IFC built; cutaway matches the plan.
5. **Render** (`render-pictures`). Massing style first so the change is readable; a finish style when the owner wants to see materials; AI pictures only if asked.
6. **Review with the owner.** Lead with the findings, not the process:
   - the one expected-cost figure against the brief's target and ceiling;
   - each Stated line of the brief: met, missed, or cannot tell;
   - failed checks and what they mean;
   - the plan, the street and rear renders, the cutaways;
   - what you would change next, and why.
   Then ask what they think. Their reactions are the input to the next round: new requirements go through `grill-brief` into the brief, choices go through `record-decision`.
7. **Commit** the variant folder with its built files (plans, summary, model, renders) on the branch, so the pictures and the numbers in git always match the `variant.json` beside them. Commit and push only when the owner asks, unless they have said to do so each round.

## Compare before converging

Early on, draw two or three variants that differ in the big move (go up, go back, stay inside the walls), not three versions of one plan. Compare them in one table (`variants/README.md` is rebuilt by `uv run pipeline.py run plans`) and let the owner rule families in or out. Record that as a decision. Then iterate inside the family that is left.

## When is it done?

The owner says so. Offer the question when: no Stated line of the brief is missed without their say-so, no check fails unexplained, the cost is inside the ceiling or they have accepted that it is not, and the last round changed little. Do not declare it finished for them.

## Merge

1. Rebuild everything from the files so nothing is stale: `uv run pipeline.py run plans model ifc`, and the renders that are shown.
2. Record the choice with `record-decision` ("Variant A round 3 is the scheme to take forward"), and mark the brief lines it settles.
3. Open a pull request from the variant branch to `main` describing the variant in the review's terms: cost figure, brief lines met and missed, limits. Merge when the owner approves. Other variants stay in `variants/` as the record of what was tried, or on their branches if never accepted.
4. Say what `main` now holds and what the natural next step is: usually taking the plans, DXF, IFC and brief to an architect.

## Always

- **Planning studies, not designs.** Costs are estimates from stated rates, not bids. Nothing is checked against the zoning code or by an engineer. Say so wherever numbers or drawings are shown.
- **One cost figure** per variant, everything counted in it.
- **State the limits** of the existing-house model in any summary that quotes a dimension.
- **Privacy.** Scans, photographs, the address, names and money stay in the private project. Nothing personal goes to an outside service or a public repo.
- **Automation stays local.** The pipeline and git hooks, not CI services.
