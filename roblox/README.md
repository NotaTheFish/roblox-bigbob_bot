\# Roblox integration scripts



This folder contains Luau modules that connect your Roblox experience to the FastAPI backend that powers \*\*roblox-bigbob\_bot\*\*. The snippets are designed to be copied into Roblox Studio and wired into your game logic.



\## File overview



| File | Purpose | Roblox placement |

| --- | --- | --- |

| `BackendConfig.lua` | Configuration template for backend URL, HMAC secret, and endpoint paths. | ModuleScript inside \*\*ServerStorage\*\* (e.g. `ServerStorage/Backend/BackendConfig`). Keep the real secret server-side only. |

| `BackendClient.lua` | Low-level HTTP client that signs requests with the shared HMAC key and handles JSON parsing. | ModuleScript inside \*\*ServerStorage/Backend\*\*. |

| `VerificationService.lua` | High-level helper for verification code checks (`/bot/verification/\*`). | ModuleScript inside \*\*ServerStorage/Backend\*\*. |

| `ShopGrantService.lua` | Helper for dispatching shop grant requests to `/game/grant`. | ModuleScript inside \*\*ServerStorage/Backend\*\*. |

| `ServerBootstrap.server.lua` | Example Script showing how to connect the modules inside `ServerScriptService`. | Script placed directly under \*\*ServerScriptService\*\*. |



You can move the modules to another server-only container (such as \*\*ReplicatedStorage\*\* with permissions locked) as long as secrets are not exposed to the client.



\## Configuring secrets and URLs



1\. \*\*Create a backend folder\*\* in \*ServerStorage\* (recommended) and add the ModuleScripts listed above.

2\. Open `BackendConfig.lua` and update:

&nbsp;  - `BaseUrl` — the public HTTPS URL of your FastAPI deployment (no trailing slash).

&nbsp;  - `HmacSecret` — must match the `HMAC\_SECRET` environment variable configured for the backend. Store this value server-side only.

&nbsp;  - `Endpoints` — adjust paths if your API routes differ. Default values align with the existing FastAPI routes (`/game/grant`, `/game/progress/push`, etc.).

&nbsp;  - `Timeout` or `DefaultHeaders` if you need to tune HTTP behaviour (for example, to add `X-Server-Key`).

3\. In Roblox Studio, ensure \*\*Allow HTTP Requests\*\* is enabled under \*Game Settings → Security\* so the scripts may contact the API.

4\. (Optional) If you prefer not to keep secrets inside a ModuleScript, replace `BackendConfig.lua` with code that reads the secret from a `StringValue` stored in `ServerStorage` or from an external configuration provider at runtime.



\## Wiring the scripts in Roblox Studio



1\. Copy `BackendClient.lua`, `VerificationService.lua`, `ShopGrantService.lua`, and `BackendConfig.lua` into `ServerStorage/Backend/`.

2\. Copy `ServerBootstrap.server.lua` into `ServerScriptService` and adjust the `require` paths if you placed the modules elsewhere.

3\. Attach gameplay logic:

&nbsp;  - \*\*Verification flow\*\*: set `player:SetAttribute("VerificationCode", code)` when the player enters their Telegram-provided code (e.g. via a TextBox or a command). The bootstrap script will automatically call the backend through `VerificationService` and set `player:GetAttribute("Verified")` based on the response.

&nbsp;  - \*\*Shop grants\*\*: create a `RemoteEvent` named `GrantPurchase` inside `ReplicatedStorage`. Fire the event from the client with a payload `{ rewards = { { type = "currency", amount = 100 } }, source = "shop" }` when the player purchases something. The server script uses `ShopGrantService` to call `/game/grant` and you can react to the response (e.g. grant in-game currency).

&nbsp;  - \*\*Progress sync (optional)\*\*: `BackendClient` exposes `Post`/`Get` helpers so you can push additional data to `/game/progress/push` or other FastAPI routes by calling `client:Post(Config.Endpoints.ProgressPush, payload)` inside your own Scripts.

4\. Monitor the output window for warnings—network issues or invalid payloads surface as `warn` messages.



\## FastAPI security headers



All helper modules automatically:

\- Generate an `Idempotency-Key` header using `HttpService:GenerateGUID(false)` for each request.

\- Sign the request body with the shared HMAC secret and attach it as `X-Signature`.

\- Encode payloads as JSON.



Ensure the backend uses the same HMAC secret (see `backend/security.py`) or requests will be rejected with `401 Unauthorized`.



\## Customising responses



The example assumes the verification endpoint returns `{ "status": "verified" }` or `{ "verified": true }`, and the grant endpoint returns `{ "request\_id": "..." }`. Update the handling logic in `ServerBootstrap.server.lua` if your FastAPI responses differ.



\## Testing locally



When running the FastAPI app locally (e.g. `uvicorn backend.main:app --reload`), update `BackendConfig.BaseUrl` to use `https://localhost:8000`. Roblox Studio requires HTTPS URLs; use a tunnelling tool (ngrok, Cloudflare Tunnel) if necessary and set the URL accordingly.

