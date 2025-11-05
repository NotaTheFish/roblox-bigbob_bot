--!strict
--[[
    Minimal HTTP client for talking to the FastAPI backend from Roblox.

    Usage:
        local Config = require(ServerStorage.BackendConfig)
        local BackendClient = require(ServerStorage.BackendClient)
        local client = BackendClient.new(Config)
        local response = client:Post(Config.Endpoints.ProgressPush, {
            roblox_user_id = tostring(player.UserId),
            progress = {...},
        })
]]

local HttpService = game:GetService("HttpService")

export type Config = {
    BaseUrl: string,
    HmacSecret: string,
    DefaultHeaders: { [string]: string }?,
    Timeout: number?,
    Endpoints: { [string]: string }?,
}

export type RequestOptions = {
    IdempotencyKey: string?,
    Headers: { [string]: string }?,
    Timeout: number?,
}

local BackendClient = {}
BackendClient.__index = BackendClient

local function ensureCryptAvailable()
    if typeof(crypt) ~= "table" or not crypt.hash or not crypt.hash.hmac then
        error("The `crypt` library is not available. Enable `Allow HTTP Requests` and run on the server.")
    end
end

local function sanitizePath(path: string): string
    if string.sub(path, 1, 1) ~= "/" then
        path = "/" .. path
    end
    return path
end

function BackendClient.new(config: Config)
    assert(config, "BackendClient.new requires a configuration table")
    assert(config.BaseUrl, "BackendConfig.BaseUrl is required")
    assert(config.HmacSecret, "BackendConfig.HmacSecret is required")

    ensureCryptAvailable()

    local self = setmetatable({}, BackendClient)
    self._baseUrl = string.gsub(config.BaseUrl, "/+$", "")
    self._hmacSecret = config.HmacSecret
    self._timeout = config.Timeout or 10
    self._defaultHeaders = config.DefaultHeaders or {}
    self.Endpoints = config.Endpoints or {}
    return self
end

function BackendClient:_makeHeaders(body: string, customHeaders: { [string]: string }?, idempotencyKey: string?)
    local signature = crypt.hash.hmac("sha256", body, self._hmacSecret)

    local headers = {
        ["Content-Type"] = "application/json",
        ["X-Signature"] = signature,
        ["Idempotency-Key"] = idempotencyKey or HttpService:GenerateGUID(false),
    }

    for key, value in pairs(self._defaultHeaders) do
        headers[key] = value
    end

    if customHeaders then
        for key, value in pairs(customHeaders) do
            headers[key] = value
        end
    end

    return headers
end

function BackendClient:_request(method: string, path: string, bodyTable: any?, options: RequestOptions?)
    options = options or {}
    local body = ""
    if bodyTable ~= nil then
        body = HttpService:JSONEncode(bodyTable)
    end

    local headers = self:_makeHeaders(body, options.Headers, options.IdempotencyKey)
    local url = self._baseUrl .. sanitizePath(path)

    local previousTimeout = HttpService.HttpTimeout
    HttpService.HttpTimeout = options.Timeout or self._timeout

    local success, response = pcall(function()
        return HttpService:RequestAsync({
            Url = url,
            Method = method,
            Body = body ~= "" and body or nil,
            Headers = headers,
        })
    end)

    HttpService.HttpTimeout = previousTimeout

    if not success then
        error(string.format("Request to %s failed: %s", url, tostring(response)))
    end

    if not response.Success then
        error(string.format("Backend responded with HTTP %d: %s", response.StatusCode, response.Body))
    end

    if response.Body == nil or response.Body == "" then
        return nil
    end

    local ok, decoded = pcall(function()
        return HttpService:JSONDecode(response.Body)
    end)

    if not ok then
        error(string.format("Failed to parse JSON response from %s: %s", url, tostring(decoded)))
    end

    return decoded
end

function BackendClient:Get(path: string, options: RequestOptions?)
    return self:_request("GET", path, nil, options)
end

function BackendClient:Post(path: string, body: any?, options: RequestOptions?)
    return self:_request("POST", path, body, options)
end

function BackendClient:Put(path: string, body: any?, options: RequestOptions?)
    return self:_request("PUT", path, body, options)
end

function BackendClient:Patch(path: string, body: any?, options: RequestOptions?)
    return self:_request("PATCH", path, body, options)
end

function BackendClient:Delete(path: string, options: RequestOptions?)
    return self:_request("DELETE", path, nil, options)
end

return BackendClient