# Threat model

RockHawk holds litigation and contract text. Treat a deployment as a privileged-data system even when the bundled demo is fictional.

## Assets

- Uploaded documents and extracted page text
- Review-table values, comments, assignments
- Audit trail
- Session tokens and password hashes
- Optional prompts sent to an OpenAI-compatible model

## Adversaries

- Stolen laptop / stolen Compose host
- Authenticated insider browsing a walled matter
- Malicious document (zip bombs are not fully mitigated)
- Prompt injection in a document that is later sent to `openai_compatible`
- Cross-matter leakage through Ask RockHawk (mitigated: Ask is table-scoped)

## Controls

| Risk | Control |
| --- | --- |
| Password theft | bcrypt hashes; published demo password must be rotated |
| Session theft | HMAC JWT, short-ish TTL, HTTPS in front of Compose on any network |
| Unauthorized matter access | Membership + ethical walls checked on every matter-scoped route |
| Fabricated legal facts | Mock extractor is lexical; remote prompt forbids invention; UI labels drafts |
| Audit tampering | Append-only table; no update/delete API |
| Data loss | Docker volumes; restart-safe |
| Model exfiltration | Default `AI_PROVIDER=mock`; remote provider is opt-in |

## Residual risk

- This build does not implement disk encryption, WORM audit storage, or a SIEM export
- OIDC is a hook, not a complete SSO implementation
- Ethical walls do not search for conflicts automatically
- `SECRET_KEY` in `.env` is equivalent to a signing HSM for JWTs — protect the file

See also [known limitations](known-limitations.md).
