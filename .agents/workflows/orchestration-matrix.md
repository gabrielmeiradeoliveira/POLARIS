# Orchestration Matrix and Multi-Agent Delegation Policy

This document defines the operational delegation matrix, runtime boundaries, file authorization constraints, and verification workflow for multi-agent execution in POLARIS within the Antigravity runtime.

---

## 1. Proven Runtime Capabilities vs. Unconfirmed Hypotheses

To prevent assumptions and maintain operational predictability, runtime parameters are strictly classified based on empirical evidence:

### 1.1. Schema-Accepted Model Values
The Antigravity runtime tool `invoke_subagent` accepts **only** the following enum values for its `Model` parameter:
- `"inherit"`: Inherits the active model of the parent conversation.
- `"flash_lite"`: Lighter, fast execution tier.
- `"flash"`: Balanced execution tier.
- `"pro"`: Higher-capacity reasoning tier.

Any other value (such as commercial identifiers, vendor names, version strings, or custom aliases like `"Argon"`, `"gemini-4-argon"`, or `"claude-sonnet"`) is rejected by runtime schema validation.

### 1.2. Observed Session Model
- In the active development interface session where this investigation occurred, the selected model was recorded as **Gemini 3.8 Flash (Medium)**.
- **Record only**: This reflects solely the model observed in that specific session. It is **not** a permanent configuration, default, or fixed repository constraint.
- Commercial models such as "Argon" were **not confirmed available in the investigated runtime interface** and must not be documented as available or assumed active without explicit verification in the active UI.

### 1.3. Subagent Execution Evidence
Empirical validation probes executed on this runtime confirmed:
- Subagent invocations requesting `Model: "flash"`, `Model: "pro"`, `Model: "flash_lite"`, and `Model: "inherit"` were each accepted by `invoke_subagent` and produced responses.
- **Evidence scope**: This proves that all four schema options are operational dispatch values in this runtime.
- **Evidence limit**: The runtime does not identify or publish the exact underlying commercial model name or version serving the subagent turns. Commercial identity mappings for `pro`, `flash`, or `flash_lite` remain: **Not confirmed in the investigated runtime**. Token pricing, performance metrics, and hard token limits are likewise **not confirmed in the investigated runtime**.

### 1.4. Runtime Subagent Types
- In the investigated IDE runtime, empirical tests confirmed that `invoke_subagent` accepts:
  - `TypeName: "self"`: Subagent with workspace read/write/edit tools and command execution capabilities.
  - `TypeName: "research"`: Subagent restricted to read-only exploration tools (`view_file`, `list_dir`, `grep_search`). File writing and command execution tools are absent.
- **Scope limit**: These reflect the functional types observed in the investigated runtime. They are not asserted to be universally the only types across other Antigravity versions or interfaces.
- **Isolation limit**: `research` and `self` share the workspace filesystem. They are separate execution turns/threads with distinct tool surfaces, not hermetically isolated containers or independent virtual machines.

### 1.5. Maestro Custom Specialists in IDE Runtime
- The Maestro plugin repository includes 39 custom specialist markdown files in `~/.gemini/config/plugins/maestro/agents/*.md` (`architect`, `coder`, `tester`, `code-reviewer`, etc.).
- Direct invocation via `invoke_subagent(TypeName: "architect")` failed in the investigated IDE runtime with:
  `subagent "architect" not found or not allowed to be invoked`.
- **Limitation scope**: This limitation applies specifically to the investigated IDE environment (consistent with Maestro documentation noting custom agents run in CLI/App but are not registered as standalone invocation targets in the IDE). It does not imply that custom specialists are universally incompatible with all Maestro environments.
- **Operational Alternative**: Specialist personas and methodologies are executed by selecting a valid native runtime type (`research` for read-only roles, `self` for implementation/testing roles) and injecting the specialist role, prompt template, and tool constraints into `Prompt` and `Role`.

---

## 2. Operational Delegation Matrix

The table below defines the required delegation policy. Requested model tiers represent runtime level selections, not guarantees of commercial model identity:

| Stage | Runtime Type | Requested Model | Permissions and Restrictions |
|---|---|---|---|
| **Planning** | `research` or Main Orchestrator | `pro` for `research`; Orchestrator uses current session model | Read and analyze only; produce plan without editing any files. |
| **Implementation** | `self` | `pro` | Modify strictly the explicitly approved files. No scope expansion. |
| **Testing** | `self` | `flash` | Run approved tests; modify tests only if test files are explicitly in the approved plan. |
| **Independent Review** | `research` | `pro` | Read-only; inspect diff, surrounding context, and test outputs; produce findings with `path:line` citations. |
| **Correction** | `self` | `pro` | Correct only confirmed review findings in authorized files; maximum of two cycles. |
| **Final Report** | Main Orchestrator | `inherit` does not apply as a mandatory subagent selection (runs in main session) | Consolidate results, limitations, test outputs, and modified files. |

> [!IMPORTANT]
> If any combination of runtime type and model cannot be dispatched by the runtime, do not improvise or substitute fictitious configurations. Log the exact error, halt the dependent stage, and report the limitation to the user.

---

## 3. Strict File Authorization and Workspace Rules

### 3.1. Enforcement Architecture: Platform Hard Controls vs. Agent Protocol Controls

To ensure strict operational clarity, execution boundaries are explicitly divided into what the runtime enforces mechanically versus what the agent must follow as behavioral protocol:

- **Platform Hard Controls (Runtime Enforced)**:
  - Tool surface restrictions: The Antigravity runtime strictly enforces available tools per subagent type (e.g., `research` has no file-writing or terminal execution tools in its schema, preventing edits).
  - Schema parameter validation: The runtime mechanically validates the `Model` enum (`inherit`, `flash_lite`, `flash`, `pro`) and rejects unregistered types or arbitrary model strings.
  - Subagent registration checks: Rejection of unregistered custom agent names (such as direct `architect` invocations in the IDE).

- **Agent Protocol Controls (Instruction Enforced)**:
  - Human approval before editing code.
  - Path-based file authorization and confinement to approved files.
  - Prohibition of scope expansion or unauthorized test modifications.
  - Hard limit of two correction cycles.
  - Halting for human intervention on blockers or cycle exhaustion.

> [!CAUTION]
> The rules in the **Agent Protocol Controls** group are strict procedural mandates followed by the agent and verified by the human auditor. They are **not** automated runtime guarantees. The runtime does not provide an automated file-path whitelist sandbox, an automated cycle counter, or an automated approval interceptor. They depend on agent compliance and active human governance.

### 3.2. Operational File Authorization Rules

1. **Mandatory Planning Prior to Edits**:
   - Every task must begin with a structured implementation plan listing:
     - Clear technical objective and boundaries.
     - Files to create, modify, or delete (with exact paths).
     - Acceptance criteria.
     - Exact verification and test commands.
   - **Explicit human approval of the plan is mandatory** before any production or test code is edited.

2. **Test File Scope Confinement**:
   - Test files are treated with the same authorization rigor as production files.
   - Test files may only be created or modified if they are explicitly included in the approved plan.
   - If test adjustments or new test cases require modifying an unapproved test file, halt execution and request approval to update the plan.

3. **Prohibition of Silent Scope Expansion**:
   - Modifying files outside the approved list is strictly prohibited.
   - Speculative refactoring, unsolicited cleanup, reformatting unrelated files, or adding new dependencies is forbidden.
   - If an unexpected file modification becomes necessary during implementation, halt execution and ask the user to authorize the updated file list.

4. **Preservation of Pre-existing Changes and Persistent Git Baseline**:
   - Pre-existing local modifications and untracked files must never be reverted, overwritten, or removed.
   - Destructive Git commands (`git reset --hard`, `git clean`, `git checkout --`, `git restore`) are prohibited.
   - **Persistent Git Baseline Requirement**:
     - Before modifying any file in a new implementation task, the orchestrator must capture the verbatim output of `git status --short`.
     - This initial state must be persisted in a task-specific documentation artifact (e.g., in the task implementation plan or a dedicated baseline artifact under the task workspace) with an explicit path and clear stated purpose.
     - The output must be preserved verbatim without reformatting, truncation, or omission of untracked files.
     - At task completion, the final Git status must be compared directly against this persisted baseline artifact to cleanly differentiate pre-existing changes from changes introduced during the task.
     - **Historical State Notice**: For the initial documentation task that established this policy, no persistent on-disk baseline snapshot was generated prior to the first edits; evidence was captured solely within conversational trajectory logs. In all future development tasks, the persistent baseline artifact must be created on disk *before* any file edits begin.

5. **Approval Scope Boundaries**:
   - User approval of an implementation plan authorizes only the specified edits. It does **not** authorize commits, publishing, remote pushes, package installations, or external API calls.

---

## 4. Execution Workflow

Execution must proceed through the following unambiguous, sequential stages:

### Stage 1: Planning
1. Inspect the relevant repository context, guidelines, and files.
2. Formulate objective, confined scope, affected files, risks, acceptance criteria, and verification commands.
3. Present the plan to the user.
4. **Halt and await explicit human approval.** No code or test file may be created or edited before approval.

### Stage 2: Implementation
1. Dispatch implementation to `self` with requested model `pro`.
2. Implement strictly the approved vertical slice, following existing architectural patterns and style.
3. Do not expand scope silently.
4. Report the exact list of files created or modified.

### Stage 3: Testing
1. Execute the automated verification and test commands specified in the approved plan.
2. Record the exact command executed, exit code, and complete output.
3. Categorize results explicitly:
   - Passed tests.
   - Failed tests.
   - Skipped / unexecuted tests.
   - Interrupted tests.
4. Never state a test passed unless it ran to completion and returned a verified zero exit code.
5. Do not mistake environmental issues, timeouts, or service unavailability for confirmed code defects without direct evidence.
6. If modifying an unauthorized test file is necessary, halt and seek user approval.

### Stage 4: Independent Review
1. Request an independent review using `research` with requested model `pro` (verified read-only tool surface).
2. Provide the reviewer with the relevant diff, the approved plan, acceptance criteria, and test outputs.
3. The reviewer audits correctness, regression risks, security implications, error handling, and scope adherence.
4. Every finding must include:
   - Exact `path:line` citation.
   - Technical impact.
   - Verifiable evidence.
   - Concrete recommendation.
5. If the reviewer modified code or if read-only separation cannot be guaranteed, the review is **not** independent.
6. If read-only mode cannot be verified by the runtime, halt the workflow and report the limitation rather than falsely claiming an independent review occurred.

### Stage 5: Fix Iteration
A fix cycle is strictly defined as:
$$\text{Fix Cycle} = \text{Correction of confirmed findings} \longrightarrow \text{Re-execution of tests} \longrightarrow \text{New independent review}$$

Rules:
- Hard limit of **two correction cycles** per approved task (`Cycle 1/2` and `Cycle 2/2`).
- Count cycles explicitly in all progress updates.
- **Never initiate a third cycle automatically.**
- If unresolved issues, critical findings, or test failures persist after `Cycle 2/2`, **halt immediately and request human intervention**, providing all findings and evidence.
- Do not classify infrastructure or harness failures as code defects without evidence.
- If fixing a finding requires modifying files outside the approved plan, stop and request approval before touching additional files.

### Stage 6: Final Report
Every completed workflow must present a structured final report containing:
- Objective and approved scope.
- Files created and modified during the task.
- Pre-existing files and uncommitted changes preserved.
- Verification commands executed, exit codes, and output summaries.
- Test outcomes, coverage limitations, and unexecuted checks.
- Independent review outcome and status of all findings.
- Number of fix cycles consumed (e.g. `0/2`, `1/2`, or `2/2`).
- Runtime limitations encountered and model tiers requested.
- Confirmation of which checks were genuinely completed.
- Final Git status distinguishing task changes from pre-existing changes.

> [!CAUTION]
> Never declare a task completed or approved if mandatory tests were not executed or if unresolved critical/major review findings remain.

---

## 5. Stop Conditions (Mandatory Escalation)

Autonomous execution must halt immediately, preserving workspace state, when:
1. An existing document, rule, or test contradicts the user's instructions and requires human resolution.
2. Pre-existing local modifications cannot be preserved safely.
3. Implementation or review depends on an unproven runtime capability.
4. The required read-only separation for independent review cannot be verified.
5. Addressing an issue requires modifying files outside the authorized plan.
6. Two correction cycles have been exhausted without full resolution.

In any stop condition, state the condition, present the exact evidence, and await explicit human instructions.
