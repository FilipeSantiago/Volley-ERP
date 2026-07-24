# Memory

Last updated: 2026-07-24

## Purpose
This file is a local project memory for future conversations in this repository. It captures modeling decisions, constraints, and recent work completed in the repo.

## High-level Context
Project: `volley_erp`
Type: FastAPI backend for volleyball operations with Google OAuth, Firestore authorization data, Google Drive/Sheets workspace integration, and JWT-based stateless API auth.

## Important Communication / Working Constraints
- The user may ask for planning-only responses. Respect explicit instructions like `plan it do not code`.
- When asked to modify only entities, do not change repositories, services, controllers, dependency injection, endpoints, tables, worksheets, or collections.
- The user explicitly asked to avoid introducing redundant financial ledgers.
- `FinancialEntry` is the single transactional ledger.
- `OperatingExpense` should not become a separate competing ledger.

## Recent README / Feature Mapping Work
A comprehensive `README.md` was written to reflect implemented features already present in the repo:
- Google OAuth web/mobile auth
- JWT access/refresh tokens
- organizations / invites / teams
- athletes / coach
- recurring monthly fee rules
- Google Drive + Sheets workspace provisioning

## Finance / Entity Modeling Decisions
### Core rule
- `FinancialEntry` is the only ledger.
- Other entities explain why a ledger entry exists.

### Membership fee domain
- `MembershipFee` is a recurring rule/template, not proof of payment.
- Existing recurring monthly fee semantics were preserved in the entity layer:
  - `MONTHLY_CONTRIBUTION -> CREDIT`
  - `COACH -> DEBIT`
  - `COMMISSION -> DEBIT`
  - `COURT -> DEBIT`
- Validation semantics preserved conceptually:
  - `MONTHLY_CONTRIBUTION` requires `athlete_id`
  - `COACH` forbids `athlete_id`
  - `COMMISSION` forbids `athlete_id` and requires `person_name`
  - `COURT` forbids `athlete_id` and `person_name`
- `MembershipFeeCharge` represents one athlete’s obligation for one month.
- `EventCost` represents immutable cost snapshots caused by events.
- `Cashflow` models are DTO/read-model only, not persisted aggregates.

### Operating expense decision
- The user decided `OperatingExpense` should not be a meaningful separate domain ledger.
- Current implementation keeps `OperatingExpense` only as a compatibility wrapper over debit-side `FinancialEntry` semantics.

## User / Auth Modeling Decisions
### Auth architecture
- Keep auth stateless.
- Do not persist API JWT sessions/tokens.
- Persist only user identity and Google connection state.

### Persisted auth entities
- `User`
- `GoogleConnection`

### User/Auth repository decision
- Repositories were updated previously to validate against typed auth entities while still returning dict-shaped data for compatibility.
- Auth flow itself was intentionally kept unchanged.

## Organization / Team / Person / Athlete Modeling Decisions
The user clarified that the correct domain should explicitly model `Team`, and that `Person` should be linked to `User`.

### Core identity structure
- `User` = platform identity / auth subject
- `Person` = human/business identity
- `Person.user_id` is optional

### Canonical entities now expected in the domain
- `Organization`
- `Team`
- `OrganizationMember`
- `TeamMember`
- `Athlete`
- `AthleteTeamRelationship`
- `Coach`
- `Event`
- `EventAttendance`
- `EventCost`
- `FinancialEntry`
- `MembershipFee`
- `MembershipFeeCharge`

### Important distinction
Do not merge these two concepts:
- `TeamMember` = authorization relationship (`User <-> Team`)
- `AthleteTeamRelationship` = sports participation relationship (`Athlete <-> Team`)

### Team scoping rule
`team_id` is a real aggregate boundary and must remain explicit on operational/financial entities, including:
- `Coach`
- `Event`
- `EventAttendance`
- `EventCost`
- `FinancialEntry`
- `MembershipFee`
- `MembershipFeeCharge`
- `OperatingExpense` compatibility wrapper

## Work Completed In `models/entity`
Entity-only work was requested and implemented without touching repositories/services/controllers in that turn.

### Added canonical entities
- `models/entity/organization.py`
- `models/entity/team.py`
- `models/entity/organization_member.py`
- `models/entity/team_member.py`
- `models/entity/athlete_team_relationship.py`

### Updated existing entity files
- `models/entity/person.py`
  - `Person` includes optional `user_id`
- `models/entity/athlete.py`
  - `Athlete` includes optional `person_id`
- `models/entity/coach.py`
  - `Coach` includes optional `person_id`
- `models/entity/__init__.py`
  - exports updated to include the new entity models

### Intended domain graph
- `User`
  - platform account
- `Person`
  - optional link to `User`
- `Organization`
  - owns many `Team`
- `Team`
  - belongs to `Organization`
- `OrganizationMember`
  - `User <-> Organization`
- `TeamMember`
  - `User <-> Team`
- `Athlete`
  - athlete profile, optional link to `Person`
- `AthleteTeamRelationship`
  - `Athlete <-> Team`
- `Coach`
  - coach profile, optional link to `Person`, team-scoped in current behavior
- `FinancialEntry`
  - single ledger

## Testing / Validation History
- Existing tests previously passed after entity/auth work using:
  - `.venv/bin/python -m unittest discover -s tests`
- A non-fatal log line can appear during tests:
  - `Failed to ensure organization workspace org_id=org-1: Google Drive API is not enabled.`
- That log did not fail the suite.

## Important Future Guidance
If the user next asks to continue this line of work:
1. Re-read `models/entity/*` first.
2. Respect the distinction between auth membership and sports participation.
3. Do not introduce new ledgers.
4. Keep auth stateless unless the user explicitly changes that decision.
5. If asked to wire repositories/services next, start with organization/team membership repositories before broader service refactors.

## Limitation
This file is the persistent project note. It is not a guarantee of platform-level memory across all future sessions, but it should let a future turn recover the context quickly by reading this repository file.
