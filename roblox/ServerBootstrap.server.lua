--!strict
--[[
    Example Script meant to live under ServerScriptService.
    Demonstrates how to instantiate the helper modules and react to game events.
]]

local Players = game:GetService("Players")
local ServerStorage = game:GetService("ServerStorage")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

type Player = Players.Player

-- Adjust these paths to match the folders you create in Roblox Studio.
local Config = require(ServerStorage.Backend.BackendConfig)
local BackendClient = require(ServerStorage.Backend.BackendClient)
local VerificationService = require(ServerStorage.Backend.VerificationService)
local ShopGrantService = require(ServerStorage.Backend.ShopGrantService)

local client = BackendClient.new(Config)
local verifier = VerificationService.new(client, Config.Endpoints)
local grants = ShopGrantService.new(client, Config.Endpoints)

local GrantPurchaseEvent = ReplicatedStorage:FindFirstChild("GrantPurchase")

local function handlePlayerVerification(player: Player)
    local enteredCode = player:GetAttribute("VerificationCode")
    if type(enteredCode) ~= "string" or enteredCode == "" then
        return
    end

    local ok, result = pcall(function()
        return verifier:CheckCode(tostring(player.UserId), enteredCode)
    end)

    if not ok then
        warn("Verification request failed", result)
        return
    end

    if result and (result.status == "verified" or result.verified == true) then
        player:SetAttribute("Verified", true)
    else
        player:SetAttribute("Verified", false)
    end
end

local function handleGrantRequest(player: Player, grantPayload: any)
    local ok, response = pcall(function()
        return grants:GrantRewards(tostring(player.UserId), grantPayload.rewards, grantPayload.source)
    end)

    if not ok then
        warn("Grant request failed", response)
        return
    end

    -- Use the response data (e.g., status, request_id) to update the player state.
    player:SetAttribute("LastGrantRequestId", response and response.request_id or "")
end

Players.PlayerAdded:Connect(function(player)
    task.defer(handlePlayerVerification, player)
end)

if GrantPurchaseEvent and GrantPurchaseEvent:IsA("RemoteEvent") then
    GrantPurchaseEvent.OnServerEvent:Connect(function(player, payload)
        if typeof(payload) ~= "table" or typeof(payload.rewards) ~= "table" then
            warn("Invalid grant payload from client")
            return
        end
        handleGrantRequest(player, payload)
    end)
end