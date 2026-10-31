# ScholarFlow — Hackathon Playbook and Cross-Chat Execution Guide

> **Superseded.** This describes an earlier idea (ScholarFlow) that was dropped before any code was written. The team built FasalSaakshi; see [README.md](README.md).

## 1. Purpose and current status

This is the standalone operating guide for planning, building, validating, submitting, and presenting ScholarFlow. A new chat should be able to use this document without access to the original conversation.

This document is a plan, not evidence of completed work. Creating it does not mean any portal, integration, source, deployment, or user journey has been verified.

This repository copy is portable: references to `HACKATHON_PLAYBOOK.md` mean this file at the repository root. If a chat cannot access the repository, attach or paste the playbook and the latest handoff instead.

### Current baseline

- Selected track: Theme 1 — Civic Pulse, Digital Governance & Public Information.
- Selected problem: Problem 3 — Autonomous Public Service & Bureaucracy Execution Agent.
- Working project name: ScholarFlow. Naming is provisional and must not consume early execution time.
- Direction: a scholarship application agent grounded in official requirements, supporting one real application journey with human control.
- Team: apparently three capable participants; exact responsibilities and relevant experience remain to be confirmed.
- Planning budget: 48 elapsed hours, based on the supplied event screenshots. Actual remaining time and submission deadline must be checked.
- Phase status: Phase 1 not yet executed or verified in this document.
- No suitable portal or authorized end-to-end workflow has yet been established in the planning conversation.
- No implementation, stack, algorithm, or architecture is prescribed here. Those decisions belong to the relevant execution phases.

### Project direction, not an unconditional promise

The intended journey is from official scholarship requirements and a student's background to a prepared application, with legitimate submission and verified acknowledgement only where appropriate, authorized, and feasible.

Do not claim submission if only preparation was achieved. Do not promise broad portal support before validating one workflow. If real execution is infeasible, make an explicit scope or problem-statement decision rather than disguising a preparation tool as an execution agent.

## 2. Competition facts and assumptions

The following were read from user-supplied screenshots, not independently reconfirmed:

| Evaluation category | Points |
| --- | ---: |
| Technical architecture and engineering depth | 20 |
| AI reasoning and agentic execution | 25 |
| Problem relevance, impact, and USP | 25 |
| Live demonstration and robustness | 30 |

Reported submission requirements:

- A problem statement and solution description.
- A working hosted application or endpoint.
- A 2–3 minute demonstration video showing real end-to-end behavior.
- A public GitHub/GitLab repository with setup instructions, architecture explanation, and source/configuration files.
- A 5–7 slide pitch deck.

Reported constraints:

- Teams have 2–3 members.
- Projects must be built during the event's build window.
- Fake data, static mock datasets, placeholder figures, and hardcoded mock responses are prohibited.
- Applications must use an active backend and real APIs, live databases, or official open datasets.
- Open-source libraries and starter boilerplate are allowed, but core work must be integrated and built during the event.
- Every teammate must understand and independently explain the project.
- Pre-recorded demonstrations must not be disguised as a live application.
- Plagiarism, pre-existing project submissions, and unauthorized assistance are prohibited.
- The top 10 reportedly present at a finale; two winners are judge-selected and one is audience-selected.

Confirm the complete current rules. In particular, clarify acceptable official-document storage/caching, AI coding assistance, external assistance, human-assisted portal steps, and development after initial submission.

No numerical winning probability or predicted judging score is justified by the available information.

## 3. Governing strategy

1. Reduce uncertainty before expanding scope.
2. Prove access and real execution before investing in presentation.
3. Support one real journey well before considering another.
4. Integrate continuously instead of accumulating disconnected components.
5. Use the rubric to select evidence, not to justify unnecessary complexity.
6. Treat reliability as product work, not final cleanup.
7. Preserve time for deployment, testing, submission, and rehearsal.
8. Prefer an honest limitation to an impressive unsupported claim.
9. Never infer that a resource is usable merely because the team can obtain accounts or credentials.
10. The decision to pursue this project is strategic, not a guarantee of winning.

## 4. Team operating model

Assign a primary owner for each responsibility:

| Role | Accountability |
| --- | --- |
| Product and evidence lead | User understanding, official requirements, scope, compliance, judging narrative |
| Execution lead | Technical direction, core execution, integration, deployment |
| Experience and quality lead | User journey, interaction quality, independent testing, demonstration readiness |

These are accountability roles, not exclusive coding territories. Everyone must understand the complete journey.

### Coordination rules

- Give every task one accountable owner and a concrete completion test.
- Keep a shared integrated version runnable as early as possible.
- Do not let two people make incompatible changes to the same interface without coordination.
- Hold a short checkpoint every 3–4 hours and at phase boundaries.
- Report access, compliance, and critical-path blockers immediately.
- At checkpoints answer: What now works? What remains unproven? What can prevent submission? What are we cutting or changing?
- Cross-review important work. The author is not the only tester.
- Keep brief evidence and decision notes as work happens; do not reconstruct the entire event from memory at the end.
- Schedule staggered rest and critical-path coverage. Forty-eight elapsed hours are not forty-eight productive hours per person.
- Delegate to additional AI agents only if the user explicitly authorizes it and current session instructions permit it.

## 5. Ground rules for execution

### 5.1 Evidence and truthfulness

Use these labels consistently:

- **Verified:** directly observed with a reproducible check and an evidence reference.
- **Reported:** stated by a teammate, user, organizer, or source but not independently checked.
- **Assumed:** temporarily accepted to proceed; must have a validation action if consequential.
- **Proposed:** not yet selected or implemented.
- **Blocked:** cannot proceed until a named dependency is resolved.

Keep planned, implemented, tested, deployed, and verified distinct. A successful local component test does not prove a deployed end-to-end journey.

Never fabricate source quotations, user feedback, telemetry, acknowledgements, screenshots, execution logs, performance numbers, or impact statistics.

### 5.2 Scope discipline

- Work on the current approved phase and its dependencies.
- Do not implement future-phase ideas simply because they are interesting.
- Every addition must identify its benefit, cost, validation method, and what it displaces.
- Support fewer workflows rather than weaken verification.
- After hour 28, favor strengthening existing behavior over adding major journeys.
- At hour 35, freeze major features. Exceptions require an explicit decision and a regression plan.
- Preserve testing, packaging, and submission time when cutting scope.

### 5.3 Technical decisions belong in the proper phase

- Do not preselect a framework, algorithm, or multi-agent architecture to make the project sound sophisticated.
- During discovery, investigate feasibility; do not turn a probe into an accidental production architecture.
- During implementation planning, compare only credible alternatives that affect the current decision.
- Prefer the simplest approach that meets the acceptance criteria and can be explained and tested.
- Record important decisions with their evidence, trade-offs, and reconsideration trigger.
- Do not expose or request private internal reasoning. Provide concise decision rationales, assumptions, tool outcomes, and evidence instead.

### 5.4 Real-world execution, privacy, and authorization

- Use real official source material and permitted access methods.
- Respect portal terms, authentication, access controls, and service limits.
- Do not bypass CAPTCHA, OTP, or other protective mechanisms.
- Keep human authentication, sensitive declarations, and final approval with the user.
- Never create fake applications just to obtain a successful demonstration.
- Use consenting users and collect the minimum personal information necessary.
- Do not collect or send identity documents to model providers by default.
- Do not expose credentials or sensitive personal data in repositories, logs, screenshots, recordings, or handoffs.
- Test non-destructively first. Obtain explicit approval before consequential actions, uploads, submissions, or payments.
- Distinguish factual user information from policy rules and system-derived findings.
- Report the actual state: draft prepared, awaiting intervention, failed, or submitted with verified acknowledgement.

### 5.5 Data and demonstration compliance

- Do not replace unavailable integrations with hardcoded success paths or mock datasets in the judged application.
- Do not assume that moving invented data into a live database makes it compliant.
- Clarify whether authentic official documents may be stored or cached and how provenance should be shown.
- Do not present stale information as current; show relevant source dates and freshness limits.
- A required recorded demo is acceptable as a recording; it must not substitute for live evaluation while being represented as live.
- Contingencies must reveal failures honestly. Never silently substitute a recording or fabricated response.

### 5.6 Changes, approvals, and session boundaries

- Inspect existing work before editing. Preserve changes made by others.
- Do not reset, delete, or overwrite unfamiliar work to make a task easier.
- Respect the current chat's mode and tool restrictions. In Plan mode, do not implement; request a switch to an implementation-capable agent when execution is approved.
- Do not assume new chats inherit previous permissions, tool availability, external sessions, or verified facts.
- Separate technical approval from authorization to take real-world consequential actions.
- Do not create extra plans, reports, or progress files unless requested. Maintain concise handoffs in chat unless the user approves a persistent location.

## 6. How deeply to investigate and think

Depth should follow consequence and uncertainty, not how interesting the topic is.

### Level A — Routine, reversible work

Examples: small presentation edits, straightforward wiring, low-risk usability fixes.

- Inspect the immediate context.
- State the completion test.
- Execute and verify.
- Avoid lengthy alternatives analysis.

### Level B — Important implementation choices

Examples: component boundaries, failure behavior, data handling, integration contracts.

- Inspect relevant existing work and requirements.
- Compare two or three viable approaches only when the choice matters.
- Identify likely failures and how the choice will be tested.
- Select an approach with a short rationale.
- Revisit only if new evidence invalidates the assumptions.

### Level C — High-risk or hard-to-reverse decisions

Examples: selecting a real portal, submission authorization, sensitive-data processing, changing project scope, dependency viability.

- Seek primary evidence and perform a small authorized feasibility check.
- Separate known facts from assumptions.
- Identify consequences, permission boundaries, and failure modes.
- Define a fallback or stop condition before committing substantial effort.
- Ask a targeted question when the answer changes permission, safety, scope, or feasibility.

### Time discipline

- Budget investigation before starting it.
- As a default, spend no more than 10–15 minutes decomposing an ordinary subphase; spend longer only when risk justifies it.
- Timebox a technical spike, normally 30–60 minutes, and specify what decision it must resolve. This is a guideline, not a reason to rush a safety check.
- Once evidence is sufficient to choose safely, act. Do not keep researching to avoid committing.
- If investigation expands, trade scope explicitly rather than borrowing silently from submission time.
- Long explanations are not a substitute for a working check.

## 7. Master timeline

Times are elapsed hours from the start of the available build window, not person-hours.

| Phase | Hours | Primary outcome |
| --- | --- | --- |
| 1. Competition alignment | 0–1 | Rules, deadlines, roles, judging checklist |
| 2. Real-world feasibility | 1–4 | A viable authorized workflow |
| 3. Scope and success criteria | 4–6 | A bounded journey and acceptance criteria |
| 4. Implementation planning | 6–8 | Technical decisions and integration agreements |
| 5. First end-to-end execution | 8–18 | One genuine integrated run |
| 6. Differentiation and user feedback | 18–28 | Stronger behavior supported by evidence |
| 7. Independent and adversarial testing | 28–35 | Known failures tested and prioritized |
| 8. Stabilization | 35–40 | Stable deployed release candidate |
| 9. Packaging and rehearsal | 40–44 | Complete materials and practiced story |
| 10. Audit and submission | 44–46 | Confirmed valid submission |
| 11. Protected buffer | 46–48 | Recovery margin and readiness |
| 12. Finale preparation | After submission | Presentation and live-evaluation readiness |

Collect evidence, deployment observations, and presentation notes throughout. Phase 9 is finalization, not the first time anyone thinks about documentation.

If time has already elapsed, create a revised schedule using verified progress. Shorten investigation and optional scope before reducing independent testing, submission verification, or the buffer.

## 8. Detailed phase instructions

### Phase 1 — Competition alignment | Hours 0–1

**Objective:** Establish what success, compliance, and submission actually require.

Actions:

1. Read the complete rules together.
2. Confirm deadline, timezone, build window, registration cutoff, and required submission fields separately.
3. Translate each rubric category into evidence judges should be able to observe.
4. List compliance ambiguities and ask organizers targeted questions.
5. Assign accountability and establish the checkpoint rhythm.
6. Reserve the final two hours as buffer.

Outputs: confirmed requirements, owner assignments, judging-evidence checklist, unresolved questions.

Gate: all teammates can explain what a successful and compliant submission means. Record unresolved organizer questions as risks rather than pretending they are resolved.

### Phase 2 — Validate the real-world path | Hours 1–4

**Objective:** Prove that the intended environment is usable before investing in it.

Actions:

1. Identify a small set of candidate scholarship workflows.
2. Inspect official requirements, current application availability, and actual portal steps.
3. Check access, authentication, document requirements, user eligibility, automation constraints, and permissions.
4. Speak with a few relevant students about actual difficulties.
5. Walk through the intended journey manually, stopping before consequential actions unless approved.
6. Identify human-only steps and externally controlled dependencies.
7. Select the strongest viable workflow and a credible alternative.

Outputs: verified workflow outline, source references, access risks, user observations, fallback candidate.

Gate: explain how a real user reaches a real outcome without invented data or unauthorized access.

If blocked: change the workflow now. If no suitable execution path exists, explicitly revisit scope and problem-statement alignment. Do not spend a day hiding a fatal dependency.

### Phase 3 — Define success and control scope | Hours 4–6

**Objective:** Agree on what must be demonstrated and what can be sacrificed.

Actions:

1. Describe the primary user and journey in plain language.
2. Define the starting state and observable finishing state.
3. Establish what can and cannot be claimed.
4. List the most consequential failure situations.
5. Separate must-prove work, optional improvements, and explicit exclusions.
6. Define acceptance criteria, inability-to-complete behavior, and a demonstration outline.

Outputs: bounded scope, definition of done, priorities, failure expectations, honest limitations.

Gate: every teammate describes the same user, journey, and finish line.

### Phase 4 — Plan implementation and integration | Hours 6–8

**Objective:** Make technical choices and parallel work coherent.

Actions:

1. Choose architecture and implementation approaches based on verified constraints.
2. Agree component boundaries, inputs, outputs, and integration responsibilities.
3. Establish shared development and deployment practices.
4. Break work into independently verifiable units.
5. Test the highest-risk technical assumptions first.
6. Decide how execution states and failures will be inspected.
7. Decide how secrets and personal data will be protected.
8. Confirm that the deployment path is usable early.

Outputs: selected technical approach, integration agreements, owned tasks, running foundation, tested deployment path.

Gate: teammates can work without guessing what another component will provide.

### Phase 5 — First real end-to-end execution | Hours 8–18

**Objective:** Complete the smallest genuine version of the entire supported journey.

Actions:

1. Prioritize connecting the journey over polishing isolated components.
2. Use actual permitted inputs, sources, execution steps, and result states.
3. Keep visual polish minimal.
4. Test through the intended deployment environment early.
5. Record failures and fix handoffs before adding depth.
6. Cross-review important work.
7. Run the complete journey together at the phase boundary.

Outputs: genuine integrated run, evidence of the observed outcome, remaining reliability gaps.

Gate: demonstrate the journey without manipulating hidden state or pretending manual actions were automated.

If no end-to-end run exists: stop optional work, reduce scope, and concentrate on the critical path. Disconnected components do not satisfy this gate.

### Phase 6 — Strengthen differentiation and gather feedback | Hours 18–28

**Objective:** Turn a first successful run into a convincing project.

Actions:

1. Identify the weakest demonstrated rubric categories.
2. Improve the behaviors that establish real technical depth and user value.
3. Test input and workflow variations.
4. Make uncertainty and intervention requests understandable.
5. Confirm explanations match actual decisions and execution.
6. Observe a few target users using the system with consent.
7. Address consequential friction.
8. Measure only what will be claimed, documenting how it was measured.

Outputs: stronger integrated behavior, actual feedback, measured evidence, clearer differentiation.

Gate: demonstrate why the project is more than a conversational wrapper or fixed replay.

After this phase, normally reject new major journeys.

### Phase 7 — Independent and adversarial testing | Hours 28–35

**Objective:** Find failures before judges do.

Actions:

1. Have someone other than the author test each important behavior.
2. Test missing and contradictory information, unsupported requests, unexpected actions, interruptions, repeated actions, external failures, partial completion, and required human involvement.
3. Test a fresh session without developer-only setup.
4. Reproduce, prioritize, fix or constrain, and retest each consequential defect.
5. Check source support, privacy exposure, and accurate success reporting.
6. Have teammates explain components they did not primarily author.

Outputs: defect list with disposition, verified failure behavior, known limitations, independent test observations.

Gate: common failures lead to understandable outcomes rather than misleading success, unsafe action, or unexplained crashes.

### Phase 8 — Freeze scope and stabilize | Hours 35–40

**Objective:** Protect the submission from instability.

Actions:

1. Freeze major features and prioritize high-impact defects.
2. Repeatedly test the deployed journey.
3. Check service availability, quotas, credentials, hosting behavior, and external workflow availability.
4. Remove dead controls and unsupported pathways.
5. Make limitations visible.
6. Verify a fresh user can start without the developer's private session.
7. Rehearse honest responses to external dependency failures.

Outputs: stable release candidate, verified deployment checks, demo contingency procedure.

Gate: the team trusts the deployed version more than the development version.

### Phase 9 — Package evidence and rehearse | Hours 40–44

**Objective:** Make the project easy to understand and inspect.

Actions:

1. Finalize the submission narrative: specific problem, target user, observed outcome, differentiation, limitations.
2. Verify repository setup, configuration instructions, architecture explanation, attributions, limitations, and testing instructions.
3. Finalize the required 5–7 slide deck.
4. Record the required 2–3 minute demonstration of actual behavior.
5. Ensure sensitive information is not exposed.
6. Rehearse the opening, live journey, engineering explanation, limitations, and unexpected judge request.
7. Audit claims across the application, repository, slides, and video for consistency.

Outputs: complete materials, accessible links, timed presentation, consistent evidence-backed claims.

Gate: an unfamiliar judge can understand and verify the project without continuous developer guidance.

### Phase 10 — Audit and submit | Hours 44–46

**Objective:** Secure a valid submission while recovery time remains.

Actions:

1. Assign a submitter and an independent verifier.
2. Check required fields, problem selection, link access, deployment, repository visibility, video playback, and deck permissions.
3. Open links from a clean browser session.
4. Check secrets, personal information, and capability claims.
5. Submit and inspect the actual platform confirmation.
6. Preserve a record of what was submitted and when.

Outputs: confirmed submission and independently verified links.

Gate: submission is confirmed, not merely saved as a draft or partially uploaded.

### Phase 11 — Protect the buffer | Hours 46–48

**Objective:** Handle surprises without risking valid work.

Actions:

1. Monitor deployment health.
2. Fix only submission-critical defects.
3. Rehearse questions and refresh team understanding.
4. Rest and preserve operational readiness.
5. Update the submission only if permitted.

Outputs: preserved working submission and team readiness.

Gate: no optional late change jeopardizes the submitted project.

### Phase 12 — Prepare for the finale | After submission

**Objective:** Convert a valid project into a clear live presentation.

Actions:

1. Confirm finale timing, format, connectivity, judging procedure, and update policy.
2. Preserve the submitted version; do not assume continued development is allowed.
3. Run mock judging with someone unfamiliar with the project.
4. Practice a shorter presentation and live input changes.
5. Recheck external dependencies shortly before presenting.
6. Ensure every member can explain the complete system and their own contribution.
7. Lead with a relatable user and visible transformation; support technical claims with inspectable evidence.

Prepare answers to: Why AI? What is adaptive? How is correctness checked? What requires approval? What happens when a portal changes? What was built during the event? How is it different? What evidence supports impact?

Gate: the team can present, answer independently, and handle a disrupted live journey honestly.

## 9. Mandatory phase execution protocol

Use this protocol whenever a phase is started or resumed.

### Step 1 — Reconstruct the actual state

Read this playbook and the latest handoff. Inspect only relevant existing artifacts. Confirm time remaining and mode restrictions. Separate verified progress from reported progress.

### Step 2 — State the phase contract

Before doing work, summarize:

- Phase and objective.
- Entry conditions and whether each is satisfied.
- Available time and reserved downstream time.
- Required outputs and completion evidence.
- Scope exclusions.
- Important risks and permission boundaries.

### Step 3 — Decompose only as far as useful

Create a small number of outcome-based subphases with dependencies and gates. Plan the current phase in detail; keep future phases at roadmap level.

### Step 4 — Approve the next action

Request approval for the decomposition, unless the user has already explicitly authorized proceeding within this bounded scope. In Plan mode, stop before implementation and explain the required agent switch.

### Step 5 — Execute incrementally

Work on the next unblocked subphase. Verify it before expanding. Surface important discoveries or blockers without narrating routine tool use.

### Step 6 — Evaluate the gate

Use one of these dispositions:

- **PASS:** required evidence exists; proceed.
- **CONDITIONAL PASS:** a noncritical issue is explicitly accepted, with owner and consequence recorded.
- **FAIL / BLOCKED:** stop dependent work, timebox resolution, reduce scope, or revisit the decision.

Do not conditionally pass unresolved authorization, truthfulness, privacy, or critical-path feasibility issues.

### Step 7 — Produce a handoff

Report what changed, what was verified, unresolved issues, time remaining, and the exact next action. Update this file only if the user requests it and current instructions allow it.

## 10. How to subdivide a phase

The purpose of subdivision is executable clarity, not additional bureaucracy.

### Decomposition rules

- Usually use 3–7 subphases. Use fewer when the parent is short.
- Use identifiers such as P2.1, P2.2, and P2.3.
- Name each subphase by an outcome, not a vague activity.
- Give each subphase an owner, timebox, dependency, output, verification method, and stop condition.
- Keep the total within the parent's time budget, including integration and verification.
- Parallelize only independent work. Do not confuse parallel team work with permission to spawn AI agents.
- Use further subdivision such as P2.3.a only where it removes a real execution ambiguity.
- Avoid more than two levels below the parent phase.
- If a blocker is unknown, define a short investigation with a decision outcome instead of inventing the answer.
- If a phase is too large, reduce scope or explicitly rebudget it; do not silently stretch the whole timeline.
- Do not choose detailed algorithms or technology in phases whose purpose is user, source, or workflow validation.

### Required subphase structure

For each subphase provide:

1. ID and outcome.
2. Why it is needed for the parent gate.
3. Entry conditions and dependencies.
4. Concrete actions, in order.
5. Accountable owner and any independent reviewer.
6. Timebox.
7. Expected output.
8. How completion will be verified.
9. Likely blockers and fallback/stop action.
10. Explicit non-goals.

## 11. Copy-paste prompt: start or subdivide a phase in a new chat

Replace bracketed fields before sending. If the chat cannot read repository files, attach or paste this playbook and the latest handoff.

```text
We are executing the ScholarFlow hackathon plan.

Read HACKATHON_PLAYBOOK.md at the repository root first.
If the repository is unavailable, use the attached or pasted playbook.

Current phase: [NUMBER AND NAME]
Current subphase, if any: [ID OR NONE]
Actual time remaining until submission: [HOURS/MINUTES, DEADLINE, TIMEZONE]
Time budget for this phase: [BUDGET]
Current workspace: [PATH]
Latest handoff: [PASTE HANDOFF OR PROVIDE ITS LOCATION]
Known changes since the playbook: [CHANGES OR NONE]

Your task is to prepare an executable decomposition of this phase, not to
replan the entire hackathon or immediately implement the project.

1. Read the playbook and handoff. Inspect relevant existing work using
   permitted read-only tools where useful. Do not assume earlier work is
   complete merely because it was planned or reported.
2. Summarize the objective, entry conditions, current verified state,
   important assumptions, available time, and parent completion gate.
3. Ask only questions whose answers materially affect authorization,
   safety, feasibility, scope, or the critical path. Make reasonable,
   reversible assumptions for minor matters and label them.
4. Divide the phase into a small number of outcome-based subphases.
   For each include: ID, objective, rationale, dependencies, ordered
   actions, owner, timebox, output, verification, blockers/fallback,
   and non-goals. Include integration and review time.
5. Separate sequential work from work teammates can do independently.
   Do not spawn AI subagents unless I explicitly authorize them.
6. Use risk-appropriate investigation depth. Resolve high-consequence
   uncertainties with primary evidence or a bounded feasibility check;
   do not produce endless alternatives or speculative detail.
7. Keep within this phase's purpose. Do not prematurely prescribe
   algorithms, architecture, or features belonging to later phases.
8. Preserve the playbook's truthfulness, real-data, authorization,
   privacy, scope, and submission-buffer rules.
9. Finish with the recommended order, the first concrete action, and
   the exact evidence required to declare this phase complete.

Stay in planning until the decomposition is approved. Respect the current
agent mode; if implementation requires a different agent, say so. Do not
create or modify files just to store this decomposition unless I ask.
```

## 12. Copy-paste prompt: execute an approved subphase

Use this in an implementation-capable chat after approving the decomposition. It does not authorize consequential real-world actions by itself.

```text
Use HACKATHON_PLAYBOOK.md at the repository root.
If the repository is unavailable, use the attached or pasted playbook.

Approved decomposition: [PASTE OR PROVIDE LOCATION]
Execute only: [SUBPHASE ID AND NAME]
Latest handoff: [PASTE OR PROVIDE LOCATION]
Actual time remaining: [TIME]
Workspace: [PATH]

First verify entry conditions and inspect relevant existing work. Then
execute this subphase within its approved boundaries and timebox.
Preserve work you did not create. Do not expand scope or implement the
next subphase automatically.

Use actual sources and permitted integrations. Do not fabricate data,
results, acknowledgements, tests, or success. Obtain separate explicit
approval for consequential portal actions or sensitive-data handling.

If a prerequisite is missing, state the blocker and the smallest next
decision rather than inventing a workaround. If the current chat is in
Plan mode, do not implement; request the appropriate agent switch.

Finish with: changes made, verification performed and results, gate
status, remaining risks, time impact, and a concise handoff. Reference
actual file paths or evidence when available. Do not claim unrun checks
passed. Do not modify the playbook or create extra progress files unless
I explicitly request it.
```

## 13. Handoff template for every new chat

Do not include secrets or sensitive personal data.

```text
SCHOLARFLOW HANDOFF

Timestamp and timezone:
Actual submission deadline:
Time remaining:
Workspace:
Current agent mode:

Current phase/subphase:
Parent objective and gate:
Gate status: PASS / CONDITIONAL PASS / FAIL / BLOCKED / NOT ASSESSED

Verified completed work:
- [Outcome — verification method — evidence reference]

Implemented but not verified:
- [...]

Reported facts / assumptions needing confirmation:
- [...]

Decisions and short rationale:
- [...]

Relevant files, commits, deployment links, and source references:
- [...]

Known defects and limitations:
- [Severity — consequence — owner]

External dependencies / permissions / manual interventions:
- [...]

What changed from the master plan:
- [...]

Next exact action:
- [...]

Do not do / explicit scope exclusions:
- [...]

Verification required before the next gate:
- [...]
```

### Suggested initial handoff

```text
Current phase: Phase 1 — Competition alignment.
Verified completed work: Strategic direction and this playbook only.
Unverified: Actual time remaining, full current rules, portal viability,
team assignments, user consent, sources, integrations, deployment.
Next action: Confirm deadline and complete Phase 1's entry checklist,
then decompose Phase 1 within its available time budget.
Scope restriction: No implementation or portal submission is authorized
merely by the existence of this plan.
```

## 14. Completion and decision records

Keep these concise, in chat unless persistent storage is explicitly approved.

### Phase completion record

```text
Phase/subphase:
Planned versus actual time:
Required outcomes:
Observed evidence:
Unrun checks:
Unresolved issues:
Gate decision and rationale:
Scope/time adjustments:
Next owner and action:
```

### Important decision record

```text
Decision:
Evidence and constraints:
Credible alternatives considered:
Chosen approach and concise rationale:
Known trade-offs:
Reconsider if:
Owner and time impact:
```

## 15. Non-negotiable milestones

| Target | Must be true |
| --- | --- |
| Hour 4 | A real, authorized workflow is viable, or a scope decision has been made |
| Hour 8 | Scope, ownership, and integration approach are agreed |
| Hour 18 | A genuine end-to-end run exists, or optional scope has been cut |
| Hour 35 | Major scope is frozen and independent failure testing is substantially complete |
| Hour 46 | Submission is confirmed and independently checked |

Final principle: prove risky assumptions early, integrate continuously, and spend the final quarter on reliability and communication rather than unfinished ambition.
