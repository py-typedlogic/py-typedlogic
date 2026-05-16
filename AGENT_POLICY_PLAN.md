# Agent Policy & Capability Framework — Design Plan

> **Status:** Draft. Output of a brainstorm session, May 2026. Intended to be lifted into a new, separate (private) repository for prototyping.
>
> **Audience:** the next session/maintainer picking this up. Read TL;DR first; the rest is supporting material.

---

## TL;DR — the crystal-clear plan

Build a **three-layer agent guardrail framework**, distinct from but able to reuse parts of py-typedlogic:

1. **Runtime hook layer** (must-have, ships first)
   - User-owned data in **DuckDB tables** (and/or Prolog facts) — e.g. `allowed_emails`, `spend_caps`.
   - Policies as **SQL queries and/or Prolog rules** that consult that data.
   - Tools wrapped with an `@enforced` decorator; rules attached via `@policy_for(tool)`.
   - At each tool call the relevant rules are evaluated; failures raise `PolicyDenied`.

2. **AST capability check** on agent-written ad-hoc Python (must-have for any system where the agent writes code on the fly)
   - A **restricted Python subset** (Starlark-style discipline) that statically guarantees: *the only paths to side-effects are the declared, decorated tools*.
   - Whitelisted imports and call targets; no `eval`/`exec`/`compile`/`subprocess`/`socket`/dynamic `getattr`/etc.
   - Sole job: make the runtime hook boundary **exhaustive**. Without it, `@enforced send_email` is one `subprocess.run` away from irrelevance.

3. **Modular contracts on workflows** (optional, second tier — for reusable utility functions)
   - A function (e.g. a workflow `my_super_workflow(user, ...)`) declares a `@guarantees(...)` contract about its own behavior ("every `send_email` call inside me uses `user` as recipient").
   - Verification is tiered: alias / dataflow analysis → refinement types → SMT → (rare) Lean-style proof.
   - Earns its keep for **reusable libraries / shared workflows / certified utilities**, not one-shot agent scripts.

The first two layers compose to a complete useful product. The third is added when users need it.

---

## Origin

This plan came from a brainstorm exploring "an agent language easy for humans to check and with deterministic checks." Initial framing was open-ended ("Lean-but-less-geeky"). Through iterative narrowing — driven by skeptical use-case questioning — it converged on the much smaller, more honest product above.

The narrowing is itself a finding worth preserving: most ambitious "new agent language" proposals collapse into "tool hooks plus a policy DSL plus a sandbox" once pressed. The work is then in doing those three things well, not in inventing a new logical foundation.

---

## The convergent design — details

### Layer 1 — Runtime policy hooks over user-owned data

The 80% case. Inspired by Cedar / OPA / Claude Code's PreToolUse hooks, but specialized for ergonomic per-session policies driven by user-curated data.

```
data/
  allowed_emails.csv          # editable in any spreadsheet; loaded into DuckDB
  team_members.csv
  spend_caps.csv
rules/
  email.sql                   # SELECT 1 FROM allowed_emails WHERE addr = :address
  spend.pl                    # spendable(Amt, U) :- daily_spent(U, S), Amt + S < cap(U).
tools.py
  @enforced(rules=["email.sql", "spend.pl"])
  def send_email(address, title, content): ...
```

Concretely:

```python
# session.policy — hot-reloadable, human-owned
@policy_for(send_email)
def recipient_policy(address, title, content):
    if address not in load_allowlist():
        raise PolicyDenied(f"{address} not on allowlist")
    if today() > campaign_deadline():
        raise PolicyDenied("campaign closed")

# trusted tool — wraps an external CLI / API
@enforced
def send_email(address: EmailAddress, title: Text, content: Text) -> None:
    gog_cli.send(address, title, content)
```

Properties:
- **Soundness is trivial** — the function itself enforces; no analysis required.
- **Composability** — policies stack by decorator.
- **Hot-reload** — rules file changes apply immediately, no code change.
- **Per-run flexibility** — sessions can swap rule files.
- **Audit/explain** — same rule used for runtime enforcement and post-hoc "why was this denied?" (Prolog gives proof trees for free; SQL gives the matching row).

**Why both DuckDB and Prolog as fact backends?** They cover different ergonomic niches:
- **DuckDB** wins for human curation (spreadsheet ↔ CSV ↔ DuckDB), time-windowed queries, joins, scale, browseable tooling (Harlequin, DBeaver).
- **Prolog** wins for recursion / transitive closure ("reports-to chain", "ancestor of group G"), pattern matching, explanation via proof trees.

Support both as fact sources; the policy engine queries whichever is referenced.

### Layer 2 — Restricted Python subset + AST capability check

The reason this layer exists: **the runtime hook boundary is only effective if it's exhaustive.** If the agent can write `import subprocess; subprocess.run(["gog", ...])`, the `@enforced send_email` wrapper is bypassed. Capability isolation is the prerequisite that makes runtime hooks sound.

Design lineage: **Starlark** (Google/Bazel) already proved that a deterministic Python subset is engineering-tractable. We specialize it: "no I/O *except* through declared tools."

The check is *small* — a few hundred lines of AST walking:
- Whitelisted imports (no `os`, `subprocess`, `socket`, `ctypes`, `__import__`, …).
- Whitelisted call targets (declared tools + a pure-stdlib subset).
- No `eval`, `exec`, `compile`, `getattr`/`setattr` with non-literal keys.
- No attribute escapes (`x.__class__.__bases__[0].__subclasses__()` family).
- Deterministic iteration (Starlark already mandates this).

Hard part is **being exhaustive about CPython's escape hatches** — engineering, not research. Existing AST-eval sandboxes (asteval etc.) have CVE history precisely because they tried "block bad nodes" instead of "capability discipline." Whitelist, don't blacklist.

The two layers compose cleanly:
- **AST check** guarantees: *only declared tools are reachable.*
- **Runtime hook** guarantees: *declared tools are called with policy-conformant arguments.*

Neither can do the other's job. Together they're sound.

### Layer 3 — Modular workflow contracts (optional, second tier)

Use case: a reusable utility `my_super_workflow(user, ...)` calls `send_email` internally. The author wants to advertise an invariant: "I will never email anyone other than `user`, regardless of other parameters."

```python
@workflow
@guarantees(
    "every call to send_email has address == user",
    # AST check from Layer 2 already gives: "no other path sends emails"
)
def my_super_workflow(user: EmailAddress, **kwargs) -> Report:
    body = render(kwargs)
    send_email(user, "Your report", body)         # ok
    if kwargs.get("notify_admin"):
        send_email(user, "Admin copy", body)      # also ok — still `user`
    return Report(...)
```

Verification tiers — pick the cheapest that handles the contract:

| Tier | Mechanism | Covers |
|---|---|---|
| 1 | Alias / dataflow (~200 LOC walker) | "address arg is `user` (or known projection of it)" — ~80% of practical cases |
| 2 | Refinement types | "address ∈ {user, admin_default}" |
| 3 | SMT (Cedar-style symbolic compile) | "address ∈ S where S is computed from user via …" |
| 4 | Interactive proof (Lean) | Recursion / arithmetic-heavy properties; rare |

**Where this earns its keep:** shared utility libraries, workflow templates, certified library functions. The contract is verified *once* at definition and consumed by many callers; runtime hooks can simplify when MSW's `user-only` guarantee is in scope. One-shot agent scripts don't need this.

**Cedar's design lesson applies:** deliberately restrict expressivity so verification is decidable at each tier. Refuse what you can't prove; ask the author to refactor.

---

## Use cases (driving examples)

1. **The email allowlist (the canonical case).**
   User has a `gog` CLI for sending email. They want: "only email people in `allowed_emails.csv`."
   - Layer 1 alone handles it: `@policy_for(send_email)` queries DuckDB.
   - Layer 2 needed if the agent writes ad-hoc Python that could `subprocess.run(["gog", …])`.
   - Layer 3 not needed unless `my_super_workflow` wants to advertise its own constraint.

2. **Spend caps.**
   "Agent can't spend more than $X/day across all tools."
   - Layer 1: a `spendable(amt)` Prolog rule queries a running ledger.
   - Layer 2: prevents agent from calling payment APIs directly.

3. **Branch protection.**
   "Agent can only push to branches matching `claude/*` and never `main`."
   - Layer 1: rule against `git_push` tool.
   - Layer 2: prevents `subprocess.run(["git", "push", ...])` shortcut.

4. **Reusable certified workflow.**
   `my_super_workflow(user, ...)` is shared across 50 agents. Author wants "this workflow only emails its `user` parameter" verified once.
   - Layer 3: tier-1 alias analysis proves the invariant.

---

## What was considered and abandoned

Honest record of the design journey. Future maintainers should know what was tried and why it was set aside.

### Abandoned: "agent language" framing
Started with "Lean-but-less-geeky agent language." Abandoned in favor of "policy + capability framework that hosts off-the-shelf Python." A language is too ambitious and the actual leverage is at the tool boundary.

### Abandoned: Plan/Step/Spec three-layer DSL
Early sketch had Plan (DAG of steps), Spec (artifact-level contracts), Step (LLM-emitted unit). Folded into the simpler tools+policy+AST architecture. The Plan/Step structure is essentially what existing orchestration frameworks (Conductor, AutoGen, LangGraph) provide; our value-add is the policy + capability discipline that goes *under* whatever orchestration the user already has.

### Abandoned: rich effect/capability ontology as primary surface
Considered a taxonomy of guarantee types: `Authority` (`reads`, `writes`, `net.reads`, …), `Resource` (`time`, `tokens`, `memory`), `InformationFlow` (`Untrusted → Sanitized`), `Behavior` (`pure`, `idempotent`, `total`). Demoted: most of this can be expressed implicitly by "tool X is in the whitelist" + "policy P fires on tool X." A small set of effect tags may resurface as metadata on tools but not as the primary DSL.

### Abandoned: refinement types + flow-sensitive narrowing as the main check
Sketched a pattern where `EmailAddress[allowed]` is a refined type, `send_email` requires it, and the agent's `if allowed_recipient(addr): send_email(addr, ...)` narrows into the refined type. Elegant but **not needed** when a runtime hook can just check the argument at the boundary. Demoted to Tier-2 of Layer 3 — applicable only when the property is structural rather than value-level.

### Abandoned: natural-language top-layer rules file
Proposed: user writes "never use gog to email someone unapproved" in NL, system compiles to lower-level rule. Abandoned because **NL → executable rule is exactly the spot where LLMs get clever and wrong, silently**, breaking the deterministic-check property. Replaced by either (a) authoring rules directly in SQL/Prolog with NL as a doc-comment, or (b) a Cedar-style deliberately-restricted English-flavored grammar with deterministic parsing (no LLM in the parse path).

### Abandoned: heavyweight static checking as the default product
Originally most of the design weight was on the static checker. After interrogation of concrete use cases, ~80% of real needs are met by runtime hooks alone. AST checking became a *specific* tool with a *specific* job (boundary exhaustiveness), and modular contracts became *optional*. Don't ship the static checker as the front door.

### Set aside (not abandoned, just not v1)
- Information-flow / taint tracking for genuinely "byte must never leak" properties (API keys, PII). Real but orthogonal; can be added later.
- Temporal / lifecycle properties ("after `pay()`, `refund()` must be reachable for 24h"). Real but second-order.
- Bundled "guarantee profiles" (`@profile.gh_writer` etc.) as ergonomic shorthand. Re-add if v1 ergonomics demand it.

---

## Background research that informed the design

Curated highlights from the brainstorm's web research. These are the works whose ideas show up in the plan.

### Harvard Metareflection Lab (Nada Amin et al.)
The lab's three pillars are Safety (types/verification), Speed (metaprogramming), Accessibility (neuro-symbolic round-trip). Direct influences:
- **The Modular Imperative (LMPL 2025, Amin/Kravchuk-Kirilyuk/Graciolli)** — LLMs systematically violate modularity even when prompted to respect it: over-engineering, hidden dependencies, silent breaking changes. **Conclusion: modularity has to be enforced structurally, not by exhortation.** Direct motivation for Layer 3's verified contracts and Layer 2's structural capability discipline.
- **VerMCTS (POPL/Dafny 2025)** — verifier-in-the-loop MCTS for Dafny/Coq synthesis; partial program checks prune branches mid-search. **Lesson: a checkable surface should give the verifier somewhere to stand at intermediate steps**, not just final output. Informs the "check per tool call" granularity.
- **dafny-annotator** — LLM proposes Dafny annotations, human approves. **Lesson: specs/contracts are auto-draftable with human-once-approval**, then deterministically checked. Applies to how policy rules and contract annotations should be authored.
- **DafnyBench + the new 1000-problem verified-programming benchmark** — context for the broader trajectory of LLM + verifier interplay.

### Cedar (AWS) — the closest production analog
- Verification-guided language design. **Deliberately less expressive than Rego** so the language stays *decidable*.
- Reference implementation in **Lean**; core properties proved.
- **Cedar Symbolic Compiler** translates policies to SMT; an SMT solver answers "could this policy *ever* permit X?" — sound, universal, no false positives.
- Lessons applied here:
  - Restrict expressivity at each verification tier so the lower tier handles the common case decidably.
  - "Permit/forbid/when/unless" structured form is more readable than Rego's free-form rules.
  - Soundness > expressivity for policy work.

### OPA / Rego
- Datalog-derived, much more expressive than Cedar.
- Runtime-evaluation-first; verification is bolted on and only works on subsets.
- **August 2025: Apple hired the OPA maintainers, sunsetting enterprise offerings** — real signal about the project's near-term trajectory.
- Lessons applied: Rego shows what *not* to do — pay for expressivity with verifiability.

### Claude Code Auto Mode (Anthropic, March 2026)
- Two-layer defense: input-side prompt-injection probe; output-side classifier evaluates each tool command.
- Classifier deliberately strips assistant prose and tool outputs so it can't be persuaded.
- Tiered approval: T1 reads/searches auto-approve, T2 in-project edits auto-approve, T3 shell/web/external/spawn → classifier review.
- **Ad-hoc Python/bash specifically demoted: broad "allow any Python" drops on entering Auto mode.**
- Reported **17% false-negative rate on overeager actions** — Anthropic explicit that "not a replacement for human review on high-stakes infrastructure."
- Lessons applied:
  - Tool-call as unit-of-enforcement is correct.
  - **Ad-hoc Python needs special treatment** — direct motivation for Layer 2.
  - Deterministic whitelist beats LLM classifier on soundness (the 17% FN is what classifier-based defense inherently costs).

### Starlark (Google/Bazel)
- Syntactically a strict subset of Python; semantically deterministic, hermetic, no I/O.
- Frozen-on-share for thread safety; deterministic dict/set iteration.
- **Proof-of-concept that a useful Python subset is engineering-tractable.** Direct template for Layer 2.

### Verifiably Safe Tool Use for LLM Agents (Doshi et al.)
- Four-tier enforcement: Blocklist / Mustlist / Allowlist / Confirmation.
- Information-flow + temporal-logic specs.
- Proposes MCP metadata tags: capabilities, confidentiality, trust_level, custom labels.
- Alloy-based bounded model checking.
- Lessons applied: the four-tier structure is good vocabulary; metadata tags on tools belong in the system even if v1 only uses a subset.

### AgentSpec (ICSE 2026)
- Runtime enforcement layer for LLM agents.
- Validates that enforcement at the agent/tool boundary is the right architectural location.

### Production patterns (DEED, Conductor, Agent Governance Toolkit — all 2026)
- The industry convergence is: declarative contracts, deterministic orchestration with zero-token routing, runtime policy enforcement before tool execution.
- Reinforces Layer 1 as the must-have base.

### Asteval / Two Six's "Hijacking the AST" / Microsoft "When prompts become shells"
- CVE history of AST-eval sandboxes that tried to *blacklist* dangerous nodes.
- **Lesson: whitelist authority, not syntax.** Direct architectural guidance for Layer 2.

### Sandbox literature (Northflank, NVIDIA, Cloudflare/Modal/E2B/Vercel reports, 2026)
- Containers insufficient for LLM-generated code; gVisor / Firecracker / libkrun for hardware isolation.
- **Env var leakage is the biggest blind spot.**
- Filter outbound network — agents don't need unknown IPs.
- Lessons applied: even with Layer 2's static check, the runtime should still run in a capability-isolated sandbox as defense in depth.

---

## Relationship to py-typedlogic

This project should be a **separate (private) repo** that depends on py-typedlogic narrowly, not a fork or an extension within pTL.

| | py-typedlogic | this project |
|---|---|---|
| Unit of interest | Facts in a data model | Tool calls in an agent run |
| Rules express | What can be inferred | What's permitted |
| Runtime role | Inference engine | Boundary enforcer |
| Target user | KR / data-model authors | Agent builders / ops / compliance |

### What to import from pTL
- The decorator + Python-AST → rule-language translation. If users author rules as decorated Python functions, pTL has done the lowering work.
- Pydantic + FactMixin pattern for typed policy data (e.g. `allowed_emails` is a Pydantic class with `FactMixin` so it round-trips to/from the rule engine).
- Eventually the Z3 wrapper, if/when Layer 3 reaches SMT-backed verification.

### What *not* to lift
- OWL-DL integration.
- Prover9 / Souffle wrappers.
- The general FOL solver abstraction (we want a focused policy evaluator, not a general theorem prover).

### Architectural relationship
Cedar : Lean :: this project : py-typedlogic. A narrow dependency for the rule-translation infrastructure; the new project owns its own runtime, sandbox, and AST checker.

---

## First prototype — sequencing

The smallest useful product is **Layer 1 alone**, end-to-end on the email allowlist use case. From there, add Layer 2 when the agent starts writing ad-hoc Python; add Layer 3 when shared workflows appear.

### Milestone 1 — Layer 1 vertical slice
- DuckDB-backed fact store; load CSVs.
- `@enforced` and `@policy_for` decorators.
- SQL-rule backend (Prolog backend deferred to M2).
- One worked example: `send_email` + `allowed_emails.csv`.
- CLI: `policy explain <denied-call-trace>` to show the matching rule and fact.
- **Acceptance test:** non-engineer edits `allowed_emails.csv`, the agent's behavior changes accordingly without a developer in the loop.

### Milestone 2 — Prolog rule backend
- Add Prolog facts as alternative fact source.
- Add Prolog rules as alternative rule language.
- Reuse pTL's translation infrastructure as a dependency.
- Worked example using transitive closure (e.g. org-chart ancestor rules).

### Milestone 3 — Layer 2 AST capability check
- Restricted-Python subset definition (Starlark-style).
- Whitelist-based AST walker.
- Test corpus of "should-pass" and "should-reject" Python snippets — particularly CPython escape-hatch attempts.
- Integration: agent-written Python is checked before being handed to the executor.

### Milestone 4 — Sandboxed executor
- Run the checked Python in a gVisor / Firecracker / Modal-style isolated process.
- Strip env vars; restrict network egress to declared hosts.
- Audit log every tool call.

### Milestone 5 — Layer 3 modular contracts (Tier 1: alias analysis)
- `@guarantees` decorator on workflow functions.
- Tier-1 alias/dataflow walker that proves "argument X to tool Y is always parameter Z."
- Worked example: `my_super_workflow(user, ...)` declaring per-recipient invariant.

Tiers 2–4 of Layer 3 are post-v1.

---

## Open questions / known tensions

- **Naming.** Pick a name that signals *gating / boundary / contract*, not *logic* or *theorem proving*. Avoid confusion with pTL.
- **Bundle abstraction for policies.** When does a user have 3 rules vs. 30? At what point does ad-hoc decoration give way to grouped policy bundles?
- **Rule-change semantics.** Hot-reload is a feature, but what happens to in-flight agent runs when rules change mid-session? Probably: rules pinned at session start; explicit `reload_policies()` to update.
- **Audit log schema.** Define early — this is what users will rely on for compliance and post-hoc debugging.
- **MCP integration.** Should `@enforced` know about MCP tool registration so policies can ride along with MCP tool metadata? Probably yes, eventually.
- **Confirm-above-threshold.** Doshi et al.'s "Confirmation" tier — some calls should always prompt regardless of policy outcome (charge_card, send_email_to_external, git_push to main). Define as a first-class policy outcome alongside permit/deny.
- **Per-call provenance for explanations.** A `PolicyDenied` exception should carry the rule that fired and the fact that matched. Prolog gives this for free via proof trees; SQL needs explicit query construction.
- **Layer 3 contract syntax.** The example used a string for the invariant; a structured form (decorator with named args, or a small predicate DSL) is probably better. Defer until prototyping makes the right ergonomics clear.

---

## Sources

Selected references that informed the design (full list available in chat transcript):

- [Metareflection Lab — Nada Amin, Harvard SEAS](https://namin.seas.harvard.edu/)
- [The Modular Imperative: Rethinking LLMs for Maintainable Software (LMPL 2025)](https://namin.seas.harvard.edu/pubs/lmpl-modularity.pdf)
- [VerMCTS: verifier + LLM + tree search](https://arxiv.org/abs/2402.08147)
- [Cedar: A New Language for Expressive, Fast, Safe, and Analyzable Authorization](https://assets.amazon.science/96/a8/1b427993481cbdf0ef2c8ca6db85/cedar-a-new-language-for-expressive-fast-safe-and-analyzable-authorization.pdf)
- [Introducing Cedar Analysis (AWS Open Source Blog)](https://aws.amazon.com/blogs/opensource/introducing-cedar-analysis-open-source-tools-for-verifying-authorization-policies/)
- [Cedar built with Lean (Lean Lang)](https://lean-lang.org/use-cases/cedar/)
- [OPA vs Cedar vs Zanzibar: 2025 Policy Engine Guide (Oso)](https://www.osohq.com/learn/opa-vs-cedar-vs-zanzibar)
- [Claude Code Auto Mode (Anthropic engineering, March 2026)](https://www.anthropic.com/engineering/claude-code-auto-mode)
- [Claude Code permission modes — official docs](https://code.claude.com/docs/en/permission-modes)
- [Starlark language design (Bazel)](https://github.com/bazelbuild/starlark/blob/master/design.md)
- [Towards Verifiably Safe Tool Use for LLM Agents (Doshi et al.)](https://arxiv.org/html/2601.08012)
- [AgentSpec: Customizable Runtime Enforcement (ICSE 2026)](https://cposkitt.github.io/files/publications/agentspec_llm_enforcement_icse26.pdf)
- [Safe Tool Calling for AI Agents](https://medium.com/data-science-collective/stop-trusting-your-agent-with-tool-arguments-dbe45fe158ad)
- [When prompts become shells: RCE in AI agent frameworks (Microsoft Security, May 2026)](https://www.microsoft.com/en-us/security/blog/2026/05/07/prompts-become-shells-rce-vulnerabilities-ai-agent-frameworks/)
- [Hijacking the AST to safely handle untrusted Python (Two Six)](https://twosixtech.com/blog/hijacking-the-ast-to-safely-handle-untrusted-python/)
- [asteval sandbox escape — cautionary CVE](https://github.com/lmfit/asteval/security/advisories/GHSA-vp47-9734-prjw)
- [Best code execution sandbox for AI agents, 2026 (Northflank)](https://northflank.com/blog/best-code-execution-sandbox-for-ai-agents)
- [Conductor: deterministic orchestration for multi-agent workflows (Microsoft, 2026)](https://opensource.microsoft.com/blog/2026/05/14/conductor-deterministic-orchestration-for-multi-agent-ai-workflows/)
- [DEED: declarative contracts for LLM agent reliability (2026)](https://earezki.com/ai-news/2026-05-14-why-your-llm-agent-needs-contracts-not-just-logs/)

---

## Kickoff prompt for the new repo's first session

> We're prototyping a three-layer agent guardrail framework — see `AGENT_POLICY_PLAN.md`. Start with Milestone 1: Layer 1 vertical slice. Build a DuckDB-backed policy engine with `@enforced` and `@policy_for` decorators and a SQL rule backend. Wire up one tool (`send_email` wrapping a stub) and one fact source (`allowed_emails.csv`). Acceptance test: a non-engineer edits the CSV, the agent's behavior changes without a developer in the loop. Do *not* build Layers 2 or 3 yet. The plan file is the source of truth for what's in scope and what was deliberately abandoned.
