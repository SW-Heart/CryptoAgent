# Strategy Trading Product Roadmap

## Goal

Build the current product into a focused `AI Strategy Trading Cockpit`.

Product scope is intentionally narrow:

- Keep the backend on Python and FastAPI
- Keep the current agent-driven strategy workflow
- Focus only on strategy trading, not chat-first product expansion
- Support `Binance Live` and `Binance Testnet` as first-class exchange account types
- Use `nofx` as an architecture reference, not as the implementation base

## Final Product Shape

The product should converge on four stable domains:

1. `Overview`
   Account status, runtime summary, recent executions, operational alerts.
2. `Strategy Lab`
   Strategy configuration, indicators, risk controls, prompts, scheduling.
3. `Execution Console`
   Positions, orders, decision runs, logs, PnL, failure and risk events.
4. `Settings`
   Exchange accounts, LLM profiles, notifications, user-level preferences.

## Architectural Principles

- Do not replace the current codebase with `nofx`
- Reuse `nofx` ideas where they are structurally better:
  - information architecture
  - object-based configuration
  - runtime observability
  - engineering workflow
- Avoid copying `nofx` feature surface that is outside current scope:
  - multi-exchange sprawl
  - competition
  - Telegram agent
  - wallet / payment identity
  - community-heavy modules
- Keep risk control as a system constraint, not only a prompt instruction

## Core Domain Model

These entities should become the long-term center of the product:

- `ExchangeAccount`
  Represents a concrete exchange connection such as `binance_live` or `binance_testnet`.
- `LLMProfile`
  Represents a model provider and model configuration.
- `StrategyProfile`
  Represents a reusable strategy definition.
- `TraderInstance`
  Represents a running unit that binds strategy + exchange account + LLM profile.
- `DecisionRun`
  Represents one complete strategy execution cycle.
- `ExecutionEvent`
  Represents fine-grained events inside a run, such as ready-check, risk block, order submission, sync failure.

## Delivery Plan

### Phase 1: Product Skeleton

Goal: move from a single large workspace into a stable product shell without breaking current trading logic.

Deliverables:

- Introduce top-level authenticated product navigation:
  - `Overview`
  - `Strategies`
  - `Execution`
  - `Settings`
- Keep the current trading screen running inside `Execution`
- Add a unified frontend workspace shell
- Start centralizing frontend API access patterns
- Prepare the repo for gradual TypeScript migration
- Start splitting large frontend responsibilities by page

Success criteria:

- Logged-in users enter a structured product workspace instead of a single large page
- Current strategy trading flow remains usable
- Future work can land page-by-page without reopening the whole app shell

### Phase 2: Strategy Object Model

Goal: convert strategy-related settings into reusable product objects.

Deliverables:

- `StrategyProfile` CRUD
- Strategy configuration sections:
  - symbols
  - timeframes
  - indicators and parameters
  - risk budget
  - prompt template
  - schedule
  - dry-run / live mode
- Strategy duplication and enable / disable

Success criteria:

- A user can own multiple strategies
- Strategy definition is decoupled from runtime execution

### Phase 3: Trader Runtime

Goal: shift from global auto-trading toggles to managed runtime instances.

Deliverables:

- `TraderInstance` CRUD
- Bindings:
  - one strategy profile
  - one exchange account
  - one LLM profile
- Start / stop / pause / manual trigger
- Support both `binance_live` and `binance_testnet`

Success criteria:

- Runtime is modeled explicitly
- The user launches a trader, not a hidden global process

### Phase 4: Execution Console

Goal: make the runtime inspectable and operationally trustworthy.

Deliverables:

- positions view
- orders view
- decision timeline
- single run detail panel
- equity / PnL visualization
- risk block records
- runtime anomalies and warnings

Each `DecisionRun` should capture:

- market summary
- indicator summary
- LLM output summary
- risk verdict
- action taken
- order results
- duration
- token / cost metrics
- final status

Success criteria:

- Users can understand why the system acted or did not act
- Operators can debug failures without reading raw backend logs only

### Phase 5: Risk and Reliability

Goal: move from functional prototype to controlled trading system.

Deliverables:

- hard ready-checks before execution
- enforced risk constraints
- idempotency and duplicate-trigger protection
- scheduler single-instance protection
- retry and backoff rules
- audit logs
- strict live / testnet isolation

Success criteria:

- Failure modes are predictable
- Risk enforcement does not depend only on model compliance

### Phase 6: Engineering and Delivery

Goal: make the system maintainable for continued iteration.

Deliverables:

- frontend tests for critical flows
- backend tests for core strategy and execution APIs
- CI pipeline
- health checks
- cleaner Docker delivery split
- rewritten product and deployment documentation

Success criteria:

- Builds are verifiable
- Regression risk is lower
- The project can scale without relying on memory only

## TypeScript Migration Strategy

The frontend should migrate incrementally.

Order:

1. New service and API files move first
2. New page-level components use `tsx`
3. Existing large JSX files migrate when they are split
4. Add stricter typing after the page shell and API boundaries are stable

This keeps migration useful without turning it into a rewrite project.

## Phase 1 Build Order

The first development phase should be executed in this order:

1. Add the roadmap to the repository
2. Introduce authenticated workspace navigation and page shell
3. Keep the current strategy console under `Execution`
4. Add lightweight overview and strategy planning pages
5. Centralize frontend API access for new work
6. Begin splitting existing large components only where needed

## Current Decisions

- Backend remains Python
- Frontend can migrate to TypeScript incrementally
- Product scope remains strategy trading only
- Testnet stays in scope and should be treated as a configurable exchange account type
- `nofx` remains a reference architecture, not a migration target
