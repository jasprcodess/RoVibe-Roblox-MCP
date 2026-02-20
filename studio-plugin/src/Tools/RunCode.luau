local Main = script:FindFirstAncestor("MCPStudioPlugin")
local Types = require(Main.Types)

local HttpService = game:GetService("HttpService")

local function runCodeWithOutput(command: string): string
	local output = ""

	local function getTableType(arg)
		local hasArray = false
		local hasTable = false
		for key, _value in arg do
			if typeof(key) == "number" then
				hasArray = true
			else
				hasTable = true
			end
			if hasArray and hasTable then
				break
			end
		end
		return hasArray, hasTable
	end

	local function serializeTable(arg): any
		if typeof(arg) == "table" then
			local _, isTable = getTableType(arg)

			local newArg = {}
			for key, value in arg do
				local newKey = serializeTable(key)
				newArg[if isTable then tostring(newKey) else newKey] = serializeTable(value)
			end
			return newArg
		elseif type(arg) == "userdata" then
			return tostring(arg) or "UNABLE_TO_SERIALIZE"
		end
		return arg
	end

	local function deepClone(t, cache)
		local clone = {}
		cache[t] = clone
		for key, value in t do
			local newKey = key
			if typeof(key) == "table" then
				if not cache[key] then
					deepClone(key, cache)
				end
				newKey = cache[key]
			end

			local newValue = value
			if typeof(value) == "table" then
				if not cache[value] then
					deepClone(value, cache)
				end
				newValue = cache[value]
			end

			clone[newKey] = newValue
		end
		return clone
	end

	local function toStrTable(t: { any }): { string }
		local clonedTable = deepClone(t, {})
		local strTable = table.create(#clonedTable)
		for i, arg in clonedTable do
			local serializedArg = serializeTable(arg)
			strTable[i] = if typeof(serializedArg) == "table"
				then HttpService:JSONEncode(serializedArg)
				else serializedArg
		end
		return strTable
	end

	local function addToOutput(header: string, ...)
		local strResults = toStrTable(table.pack(...))
		output ..= header .. " " .. table.concat(strResults, "\t") .. "\n"
	end

	local function executeCode()
		local chunk, parseError = loadstring(command)
		if not chunk then
			addToOutput("[SYNTAX ERROR]", parseError or "Unknown parse error")
			return {}
		end
		chunk = chunk :: any
		local chunkfenv = getfenv(chunk)

		local oldPrint = print
		chunkfenv.print = function(...)
			oldPrint(...)
			addToOutput("[OUTPUT]", ...)
		end

		local oldWarn = warn
		chunkfenv.warn = function(...)
			oldWarn(...)
			addToOutput("[WARNING]", ...)
		end

		local oldError = error
		chunkfenv.error = function(...)
			addToOutput("[ERROR]", ...)
			oldError(...)
		end

		local results = table.pack(chunk())
		if #results > 0 then
			addToOutput("[RETURNED RESULTS]", table.unpack(results))
		end

		return results
	end

	local ok, errorMessage = pcall(executeCode)
	if not ok then
		addToOutput("[UNEXPECTED ERROR]", errorMessage)
	end

	return output
end

local function snapshotWorkspace(): { [Instance]: true }
	local snap = {}
	for _, desc in game.Workspace:GetDescendants() do
		snap[desc] = true
	end
	return snap
end

local function describeInstance(inst: Instance): string
	local ok, desc = pcall(function()
		if inst:IsA("BasePart") then
			local p = (inst :: BasePart).Position
			local s = (inst :: BasePart).Size
			return string.format(
				'  %s "%s" at (%.1f, %.1f, %.1f) size (%.1f, %.1f, %.1f)',
				inst.ClassName, inst.Name, p.X, p.Y, p.Z, s.X, s.Y, s.Z
			)
		elseif inst:IsA("Model") then
			return string.format('  Model "%s" with %d descendants', inst.Name, #inst:GetDescendants())
		else
			return string.format('  %s "%s"', inst.ClassName, inst.Name)
		end
	end)
	return if ok then desc else string.format('  [instance] "%s"', tostring(inst))
end

local function handleRunCode(args: Types.ToolArgs): string?
	if not args["RunCode"] then
		return nil
	end

	local runCodeArgs: Types.RunCodeArgs = args["RunCode"]
	if type(runCodeArgs.command) ~= "string" then
		error("Missing command in RunCode")
	end

	local before = snapshotWorkspace()

	local output = runCodeWithOutput(runCodeArgs.command)

	local after = snapshotWorkspace()
	local created = {}
	local removed = 0

	for inst in after do
		if not before[inst] then
			table.insert(created, inst)
		end
	end
	for inst in before do
		if not after[inst] then
			removed += 1
		end
	end

	if #created > 0 or removed > 0 then
		output ..= "\n[SCENE CHANGES]\n"
		if #created > 0 then
			output ..= string.format("Created %d instance(s):\n", #created)
			local limit = math.min(#created, 30)
			for i = 1, limit do
				output ..= describeInstance(created[i]) .. "\n"
			end
			if #created > limit then
				output ..= string.format("  ... and %d more\n", #created - limit)
			end
		end
		if removed > 0 then
			output ..= string.format("Removed %d instance(s)\n", removed)
		end
	end

	return output
end

return handleRunCode :: Types.ToolFunction
