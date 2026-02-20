local Main = script:FindFirstAncestor("MCPStudioPlugin")
local Types = require(Main.Types)

local HttpService = game:GetService("HttpService")

local TRACKED_PROPS = {
	"Name", "Position", "Size", "CFrame", "Anchored", "Transparency",
	"Color", "BrickColor", "Material", "Shape", "CanCollide",
	"Source", "Text", "TextSize", "TextColor3", "BackgroundColor3",
	"Visible", "Enabled", "Value", "Parent",
}

local RUN_CODE_TIMEOUT = 30

local function readProp(inst: Instance, prop: string): (boolean, any)
	return pcall(function()
		return (inst :: any)[prop]
	end)
end

local function propToString(value: any): string
	if typeof(value) == "Vector3" then
		return string.format("(%.1f, %.1f, %.1f)", value.X, value.Y, value.Z)
	elseif typeof(value) == "CFrame" then
		local p = value.Position
		return string.format("CFrame(%.1f, %.1f, %.1f)", p.X, p.Y, p.Z)
	elseif typeof(value) == "Color3" then
		return string.format("(%d, %d, %d)", math.round(value.R * 255), math.round(value.G * 255), math.round(value.B * 255))
	elseif typeof(value) == "BrickColor" then
		return value.Name
	elseif typeof(value) == "EnumItem" then
		return tostring(value)
	elseif typeof(value) == "Instance" then
		return value:GetFullName()
	elseif typeof(value) == "boolean" then
		return tostring(value)
	elseif typeof(value) == "number" then
		if value == math.floor(value) then
			return tostring(value)
		end
		return string.format("%.2f", value)
	elseif typeof(value) == "string" then
		if #value > 80 then
			return '"' .. string.sub(value, 1, 77) .. '..."'
		end
		return '"' .. value .. '"'
	end
	return tostring(value)
end

local function snapshotProps(inst: Instance): { [string]: string }
	local snap = {}
	for _, prop in TRACKED_PROPS do
		local ok, val = readProp(inst, prop)
		if ok then
			snap[prop] = propToString(val)
		end
	end
	return snap
end

local function runCodeWithOutput(command: string): (string, boolean)
	local parts = {}

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
		table.insert(parts, header .. " " .. table.concat(strResults, "\t"))
	end

	local timedOut = false

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

		-- Run with timeout
		local finished = false
		local results = {}

		local coro = coroutine.create(function()
			results = table.pack(chunk())
			finished = true
		end)

		local startTime = os.clock()
		local ok, err = coroutine.resume(coro)

		-- If the coroutine yielded (e.g. task.wait), keep resuming until timeout
		while coroutine.status(coro) == "suspended" do
			if os.clock() - startTime > RUN_CODE_TIMEOUT then
				timedOut = true
				addToOutput("[TIMEOUT]", string.format("Code execution exceeded %ds limit", RUN_CODE_TIMEOUT))
				break
			end
			task.wait()
			ok, err = coroutine.resume(coro)
		end

		if not ok and not timedOut then
			error(err)
		end

		if finished and #results > 0 then
			addToOutput("[RETURNED RESULTS]", table.unpack(results))
		end

		return results
	end

	local ok, errorMessage = pcall(executeCode)
	if not ok and not timedOut then
		addToOutput("[ERROR]", errorMessage)
	end

	return table.concat(parts, "\n"), timedOut
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

	-- Snapshot instances
	local before = snapshotWorkspace()

	-- Snapshot string representations of properties for existing instances
	local propsBefore: { [Instance]: { [string]: string } } = {}
	for inst in before do
		propsBefore[inst] = snapshotProps(inst)
	end

	local output, timedOut = runCodeWithOutput(runCodeArgs.command)

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

	-- Detect property changes on existing instances
	local changes = {}
	for inst in after do
		if before[inst] then
			local oldSnap = propsBefore[inst]
			if oldSnap then
				for _, prop in TRACKED_PROPS do
					local oldStr = oldSnap[prop]
					if oldStr ~= nil then
						local okNew, newVal = readProp(inst, prop)
						if okNew then
							local newStr = propToString(newVal)
							if oldStr ~= newStr then
								table.insert(changes, {
									instance = inst,
									property = prop,
									oldStr = oldStr,
									newStr = newStr,
								})
							end
						end
					end
				end
			end
		end
	end

	-- Build scene changes using table.insert for efficiency
	local changeParts = {}

	table.insert(changeParts, "\n[SCENE CHANGES]")

	if timedOut then
		table.insert(changeParts, "[WARNING] Code was terminated due to timeout. Changes below reflect partial execution.")
	end

	if #created > 0 then
		table.insert(changeParts, string.format("Created %d instance(s):", #created))
		for i = 1, math.min(#created, 50) do
			local inst = created[i]
			table.insert(changeParts, describeInstance(inst))
			-- Show key properties of new instances
			local newSnap = snapshotProps(inst)
			for _, prop in TRACKED_PROPS do
				if newSnap[prop] ~= nil and prop ~= "Name" and prop ~= "Parent" then
					table.insert(changeParts, string.format("    .%s = %s", prop, newSnap[prop]))
				end
			end
		end
		if #created > 50 then
			table.insert(changeParts, string.format("  ... and %d more", #created - 50))
		end
	end

	if removed > 0 then
		table.insert(changeParts, string.format("Removed %d instance(s)", removed))
	end

	if #changes > 0 then
		table.insert(changeParts, string.format("Modified %d property(s):", #changes))
		for i = 1, math.min(#changes, 100) do
			local c = changes[i]
			local path = c.instance:GetFullName()
			table.insert(changeParts, string.format("  %s.%s: %s → %s",
				path, c.property, c.oldStr, c.newStr
			))
		end
		if #changes > 100 then
			table.insert(changeParts, string.format("  ... and %d more changes", #changes - 100))
		end
	end

	if #created == 0 and removed == 0 and #changes == 0 then
		table.insert(changeParts, "No changes detected.")
	end

	return output .. "\n" .. table.concat(changeParts, "\n")
end

return handleRunCode :: Types.ToolFunction
