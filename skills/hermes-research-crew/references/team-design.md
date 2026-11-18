# Team design: from answers to a roster

## Model families

The family is the vendor that trained the model. The provider that serves it
(OpenRouter, Nous, a local runtime) does not change the family.

| Family | Typical access in Hermes |
|---|---|
| OpenAI GPT | ChatGPT/Codex subscription (`openai-codex`), OpenAI API, OpenRouter |
| Anthropic Claude | Claude subscription or seat via Claude Code login (`anthropic`), API, OpenRouter |
| Google Gemini | Gemini API, OpenRouter |
| xAI Grok | SuperGrok subscription (`xai-oauth`), xAI API (`xai`) |
| Open-weight (DeepSeek, Qwen, Kimi, GLM, Llama, Mistral, Nemotron) | OpenRouter, Nous, local runtimes. **Each vendor is its own family.** |

Confirm provider ids against `hermes auth add --help` and the Hermes docs; they
change between releases. Do not hard-code model versions in the plan without
checking the provider's live model list.

## Derivation

1. **Access table.** From S3, S4, and S5, list each route: provider/model, family,
   billing (subscription, seat, metered, local, free), and whether it may run
   cards unattended:
   - personal subscription: yes, within the provider's terms;
   - institutional seat: only if S5 = yes;
   - metered: yes, within the S4 budget;
   - local: yes, after it passes the first card. Confirm the local server
     answers (`ollama list` succeeds) and expect the usable context to be
     limited by VRAM. Record the provider id as UNVERIFIED here; the
     `hermes model` picker runs after approval, per step 8 (it writes config);
   - free tier: attended only.
2. **Engineer (Athos).** The route best at long, tool-using coding runs among
   the unattended routes. If there is none, the setup is attended (Small team).
3. **Verifier (Porthos).** The best model from a family that differs from every
   producer's (engineer, writer, creative, and the orchestrator for anything it
   writes). If no second family exists, choose between a local open-weight model,
   a small metered budget for one, or a labelled same-family review. Put that
   choice to the user. **Independence needs competence too:** a small local
   model (under about 30B parameters) is labelled "weak check" in the plan, and
   the first card plants one known error. A verifier that misses it does not
   count as a verifier; fall back to a labelled same-family review or ask for a
   budget. If the only second family is attended-only and S4 allows spending,
   offer a metered open-weight verifier for unattended checks as an option.
   **The orchestrator is a producer too:** artifacts the orchestrator writes
   itself are independently checked only if the verifier's family differs from
   the orchestrator's. Say so in the independence statement.
4. **Writer (Aramis).** The route that writes the best prose and keeps claims
   and numbers intact. It may share the engineer's family, because the verifier
   stays independent.
5. **Creative (Bazin), if S8 asks for it.** A route with vision input that can
   render and look at what it made. Otherwise the writer takes occasional
   figures.
6. **Hygiene (Planchet), if S8 asks for it.** Careful, literal instruction
   following matters more than raw capability; a mid-tier paid route is enough.
   No free tier, because it deletes files unattended. It may share any family.
7. **Orchestrator (d'Artagnan, `default`).** The route the user is happy to chat
   with all day. It makes the most calls, so prefer a route whose cost does not
   grow per call (a flat-rate seat or a local model) or set a spend cap. Set its
   `delegation.provider` and `delegation.model` to a cheap route for read-only
   fan-out; children inherit those, not a specialist's seat.
8. **Exact model ids.** Write candidate ids in the plan marked `UNVERIFIED`
   (provider docs, the user's knowledge, or a previous install). Do **not** run
   the `hermes model` picker during planning: selecting a model writes config,
   which Rule zero forbids before approval. After approval, in Build, run the
   picker with the user to choose the real ids, then Prove validates them before
   the first card. Fallback candidates are likewise named in the plan and chosen
   by a timed probe in Prove.
9. **Fallbacks.** Use the table below.
10. **Turn caps.** Write one `agent.max_turns` number per desk. Defaults:
    orchestrator 60, engineer 75, verifier 100 (checks run long), writer 60,
    creative 60, hygiene 40.
11. **Audit the plan** against SKILL.md constraints 1-6 and the hard limits in
    `intake.md`. List every violation as an explicit caveat the user accepts, or
    change the plan.

`architecture.md` §6 lists the rest of each desk's settings (tools, skills,
usual ending).

## Fallback policy

| Desk | Works cards unattended? | Fallback |
|---|---|---|
| Orchestrator | no (interactive) | A fast free or cheap model is acceptable; a human sees every answer. |
| Engineer, writer, creative, hygiene | yes | None (the card blocks), or a same-tier paid route. Never a free tier. |
| Verifier | yes | None, or a route outside every producer's family. |

Pick a fallback by a timed one-call probe, never by name. Free model ids fail as
403 (gated), 404 (retired), 429 (rate-capped), or a long silence, and only a
probe tells them apart.

## Choosing routes by capability, not brand

Match each desk to what it needs (`architecture.md` §4), then pick the
cheapest route the user has that meets it. There is no default ranking of
billing types.

| Billing | Strengths | Watch for |
|---|---|---|
| Subscription or seat | cost does not grow per call; strong closed models | usage windows shared by every desk on it; provider and institution terms |
| Metered open-weight (DeepSeek, Qwen, Kimi, GLM, ...) | low cost per call; easy second family for the verifier; pinnable versions | tool-use reliability varies by model; set a spend cap at the provider |
| Metered closed (vendor APIs) | strongest models without a subscription | cost on long unattended runs |
| Local | private; no per-call cost | hardware limits context and speed; prove it on the first card |
| Free tier | learning, attended experiments | never on a desk that runs cards unattended |

Mixed teams are normal: for example, the orchestrator on a subscription the
user already has, the engineer and verifier on capped metered open-weight
routes from two different vendors. Whether a cheaper route is good enough is an
empirical question about the user's own tasks; the next section shows how to
answer it.

## Comparing models on your own work

Do not claim a cheaper model is equivalent, or that a premium one is required,
without trying it. A small, fair comparison:

1. Pick three to five representative past cards with clear acceptance criteria.
2. Change **one desk's route at a time**. Keep the card body, the starting
   files (a fresh worktree from the same commit), the tools, the skills and the
   verifier fixed.
3. For each run record: accepted by the verifier (yes/no), your minutes of
   intervention or rework, retries, elapsed time, the route actually served
   (from `agent.log`), and the cost.
4. Compare **cost and human time per accepted result**, not price per token.
   Write down how it felt to work with too, in its own column; it is a real
   cost, just not the same measurement.

A route that wins on your cards is good evidence for you, not a general ranking.

## Institutional and EDU seats

Tell the user, in your own words:

> Your institution owns this seat. Many institutions allow personal interactive
> use but restrict automation or third-party tools, and some providers' terms
> limit subscription logins in third-party harnesses. I can use it while you are
> present. Before cards run on it unattended, please confirm both sets of terms.

Record the S5 answer in the plan. Until it is "yes":

- the seat's profile gets no unattended board dispatch;
- mark it `attended-only` in `PROFILES.md`;
- the orchestrator may still use it interactively.

**Mechanism.** Two cases.

- **Attended mode** (Small team, a 'Not yet' override, or any hard limit 1-3 in
  force): no background dispatcher at all. Set
  `hermes config set kanban.dispatch_in_gateway false` and do not run
  `hermes kanban daemon`. While the user is present, the orchestrator runs
  `hermes kanban --board <b> dispatch --max 1`, which starts a card only when
  none is already running on that board.
- **Attended-only profiles in an otherwise unattended team:** create their root
  cards already parked with `hermes kanban --board <b> create "<title>"
  --assignee <p> --initial-status blocked ...`, which leaves no window for the
  dispatcher. A chained card (`--parent`) waits in `todo` until its parent
  finishes, so park it right after creating it with `hermes kanban schedule <id>`.
  Release either kind with `hermes kanban unblock <id>` while the user is
  present. If a released card blocks again, check whether auto-decomposition
  fired (`running-the-board.md`).

Verify before leaving it overnight: `hermes kanban --board <b> list` must show no
`ready` card assigned to an attended-only profile. On first setup, create and
park the cards **before** installing or starting the dispatcher, run this check,
then start it.

**One subscription shared by several desks** hits its usage window fast. Cap
concurrency at the right level:

- one board: `--max 1` on `dispatch` or `daemon` counts cards already running
  on that board, so it is a per-board cap (the installed help text describes it
  as per pass; the dispatcher source counts running cards);
- all boards: `hermes config set kanban.max_in_progress 1` in the profile that
  dispatches counts running cards across every board.

Chaining cards (`--parent`) instead of fanning out also helps.

Personal subscriptions have terms too: some providers restrict using a consumer
login through third-party tools. The plan's approval line includes the user's
acknowledgement that checking provider and institution terms is their
responsibility.

## Worked examples

**A. One subscription, $0.** PhD student; ChatGPT/Codex subscription; one
large codebase and a paper.
- Orchestrator, engineer, writer: `openai-codex`.
- Verifier: no second family at $0. Offer three options: a local open-weight model
  (if S10 shows the hardware), about $5-10/month metered for an open-weight
  verifier, or a labelled same-family review.
- Verdict: Full team with a caveat (long tasks), or Small team. Lock: paper
  numbers come from pinned code and models, never from a chat seat.

**B. Institutional seat (terms unconfirmed) plus a personal subscription.**
Claude seat through the university; personal Codex subscription; $20 budget.
- Engineer: `openai-codex` (unattended allowed).
- Writer and orchestrator: the Claude seat, interactively.
- Verifier: always a family other than the artifact's producer, pinned per card
  with `hermes kanban --board <b> set-model <id> <model> --provider <p>`.
  Engineer (GPT) artifacts are checked on the Claude seat while the user is
  present, or unattended on an open-weight route inside the $20. Writer and
  orchestrator (Claude) artifacts are checked on `openai-codex`. Checking a
  Claude-written artifact on the Claude seat would be a same-family review and
  must be labelled so.

**C. API keys only, $100.** Tool-builder.
- Engineer: a strong open-weight coder, metered.
- Verifier: a closed model from another vendor, metered.
- Writer: the engineer's route or a prose-strong model. Orchestrator: a cheap
  route.
- Set provider-side spend caps; with metered routes a runaway card has a cost.

**D. No subscriptions, $30, simulations overnight.** Economist running Monte
Carlo studies.
- Orchestrator and engineer: one capped metered open-weight vendor.
- Verifier: an open-weight model from a different vendor.
- Hygiene: the cheapest paid route that follows instructions well; daily
  no-agent scan, weekly card, because overnight runs leave per-seed output.
- Before trusting the setup, run the comparison above on three past cards.
