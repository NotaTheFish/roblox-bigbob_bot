--!strict
--[[
    Helper module for requesting shop reward grants from the FastAPI backend.

    Example usage (ServerScriptService Script):
        local ServerStorage = game:GetService("ServerStorage")
        local Config = require(ServerStorage.Backend.BackendConfig)
        local BackendClient = require(ServerStorage.Backend.BackendClient)
        local ShopGrantService = require(ServerStorage.Backend.ShopGrantService)

        local client = BackendClient.new(Config)
        local grants = ShopGrantService.new(client, Config.Endpoints)
        grants:GrantRewards(tostring(player.UserId), {
            { type = "currency", amount = 250 },
        }, "daily_shop")
]]

local HttpService = game:GetService("HttpService")

local ShopGrantService = {}
ShopGrantService.__index = ShopGrantService

export type Endpoints = {
    GrantRewards: string?,
}

export type BackendClient = {
    Post: (self: any, path: string, body: any?, options: any?) -> any?,
}

function ShopGrantService.new(client: BackendClient, endpoints: Endpoints?)
    assert(client, "ShopGrantService requires a BackendClient instance")
    local self = setmetatable({}, ShopGrantService)
    self._client = client
    self._grantPath = endpoints and endpoints.GrantRewards or "/game/grant"
    return self
end

export type Reward = {
    type: string,
    amount: number?,
    item_id: string?,
}

function ShopGrantService:GrantRewards(robloxUserId: string, rewards: { Reward }, source: string?)
    assert(robloxUserId ~= "", "robloxUserId is required")
    assert(#rewards > 0, "at least one reward must be provided")

    local requestId = HttpService:GenerateGUID(false)
    local payload = {
        request_id = requestId,
        roblox_user_id = robloxUserId,
        rewards = rewards,
        source = source,
    }

    return self._client:Post(self._grantPath, payload, {
        IdempotencyKey = requestId,
    })
end

return ShopGrantService