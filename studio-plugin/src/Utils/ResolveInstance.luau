-- Resolves a dot-separated path like "Workspace.MyModel.Part" to an Instance.
-- Handles instance names containing dots by trying greedy matching first.
local function resolveInstance(path: string): Instance?
	local parts = string.split(path, ".")
	local current: Instance = game
	local i = 1

	while i <= #parts do
		-- Try greedy match: join remaining parts and see if a child exists with dots in the name
		local found = false
		for j = #parts, i, -1 do
			local candidate = table.concat(parts, ".", i, j)
			local child = current:FindFirstChild(candidate)
			if child then
				current = child
				i = j + 1
				found = true
				break
			end
		end
		if not found then
			return nil
		end
	end

	return current
end

return resolveInstance
