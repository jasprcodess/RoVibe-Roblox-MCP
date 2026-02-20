local LogService = game:GetService("LogService")

local DEBUG_TOOL_MAX_OUTPUT = 10000

local ConsoleOutput = {
	outputMessage = "",
}

function ConsoleOutput.startListener()
	local connMessageOut = LogService.MessageOut:Connect(function(message: string, _: Enum.MessageType)
		local separator = if #ConsoleOutput.outputMessage > 0 then 1 else 0
		if #ConsoleOutput.outputMessage + separator + #message <= DEBUG_TOOL_MAX_OUTPUT then
			if #ConsoleOutput.outputMessage == 0 then
				ConsoleOutput.outputMessage = message
			else
				ConsoleOutput.outputMessage = ConsoleOutput.outputMessage .. "\n" .. message
			end
		end
	end)
	return connMessageOut
end

return ConsoleOutput
