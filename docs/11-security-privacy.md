# Security and privacy

**Status:** Accepted baseline

## 1. Security goals

Protect account access, truthful learner profile, unpublished content, attempts, voice recordings, transcripts, provider credentials, and administrative actions. Preserve integrity of progress and releases. Maintain useful auditability without logging secrets or excessive personal data.

## 2. Data classification

- **Public:** intentionally published marketing content.
- **Internal:** generic course content, architecture, operational metadata.
- **Confidential:** profile, progress, answers, transcripts, learner claims.
- **Highly sensitive:** credentials, refresh tokens, raw voice, provider secrets, recovery material.

Each field and object class receives an owner, retention policy, allowed processing purposes, and export/deletion behavior.

## 3. Initial threat model

Relevant threats include credential theft, session replay, brute force, insecure object URLs, IDOR across future users, content/admin privilege escalation, prompt injection, malicious imports, stored XSS in content, SQL injection, CSRF, SSRF through media/provider URLs, oversized audio denial of service, queue replay, dependency compromise, leaked Railway variables, backup exposure, and accidental public deployment.

## 4. Authentication

Initial private access uses a provisioned account; there is no public registration. Passwords use Argon2id with reviewed parameters. Sessions use short-lived access and rotating refresh tokens, stored hashed server-side and revocable.

Cookies, if used, are Secure, HttpOnly, appropriate SameSite, narrowly scoped, and protected against CSRF. Login attempts are rate-limited and security events are recorded without storing raw passwords.

Do not hard-code one user ID. Future accounts must work without data redesign.

## 5. Authorization

Backend enforces authorization on every resource. UI hiding is not authorization. Initial roles: learner, editor, administrator. Permissions distinguish content draft, publish, import, provider config, system operations, and learner data.

Repository queries include ownership/permission scope. Tests specifically attempt cross-user access even before public multi-user launch.

## 6. Secrets

Secrets exist only in local secret stores or Railway variables. Never commit `.env`, tokens, private keys, database URLs, signed URLs, or provider payloads containing credentials.

Use separate secrets per environment, least privilege, rotation procedures, and deployment-safe secret changes. Logs redact authorization headers, cookies, database URLs, and configured sensitive keys.

## 7. Web/API controls

- exact CORS allowlist;
- CSRF protection for cookie-authenticated mutations;
- input validation at trust boundaries;
- parameterized database access;
- output encoding and sanitized rich content;
- restrictive Content Security Policy;
- security headers;
- request size/time limits;
- rate limiting by endpoint risk;
- correlation IDs that contain no personal data;
- safe error messages.

## 8. Media security

Audio objects are private. Access uses short-lived signed operations after authorization. Object keys are opaque and user-scoped. Upload finalization validates content type, size, duration, checksum, and ownership.

Do not trust browser MIME type alone. Consider malware scanning when supporting broader file imports. Lifecycle deletion is reconciled with database state.

## 9. AI and prompt security

Learner answers and imported content are untrusted data, never privileged instructions. Prompts delimit data, use structured outputs, validate schemas, cap length, and restrict tools/provider capabilities.

AI cannot directly publish, change permissions, execute database writes, or confirm biographical facts. Provider output is validated and escaped before rendering.

## 10. Import security

Imports have file limits, parser safety, formula neutralization on exported spreadsheets, schema validation, reference limits, dry run, and authorized publish. Archive expansion and external URL fetching are disabled unless explicitly secured.

## 11. Privacy and consent

Before first recording, explain what is recorded, why, providers involved, retention, and deletion controls. Store consent version/time. Refusing optional voice processing leaves text learning usable.

Collect the minimum data. Do not train external models on learner data unless provider terms and explicit consent permit it. Provider settings should disable data retention/training where available.

## 12. Retention

Configure separately for raw audio, raw provider responses, transcripts, derived evaluations, attempts, security logs, audits, and backups. Scheduled deletion produces auditable results and retries failures.

Backups inherit data sensitivity and retention. Deleting live data does not falsely imply immediate deletion from all backups; policy must explain restoration-handling.

## 13. Logging and analytics

No raw tokens, passwords, complete voice payloads, signed URLs, or unnecessary answer text. Prefer IDs, status, timing, size, error code, and model version. Analytics events are pseudonymous and purpose-limited.

## 14. Dependency and supply chain

Lock dependencies, review automated updates, scan packages/images, produce an SBOM when feasible, pin CI actions by trusted versions, protect main branch, require checks, and avoid unreviewed install scripts.

## 15. Backups and incident response

Backups are encrypted and access-controlled. Restore drills verify usefulness. Incident procedure covers detection, containment, credential rotation, scope analysis, recovery, user notification obligations, and post-incident remediation.

## 16. Security release gate

Before production: threat review, secret scan, dependency scan, authorization tests, CSP/CORS/CSRF verification, upload abuse tests, rate limits, backup verification, privacy text, deletion path, provider data-settings review, and production visibility check.
