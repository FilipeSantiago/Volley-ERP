# Repository guidance

Build this FastAPI backend incrementally, feature by feature.

## Stack
- FastAPI
- Controller / Service / Repository architecture
- Google Sheets as DB (BYOS)
- Google Calendar for schedule events
- Google Drive for photo storage

## Working rules
- Do not generate the whole application at once.
- Implement only the requested feature.
- Inspect the current code first and reuse what already exists.
- Avoid code repetition and duplicate helpers/services/repositories.
- Keep controllers/routes thin, services for business logic, repositories for external data access.
- Prefer minimal diffs and consistency with the current codebase.
- If a better pattern or refactor is recommended, do not apply it automatically.
- First explain what was found, what would change, the benefits, and ask for permission.

## FastAPI rules
- Use APIRouter for feature/domain route organization.
- Use Pydantic models for request/response schemas when applicable.
- Use Depends() for endpoint-level dependency injection when appropriate.
- For file upload endpoints, use Form and UploadFile patterns.
- Keep validation at the API boundary whenever possible.
- Use dependency overrides in tests when useful.

## Repository and helper rules
- Do not centralize all Google Drive logic into a single generic repository for all domains.
- Keep repositories domain-oriented.
- Each domain should have its own repository when needed.
- Shared Google Drive operations should be extracted into helper/utility classes or functions.
- Domain repositories should use these shared helpers instead of duplicating Google Drive logic.
- The same principle can be applied to Google Sheets and Google Calendar integrations when useful.
- Repositories should remain responsible for domain-specific persistence flows, while helpers should contain reusable low-level integration logic.

## Dependency inversion and injection rules
- Apply Dependency Inversion across route/controller, service, and repository layers.
- Routes/controllers should depend on services, not instantiate them directly.
- Services should depend on repositories, not instantiate them directly.
- Repositories may depend on Google integration helpers/clients.
- Wire concrete dependencies at the application/bootstrap/composition level.
- If a DI framework/container is used, integrate it cleanly with FastAPI instead of bypassing FastAPI dependency patterns.
- Keep dependency wiring explicit and testable.

## Response order
1. Current understanding
2. Reuse analysis
3. Files likely to change
4. Minimal implementation plan
5. Optional pattern improvement proposal needing approval
6. Implementation
7. Test/checklist steps