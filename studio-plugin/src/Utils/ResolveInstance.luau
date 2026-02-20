local function resolveInstance(path: string): Instance?
	local parts = string.split(path, ".")
	local current: Instance = game

	for _, part in parts do
		local child = current:FindFirstChild(part)
		if not child then
			return nil
		end
		current = child
	end

	return current
end

return resolveInstance
