local Main = script:FindFirstAncestor("MCPStudioPlugin")
local ConsoleOutput = require(Main.Utils.ConsoleOutput)
local DataModelType = require(Main.Utils.DataModelType)
local GameStopUtil = require(Main.Utils.GameStopUtil)
local MockWebSocketService = require(Main.MockWebSocketService)
local PluginUtils = require(Main.Utils.PluginUtils)
local Types = require(Main.Types)

local ChangeHistoryService = game:GetService("ChangeHistoryService")
local HttpService = game:GetService("HttpService")
local RunService = game:GetService("RunService")
local StudioService = game:GetService("StudioService")

local URI = "http://localhost:44755"
local RECEIVE_ENDPOINT = "/request"
local SEND_ENDPOINT = "/response"

PluginUtils.plugin = plugin

local datamodelType = DataModelType.getDataModelType()

if datamodelType == "Server" then
	task.spawn(GameStopUtil.monitorForStopPlay)
end

if RunService:IsRunning() then
	return
end

local connMessageOut = ConsoleOutput.startListener()

local old_warn = warn
local function log(...)
	if false then
		old_warn(...)
	end
end

local function fetchToolDispatch()
	local dispatch = {}
	for _, tool in Main.Tools:GetChildren() do
		if tool:IsA("ModuleScript") then
			dispatch[tool.Name] = require(tool) :: Types.ToolFunction
		end
	end
	return dispatch
end

local toolDispatch = fetchToolDispatch()

local function connectWebSocket()
	local client = MockWebSocketService:CreateClient(URI)
	client:SetReceiveEndpoint(RECEIVE_ENDPOINT)
	client:SetSendEndpoint(SEND_ENDPOINT)

	client.Opened:Once(function()
		log("[MCP] Connection opened")
	end)

	client.Closed:Once(function()
		log("[MCP] Connection closed")
	end)

	client.MessageReceived:Connect(function(message)
		log("[MCP] Message received")

		local ok, err = pcall(function()
			local body = HttpService:JSONDecode(message)
			if not body or not body.id or not body.args then
				warn("[MCP] Invalid message received, missing id or args")
				return
			end

			local id: string = body.id
			local responseSent = false
			local function sendResponseOnce(response: string)
				if not responseSent then
					log("[MCP] Sending response:" .. response)
					responseSent = true
					client:Send({
						id = id,
						response = response,
					})
				end
			end

			local args: Types.ToolArgs = body.args
			local recording = ChangeHistoryService:TryBeginRecording("StudioMCP")

			local toolName = next(args)
			local handled = false

			if toolName then
				local tool = toolDispatch[toolName]
				if tool then
					local success, response = pcall(tool, args)
					if success and response then
						handled = true
						sendResponseOnce(response)
					elseif not success then
						handled = true
						sendResponseOnce("Error handling request: " .. tostring(response))
					end
				end
			end

			if recording then
				ChangeHistoryService:FinishRecording(recording, Enum.FinishRecordingOperation.Commit)
			end

			if not handled then
				sendResponseOnce("No tool found to handle request")
			end
			log("[MCP] Successfully handled request")
		end)

		if not ok then
			warn("[MCP] Error processing message: " .. tostring(err))
		end
	end)

	return client
end

local function getButtonImage()
	local ok, response = pcall(function()
		return StudioService:GetClassIcon("PackageLink").Image
	end)
	return ok and response or "rbxasset://textures/ui/GuiImagePlaceholder.png"
end

local currentClient: MockWebSocketService.MockWebSocketClient? = connectWebSocket()
print("The MCP Studio plugin is ready for prompts.")

local toolbar = plugin:CreateToolbar("MCP")
local toggleButton = toolbar:CreateButton("Toggle MCP", "Toggle connection to the server", getButtonImage())
toggleButton.ClickableWhenViewportHidden = true
toggleButton:SetActive(currentClient ~= nil)

toggleButton.Click:Connect(function()
	if not currentClient then
		currentClient = connectWebSocket()
		toggleButton:SetActive(true)
		print("The MCP Studio plugin is ready for prompts.")
	else
		currentClient:Close()
		currentClient = nil
		toggleButton:SetActive(false)
		print("The MCP Studio plugin is stopped.")
	end
end)

plugin.Unloading:Connect(function()
	connMessageOut:Disconnect()
	if currentClient then
		currentClient:Close()
		currentClient = nil
	end
end)
