# Intake

The intake turns an open request ("set me up") into a plan the user approved.
Fill decision **slots**, not a fixed script. Probe first, ask only what the probe
could not answer, and phrase each question for this user, in plain words.

## Mechanics

- Use the `clarify` tool when present: up to 5 questions per call, up to 4
  choices each. Put the probe-consistent (recommended) choice first; the UI adds
  an "Other" row by itself. Choices go in `choices`, never in the question text.
  For free-text values (folder paths, provider names), omit `choices` to ask an
  open question.
- Without `clarify` (one-shot runs, messaging platforms), ask the same round as a
  numbered list in chat and wait. A Kanban card worker never runs the intake; it
  belongs to an interactive session.
- At most three rounds. A round is one topic group: its follow-ups (the
  restricted-data question, round 2b) belong to it. Aim for six `clarify` calls
  or fewer in total. Independent questions share a call.
- **The intake may end after round 1** when the verdict is Single profile or Not
  yet and the user accepts it. Otherwise the verdict becomes final after round 2.
- A skip or timeout on S3, S5, or S6 stops the intake. Report what is missing.
  Do not guess providers, institutional terms, or data restrictions.
- Record every answer and every probed fact in the plan's Intake section, with
  its source: `probe`, `user`, `default`, or `assumed`.

## Step 1: probe (read-only)

```bash
hermes --version
hermes profile list                                   # existing profiles: S1 branch
hermes auth list | awk '/^[a-z0-9-]+ \(/{print $1}'    # provider names ONLY; labels can be emails
hermes kanban boards list
hermes config get kanban.dispatch_in_gateway; hermes gateway status   # how cards would be dispatched
uname -s; for t in git gh uv docker ollama; do command -v $t >/dev/null && echo "$t ok"; done
gh auth status >/dev/null 2>&1 && echo "gh logged in"
command -v ollama >/dev/null && ollama list                 # local models already pulled
command -v nvidia-smi >/dev/null && nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
```

Exact model ids come later, with the user, from `hermes model` (an interactive
picker that reads each provider's live model list). See `team-design.md`
step 6.

A provider in `hermes auth list` is a credential, not an entitlement. It may be
exhausted, metered, a free tier, or an institutional seat. Billing type and
permission come from the user (S3, S5).

## Decision slots

| ID | Slot | Decides | Probe? |
|---|---|---|---|
| S1 | Goal: fresh start, consolidate an existing install, add a team to a working install, or just evaluating | branch | partly (profile count) |
| S2 | Work shape: active projects per month; kinds of work (analysis code, tools, writing, design, data) | fit, roster | no |
| S3 | Model access: each provider's family and billing type (personal subscription, institutional seat, metered with credit, local, free tier) | routes, independence | partly |
| S4 | Monthly metered budget | metered routes, paid fallbacks | no |
| S5 | Which provider is an institutional seat, and does the institution permit agent automation on it? | unattended dispatch | **never infer** |
| S6 | Publication stakes, and licensed / restricted / human-subjects data | locks, data handling | no |
| S7 | Review habit: reviews results, approves each card, or will not review | fit, dispatch | no |
| S8 | Desks: builder, checker, voice (prose or design), data | roster | no |
| S9 | Workspace: where projects live; projects without a remote | registry, backup | partly |
| S10 | Platform: OS, laptop or always-on machine, local GPU/RAM, notification channel | overnight runs, local checker | partly |

## Round 1: is it worth it? (S1, S2, S6, S7)

```json
{"questions": [
  {"question": "What do you want from this setup?",
   "choices": ["Start fresh: a small agent team for my projects", "Clean up a Hermes install I already have",
               "Add a team to a setup that already works", "Just tell me whether it's worth it"]},
  {"question": "How many projects do you actively work on in a typical month?",
   "choices": ["2-4", "5 or more", "1"]},
  {"question": "What do you need agents to do?", "multi_select": true,
   "choices": ["Analysis code and scripts", "Build tools or software", "Write papers or docs", "Figures, slides, design"]},
  {"question": "Does any project involve the following?", "multi_select": true,
   "choices": ["Results I intend to publish", "Licensed, restricted, or human-subjects data", "Neither", "Not sure yet"]},
  {"question": "How will you work with what the agents produce?",
   "choices": ["Agents work while I'm away; I review results", "I approve each task before the next starts",
               "Agents handle routine tasks alone; I review the rest", "I don't want to review anything"]}
]}
```

Reorder by the probe: with eight existing profiles, put "Clean up" first.

How the last answer maps:

- "Work while I'm away; I review results": unattended dispatch allowed.
- "Approve each task": attended mode (no background dispatcher).
- "Routine tasks alone": routine cards run unattended; every other card is
  created parked. A routine task is checked mechanically (tests pass, a file
  builds) and touches no published result and no restricted data.
- "I don't want to review anything" means the user will not read checker blocks
  or a morning queue. That is verdict row 1. Agreeing to read the queue, even
  briefly, changes it.

If restricted data was selected, ask one follow-up before the verdict, then
record the answer as a project lock (see `projects-and-cards.md`):

```json
{"questions": [{"question": "How may agents work with the restricted data?",
  "choices": ["Agents write code against fake or sample data; only my own scripts touch the real data",
              "A local model may read the real data; hosted models may not",
              "My data agreement allows hosted AI tools (I've checked)"]}]}
```

## Fit verdict

Walk the table **top to bottom; the first matching row wins.** Give the verdict in
two or three plain sentences with the reason.

| # | Verdict | When | What to offer |
|---|---|---|---|
| 1 | **Not yet** | The user will not review output, or has no usable model access | Explain what would change the answer (agreeing to review blocks; one working route). Offer a single attended profile meanwhile. |
| 2 | **Single profile** | 1 project, no publication stakes, no restricted data | One profile, attended, with good skills. Use the short plan form. |
| 3 | **Small team** | 1 project with stakes; or only free-tier models; or no route may run unattended | PM + checker in attended mode: the PM (with the user) does the work, and checks run only while the user is present. |
| 4 | **Full team** | Everything else: 2+ projects, at least one route allowed to run unattended | PM + builder + checker + voice. If the checker's only route is attended-only, say "Full team, attended checks": builders run unattended, checks wait for the user. |

After round 1 the verdict is provisional; round 2 can move it down the table,
never up past row 1 or 2 conditions. Local models count as able to run cards
unattended only after they pass the first card (`team-design.md`).

### Overrides

The user may override any verdict with the reasons on record. Then:

- build the roster they asked for, using the full plan form;
- an informed override beats constraint 10 (smallest team), which is guidance;
- if any of hard limits 1-3 applies, the whole setup runs in **attended mode**
  (no background dispatcher). Say so before they approve;
- a pushback reopens only the questions whose answers changed, not the intake.

### Hard limits: these survive any override

The user may override a verdict (record it). These five limits still hold, and
the agent says so plainly:

1. No unattended dispatch to a free-tier route.
2. No unattended dispatch to a seat marked attended-only.
3. No unattended pipeline for a user who will not review blocks.
4. Restricted data is handled exactly as the user's answer above says.
5. With publication stakes, the reproducibility lock is on every card for that project.

## Round 2: resources (S3, S4, S5)

Ask only what the probe left open.

```json
{"questions": [
  {"question": "Which model access do you have?", "multi_select": true,
   "choices": ["Subscriptions: personal (ChatGPT/Codex, Claude, SuperGrok, Gemini) or an institutional/EDU seat",
               "Pay-per-token API keys with credit (OpenRouter, Nous, a vendor API)",
               "Free-tier models (for example OpenRouter :free)", "Local models (Ollama, llama.cpp)"]},
  {"question": "How much can you spend per month on pay-per-token usage?",
   "choices": ["$0", "Up to $10", "Up to $50", "More, with a hard cap I set at the provider"]}
]}
```

If subscriptions were named, ask round 2b. Build the first question's choices
from the probed provider **names** (never labels), plus "None of them":

```json
{"questions": [
  {"question": "Is any of these an institutional or EDU seat?", "choices": ["<provider-a>", "<provider-b>", "None of them"]},
  {"question": "Does your institution allow automated agent use of that seat?",
   "choices": ["Not sure: use it only while I'm present", "Yes, I've checked the terms", "No"]}
]}
```

Drop the second question when the answer to the first is "None of them".

- "Not sure" goes first because it is the safe default.
- If the answers name categories but not vendors, ask one open question: "Which
  subscriptions or providers, by name?" Map names to families with
  `team-design.md`.
- For each route the plan needs, confirm a credential in `hermes auth list`. If
  one is missing, the plan gets a step where the **user** runs `hermes auth add
  <provider>`.

## Round 3: working style (only unknowns among S8, S9, S10)

- Voice desk: mostly prose (`writer`) or mostly figures and slides (`creative`)?
- Where do projects live? (open question) Do any lack a git remote?
- Will tasks run overnight on a laptop, or on a machine that stays on?
- A notification channel (for example Telegram) for blocked tasks?
- Enough local GPU/RAM for an open-weight checker? (Only if S3 lacks a second family.)

## Writing the plan

1. Fill `templates/setup-plan.md` with `team-design.md`. For Single profile or
   Small team use the short form.
2. Show the whole plan, starting with its plain-language summary.
3. Ask the insurance question: keep the full backup archive forever, or
   auto-delete after N days (default 14, a cron job the PM may install)? The
   answer goes in plan section 9.
4. Ask one question: **Approve**, **Change something**, or **Stop**.

The `hermes model` picker is not part of planning: selecting a model writes
config, so ids are written `UNVERIFIED` in the plan and chosen after approval.
4. Build only on Approve. On Change, edit and ask again.
