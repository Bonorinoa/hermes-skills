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
     answers (`ollama list` succeeds), take the provider id Hermes shows for it
     in `hermes model`, and expect the usable context to be limited by VRAM;
   - free tier: attended only.
2. **Builder (Athos).** The strongest coding model among the unattended routes.
   If there is none, the setup is attended (Small team).
3. **Checker (Porthos).** The best model from a family that is neither the
   builder's nor the voice's. If no second family exists, choose between a local
   open-weight model, a small metered budget for one, or a labelled same-family
   review. Put that choice to the user. **Independence needs competence too:** a
   small local model (under about 30B parameters) is labelled "weak check" in the
   plan, and the first card plants one known error. A checker that misses it does
   not count as a checker; fall back to a labelled same-family review or ask for a
   budget. If the only second family is attended-only and S4 allows spending,
   offer a metered open-weight checker for unattended checks as an option.
   **The PM is a producer too:** artifacts the PM writes itself are independently
   checked only if the checker's family differs from the PM's. Say so in the
   independence statement.
4. **Voice (Aramis).** The best prose model (`writer`) or design-capable model
   (`creative`). It may share the builder's family, because the checker stays
   independent.
5. **PM (d'Artagnan, `default`).** The route the user is happy to chat with all
   day. Prefer a flat-rate route, because the PM makes the most calls. Set its
   `delegation.provider` and `delegation.model` to a cheap route for read-only
   fan-out; children inherit those, not a specialist's seat.
6. **Exact model ids.** Choose them with the user in `hermes model` (an
   interactive picker over each provider's live list; `--refresh` re-fetches).
   If that is not possible in this session, write the ids marked `UNVERIFIED`.
   The plan may be approved with them, but step 6 (Prove) must pass before the
   first card. Fallback candidates are likewise named in the plan and chosen by
   a timed probe in step 6.
7. **Fallbacks.** Use the table below.
8. **Turn caps.** Write one `agent.max_turns` number per role. Defaults: PM 60,
   builder 75, checker 100 (checks run long), voice 60.
9. **Audit the plan** against SKILL.md constraints 1-6 and the hard limits in
   `intake.md`. List every violation as an explicit caveat the user accepts, or
   change the plan.

## Fallback policy

| Role | Works cards unattended? | Fallback |
|---|---|---|
| PM | no (interactive) | A fast free or cheap model is acceptable; a human sees every answer. |
| Builder | yes | None (the card blocks), or a same-tier paid route. Never a free tier. |
| Voice | yes | None, or a same-tier paid route. Never a free tier. |
| Checker | yes | None, or a route outside every producer's family. |

Pick a fallback by a timed one-call probe, never by name. Free model ids fail as
403 (gated), 404 (retired), 429 (rate-capped), or a long silence, and only a
probe tells them apart.

## Cost tiers

| Tier | Access | Good for | Limits |
|---|---|---|---|
| 0 Free/local | free tiers, local models | learning, attended experiments | rate limits, weaker tool use; no unattended cards on free tiers |
| 1 Flat-rate | personal subscriptions; institutional seats where permitted | the whole team | usage windows; seat terms |
| 2 Metered | API keys | filling gaps, often the checker's second family | set a spend cap at the provider, not only in your head |

The cheapest full team is usually two flat-rate subscriptions from different
families: PM, builder, and voice on one, the checker on the other. With one
subscription, put the checker on a cheap metered open-weight model from another
family, inside a small capped budget.

## Institutional and EDU seats

Tell the user, in your own words:

> Your institution owns this seat. Many institutions allow personal interactive
> use but restrict automation or third-party tools, and some providers' terms
> limit subscription logins in third-party harnesses. I can use it while you are
> present. Before cards run on it unattended, please confirm both sets of terms.

Record the S5 answer in the plan. Until it is "yes":

- the seat's profile gets no unattended board dispatch;
- mark it `attended-only` in `PROFILES.md`;
- the PM may still use it interactively.

**Mechanism.** Two cases.

- **Attended mode** (Small team, a 'Not yet' override, or any hard limit 1-3 in
  force): no background dispatcher at all. Set
  `hermes config set kanban.dispatch_in_gateway false` and do not run
  `hermes kanban daemon`. While the user is present, the PM runs
  `hermes kanban --board <b> dispatch --max 1` to start one ready card at a time.
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
concurrency: chain cards instead of fanning out, or dispatch with
`hermes kanban daemon --max 1` instead of gateway dispatch.

Personal subscriptions have terms too: some providers restrict using a consumer
login through third-party tools. The plan's approval line includes the user's
acknowledgement that checking provider and institution terms is their
responsibility.

## Worked examples

**A. One subscription, $0.** PhD student; ChatGPT/Codex subscription; three
projects, one heading to a paper.
- PM, builder, voice: `openai-codex`.
- Checker: no second family at $0. Offer three options: a local open-weight model
  (if S10 shows the hardware), about $5-10/month metered for an open-weight
  checker, or a labelled same-family review.
- Verdict: Full team with a caveat, or Small team. Lock: paper numbers come from
  pinned code and models, never from a chat seat.

**B. Institutional seat (terms unconfirmed) plus a personal subscription.**
Claude seat through the university; personal Codex subscription; $20 budget.
- Builder: `openai-codex` (unattended allowed).
- Checker: the Claude seat is a second family but attended-only, so checks run
  while the user is present. For unattended checks, an open-weight route inside
  the $20.
- Voice and PM: the Claude seat, interactively.

**C. API keys only, $100.** Tool-builder.
- Builder: a strong open-weight coder, metered.
- Checker: a closed model from another vendor, metered.
- Voice: the builder's route or a prose-strong model. PM: a cheap route.
- Set provider-side spend caps; with metered routes a runaway card has a cost.
