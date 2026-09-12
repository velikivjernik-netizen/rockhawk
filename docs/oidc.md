# Optional OIDC hook

Local username/password is the supported path.

To begin wiring an identity provider:

```env
OIDC_ISSUER=https://idp.example.com/realms/firm
OIDC_CLIENT_ID=rockhawk
OIDC_CLIENT_SECRET=
OIDC_REDIRECT_URI=http://localhost:8080/api/auth/oidc/callback
```

`GET /api/auth/oidc/login` then returns the authorization parameters. The callback remains `501` until you complete authorization-code exchange, map `email` to a RockHawk user, and issue the same JWT used by password login.

Do not enable OIDC on the public internet without HTTPS and a reviewed client secret.
