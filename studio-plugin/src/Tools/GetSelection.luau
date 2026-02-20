local Main = script:FindFirstAncestor("MCPStudioPlugin")
local Types = require(Main.Types)
local getInstancePath = require(Main.Utils.GetInstancePath)

local HttpService = game:GetService("HttpService")
local Selection = game:GetService("Selection")

local function serializeValue(value: any): any
	local t = typeof(value)
	if t == "Vector3" then
		return { X = math.round(value.X * 100) / 100, Y = math.round(value.Y * 100) / 100, Z = math.round(value.Z * 100) / 100 }
	elseif t == "Color3" then
		return { R = math.round(value.R * 255), G = math.round(value.G * 255), B = math.round(value.B * 255) }
	elseif t == "EnumItem" then
		return tostring(value)
	elseif t == "Instance" then
		return value:GetFullName()
	else
		return tostring(value)
	end
end

local function getSelectionInfo(instance: Instance): { [string]: any }
	local info: { [string]: any } = {
		name = instance.Name,
		className = instance.ClassName,
		path = getInstancePath(instance),
		childCount = #instance:GetChildren(),
	}

	if instance:IsA("BasePart") then
		local part = instance :: BasePart
		info.position = serializeValue(part.Position)
		info.size = serializeValue(part.Size)
		info.color = serializeValue(part.Color)
		info.material = tostring(part.Material)
		info.transparency = part.Transparency
		info.anchored = part.Anchored
	elseif instance:IsA("Model") then
		local model = instance :: Model
		if model.PrimaryPart then
			info.primaryPartPosition = serializeValue(model.PrimaryPart.Position)
		end
		info.descendantCount = #model:GetDescendants()
	elseif instance:IsA("LuaSourceContainer") then
		info.hasSource = true
		info.sourceLength = #(instance :: LuaSourceContainer).Source
	end

	return info
end

local function handleGetSelection(args: Types.ToolArgs): string?
	if not args["GetSelection"] then
		return nil
	end

	local selected = Selection:Get()

	local items = {}
	for _, instance in selected do
		table.insert(items, getSelectionInfo(instance))
	end

	local response = {
		count = #items,
		items = items,
	}

	return HttpService:JSONEncode(response)
end

return handleGetSelection :: Types.ToolFunction
