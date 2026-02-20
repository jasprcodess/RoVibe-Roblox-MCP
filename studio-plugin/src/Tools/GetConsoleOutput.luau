local Main = script:FindFirstAncestor("MCPStudioPlugin")
local Types = require(Main.Types)

local ConsoleOutput = require(Main.Utils.ConsoleOutput)

local function handleGetConsoleOutput(args: Types.ToolArgs): string?
	if not args["GetConsoleOutput"] then
		return nil
	end

	return ConsoleOutput.flush()
end

return handleGetConsoleOutput :: Types.ToolFunction
