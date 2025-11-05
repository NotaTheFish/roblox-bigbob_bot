--!strict
--[[
    Roblox backend integration configuration.
    Replace placeholder values with the deployment specific secrets before
    publishing your experience.
]]

local BackendConfig = {
    -- Base URL of the FastAPI service handling Roblox integrations.
    -- Example: "https://bigbob-bot.example.com" (no trailing slash).
    BaseUrl = "https://your-fastapi-hostname",

    -- Shared HMAC secret – must match BACKEND_HMAC_SECRET in the FastAPI app.
    -- Never commit the real secret to version control. Store it inside
    -- ServerStorage or use an environment-specific Script in Roblox Studio.
    HmacSecret = "replace-me",

    -- Optional default headers that should be attached to each request.
    DefaultHeaders = {
        ["User-Agent"] = "BigBobRobloxServer/1.0",
    },

    -- Request timeout in seconds for HttpService calls.
    Timeout = 10,

    -- Endpoint paths used by the helper modules.
    Endpoints = {
        VerifyCode = "/bot/verification/check",
        VerificationStatus = "/bot/verification/status",
        GrantRewards = "/game/grant",
        ProgressPush = "/game/progress/push",
    },
}

return BackendConfig