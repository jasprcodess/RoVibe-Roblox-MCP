local LogService = game:GetService("LogService")

local DEBUG_TOOL_MAX_OUTPUT = 10000

local MESSAGE_TYPE_PREFIX = {
	[Enum.MessageType.MessageOutput] = "",
	[Enum.MessageType.MessageInfo] = "[INFO] ",
	[Enum.MessageType.MessageWarning] = "[WARN] ",
	[Enum.MessageType.MessageError] = "[ERROR] ",
}

local ConsoleOutput = {
	outputMessage = "",
	_parts = {} :: { string },
	_length = 0,
}

function ConsoleOutput.startListener()
	local connMessageOut = LogService.MessageOut:Connect(function(message: string, messageType: Enum.MessageType)
		local prefix = MESSAGE_TYPE_PREFIX[messageType] or ""
		local line = prefix .. message
		local newLen = ConsoleOutput._length + #line + 1
		if newLen <= DEBUG_TOOL_MAX_OUTPUT then
			table.insert(ConsoleOutput._parts, line)
			ConsoleOutput._length = newLen
		end
	end)
	return connMessageOut
end

function ConsoleOutput.flush(): string
	local result = table.concat(ConsoleOutput._parts, "\n")
	ConsoleOutput._parts = {}
	ConsoleOutput._length = 0
	ConsoleOutput.outputMessage = ""
	return result
end

return ConsoleOutput
