local Main = script:FindFirstAncestor("MCPStudioPlugin")
local Types = require(Main.Types)
local resolveInstance = require(Main.Utils.ResolveInstance)
local getInstancePath = require(Main.Utils.GetInstancePath)

local HttpService = game:GetService("HttpService")

local MAX_DEPTH = 10
local MAX_INSTANCES = 5000

local function serializeInstance(instance: Instance, depth: number, maxDepth: number, count: { n: number }): any?
	if count.n >= MAX_INSTANCES then
		return nil
	end
	count.n += 1

	local info: { [string]: any } = {
		Name = instance.Name,
		ClassName = instance.ClassName,
		Path = getInstancePath(instance),
	}

	if instance:IsA("BasePart") then
		local part = instance :: BasePart
		info.Position = { X = math.round(part.Position.X * 100) / 100, Y = math.round(part.Position.Y * 100) / 100, Z = math.round(part.Position.Z * 100) / 100 }
		info.Size = { X = math.round(part.Size.X * 100) / 100, Y = math.round(part.Size.Y * 100) / 100, Z = math.round(part.Size.Z * 100) / 100 }
		info.Orientation = { X = math.round(part.Orientation.X * 10) / 10, Y = math.round(part.Orientation.Y * 10) / 10, Z = math.round(part.Orientation.Z * 10) / 10 }
		info.Color = { R = math.round(part.Color.R * 255), G = math.round(part.Color.G * 255), B = math.round(part.Color.B * 255) }
		info.Material = tostring(part.Material):gsub("Enum.Material.", "")
		info.Transparency = part.Transparency
		info.Anchored = part.Anchored
		if part:IsA("Part") then
			info.Shape = tostring((part :: Part).Shape):gsub("Enum.PartType.", "")
		end
	elseif instance:IsA("Model") then
		local ok, cf, size = pcall(function()
			return instance:GetBoundingBox()
		end)
		if ok and cf and size then
			info.BoundingBox = {
				Center = { X = math.round(cf.Position.X * 100) / 100, Y = math.round(cf.Position.Y * 100) / 100, Z = math.round(cf.Position.Z * 100) / 100 },
				Size = { X = math.round(size.X * 100) / 100, Y = math.round(size.Y * 100) / 100, Z = math.round(size.Z * 100) / 100 },
			}
		end
	elseif instance:IsA("LuaSourceContainer") then
		info.HasSource = true
	end

	if depth < maxDepth then
		local children = instance:GetChildren()
		if #children > 0 then
			local childrenData = {}
			for _, child in children do
				local childInfo = serializeInstance(child, depth + 1, maxDepth, count)
				if childInfo then
					table.insert(childrenData, childInfo)
				end
			end
			if #childrenData > 0 then
				info.Children = childrenData
			end
		end
	else
		local numDescendants = #instance:GetChildren()
		if numDescendants > 0 then
			info.ChildCount = numDescendants
			info.Truncated = true
		end
	end

	return info
end

local function handleGetDescendants(args: Types.ToolArgs): string?
	if not args["GetDescendants"] then
		return nil
	end

	local getDescendantsArgs: Types.GetDescendantsArgs = args["GetDescendants"]

	local path = getDescendantsArgs.path or "Workspace"
	local depth = getDescendantsArgs.depth or 3

	if depth < 1 then depth = 1 end
	if depth > MAX_DEPTH then depth = MAX_DEPTH end

	local root = resolveInstance(path)
	if not root then
		error("Could not find instance at path: " .. path)
	end

	local count = { n = 0 }
	local result = serializeInstance(root, 0, depth, count)

	local response = {
		root = result,
		totalSerialized = count.n,
		truncated = count.n >= MAX_INSTANCES,
	}

	return HttpService:JSONEncode(response)
end

return handleGetDescendants :: Types.ToolFunction
