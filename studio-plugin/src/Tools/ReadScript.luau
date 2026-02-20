local Main = script:FindFirstAncestor("MCPStudioPlugin")
local Types = require(Main.Types)
local resolveInstance = require(Main.Utils.ResolveInstance)

local HttpService = game:GetService("HttpService")

local function handleReadScript(args: Types.ToolArgs): string?
	if not args["ReadScript"] then
		return nil
	end

	local readScriptArgs: Types.ReadScriptArgs = args["ReadScript"]
	if type(readScriptArgs.path) ~= "string" or readScriptArgs.path == "" then
		error("Missing path in ReadScript")
	end

	local instance = resolveInstance(readScriptArgs.path)
	if not instance then
		error("Could not find instance at path: " .. readScriptArgs.path)
	end

	if not instance:IsA("LuaSourceContainer") then
		error("Instance at path is not a script (it's a " .. instance.ClassName .. "): " .. readScriptArgs.path)
	end

	local scriptInstance = instance :: LuaSourceContainer

	local response = {
		path = readScriptArgs.path,
		className = instance.ClassName,
		name = instance.Name,
		source = scriptInstance.Source,
		lineCount = select(2, string.gsub(scriptInstance.Source, "\n", "")) + 1,
	}

	return HttpService:JSONEncode(response)
end

return handleReadScript :: Types.ToolFunction
