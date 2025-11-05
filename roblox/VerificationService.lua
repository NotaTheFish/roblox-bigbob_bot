--!strict
--[[
    Helper for checking Roblox account verification codes via the FastAPI backend.

    Example usage from a ServerScriptService Script:
        local ServerStorage = game:GetService("ServerStorage")
        local Config = require(ServerStorage.Backend.BackendConfig)
        local BackendClient = require(ServerStorage.Backend.BackendClient)
        local VerificationService = require(ServerStorage.Backend.VerificationService)

        local client = BackendClient.new(Config)
        local verifier = VerificationService.new(client, Config.Endpoints)

        local result = verifier:CheckCode(tostring(player.UserId), enteredCode)
        if result and result.status == "verified" then
            player:SetAttribute("Verified", true)
        end
]]

local HttpService = game:GetService("HttpService")

local VerificationService = {}
VerificationService.__index = VerificationService

export type Endpoints = {
    VerifyCode: string?,
    VerificationStatus: string?,
}

export type BackendClient = {
    Post: (self: any, path: string, body: any?, options: any?) -> any?,
    Get: (self: any, path: string, options: any?) -> any?,
}

function VerificationService.new(client: BackendClient, endpoints: Endpoints?)
    assert(client, "VerificationService requires a BackendClient instance")
    local self = setmetatable({}, VerificationService)
    self._client = client
    self._verifyPath = endpoints and endpoints.VerifyCode or "/bot/verification/check"
    self._statusPath = endpoints and endpoints.VerificationStatus or "/bot/verification/status"
    return self
end

function VerificationService:CheckCode(robloxUserId: string, code: string)
    assert(robloxUserId ~= "", "robloxUserId is required")
    assert(code ~= "", "verification code is required")

    local payload = {
        roblox_user_id = robloxUserId,
        code = code,
    }

    return self._client:Post(self._verifyPath, payload, {
        IdempotencyKey = HttpService:GenerateGUID(false),
    })
end

function VerificationService:GetStatus(robloxUserId: string)
    assert(robloxUserId ~= "", "robloxUserId is required")
    local query = string.format("%s?roblox_user_id=%s", self._statusPath, HttpService:UrlEncode(robloxUserId))
    return self._client:Get(query)
end

return VerificationService