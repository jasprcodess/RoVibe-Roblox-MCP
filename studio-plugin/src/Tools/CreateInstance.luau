local Main = script:FindFirstAncestor("MCPStudioPlugin")
local Types = require(Main.Types)
local resolveInstance = require(Main.Utils.ResolveInstance)
local getInstancePath = require(Main.Utils.GetInstancePath)

local HttpService = game:GetService("HttpService")

local function parseColor3(color: any): Color3?
	if typeof(color) == "table" then
		if color.R then
			return Color3.fromRGB(color.R, color.G or 0, color.B or 0)
		end
		if color.r then
			return Color3.fromRGB(color.r, color.g or 0, color.b or 0)
		end
	elseif typeof(color) == "string" then
		local ok, bc = pcall(function() return BrickColor.new(color) end)
		if ok then
			return bc.Color
		end
	end
	return nil
end

local function applyProperties(instance: Instance, properties: { [string]: any })
	for key, value in properties do
		local lowerKey = string.lower(key)

		if lowerKey == "position" and instance:IsA("BasePart") and typeof(value) == "table" then
			(instance :: BasePart).Position = Vector3.new(value.X or value.x or 0, value.Y or value.y or 0, value.Z or value.z or 0)
		elseif lowerKey == "size" and instance:IsA("BasePart") and typeof(value) == "table" then
			(instance :: BasePart).Size = Vector3.new(value.X or value.x or 4, value.Y or value.y or 1, value.Z or value.z or 2)
		elseif lowerKey == "color" and instance:IsA("BasePart") then
			local color = parseColor3(value)
			if color then
				(instance :: BasePart).Color = color
			end
		elseif lowerKey == "material" and instance:IsA("BasePart") and typeof(value) == "string" then
			local ok, mat = pcall(function()
				return (Enum.Material :: any)[value]
			end)
			if ok and mat then
				(instance :: BasePart).Material = mat
			end
		elseif lowerKey == "shape" and instance:IsA("Part") and typeof(value) == "string" then
			local ok, shape = pcall(function()
				return (Enum.PartType :: any)[value]
			end)
			if ok and shape then
				(instance :: Part).Shape = shape
			end
		elseif lowerKey == "source" and instance:IsA("LuaSourceContainer") and typeof(value) == "string" then
			(instance :: LuaSourceContainer).Source = value
		else
			local ok, err = pcall(function()
				(instance :: any)[key] = value
			end)
			if not ok then
				if typeof(value) == "table" and value.X ~= nil then
					pcall(function()
						(instance :: any)[key] = Vector3.new(value.X or 0, value.Y or 0, value.Z or 0)
					end)
				end
			end
		end
	end
end

local ALLOWED_CLASSES = {
	"Part", "WedgePart", "CornerWedgePart", "TrussPart", "SpawnLocation",
	"MeshPart", "UnionOperation", "NegateOperation",
	"Model", "Folder",
	"Script", "LocalScript", "ModuleScript",
	"PointLight", "SpotLight", "SurfaceLight",
	"Fire", "Smoke", "Sparkles", "ParticleEmitter",
	"Sound",
	"BillboardGui", "SurfaceGui", "ScreenGui",
	"Frame", "TextLabel", "TextButton", "TextBox", "ImageLabel", "ImageButton", "ScrollingFrame", "UIListLayout", "UIGridLayout", "UIPadding", "UICorner", "UIStroke", "UIAspectRatioConstraint", "UISizeConstraint",
	"Attachment", "Motor6D", "Weld", "WeldConstraint",
	"BodyVelocity", "BodyForce", "BodyPosition", "BodyGyro",
	"ClickDetector", "ProximityPrompt",
	"StringValue", "IntValue", "NumberValue", "BoolValue", "ObjectValue",
	"RemoteEvent", "RemoteFunction", "BindableEvent", "BindableFunction",
	"Configuration",
	"Camera",
	"Decal", "Texture",
	"Beam", "Trail",
}

local ALLOWED_SET = {}
for _, class in ALLOWED_CLASSES do
	ALLOWED_SET[class] = true
end

local function handleCreateInstance(args: Types.ToolArgs): string?
	if not args["CreateInstance"] then
		return nil
	end

	local createArgs: Types.CreateInstanceArgs = args["CreateInstance"]
	if type(createArgs.className) ~= "string" or createArgs.className == "" then
		error("Missing className in CreateInstance")
	end

	if not ALLOWED_SET[createArgs.className] then
		error("Cannot create instance of class '" .. createArgs.className .. "'. Use an allowed class like Part, Model, Script, etc.")
	end

	local parentPath = createArgs.parent or "Workspace"
	local parent = resolveInstance(parentPath)
	if not parent then
		error("Could not find parent at path: " .. parentPath)
	end

	local ok, instance = pcall(function()
		return Instance.new(createArgs.className)
	end)
	if not ok or not instance then
		error("Failed to create instance of class: " .. createArgs.className)
	end

	if createArgs.name and createArgs.name ~= "" then
		instance.Name = createArgs.name
	end

	if createArgs.properties then
		applyProperties(instance, createArgs.properties)
	end

	if instance:IsA("BasePart") then
		local wasAnchored = false
		if createArgs.properties then
			for key, _ in createArgs.properties do
				if string.lower(key) == "anchored" then
					wasAnchored = true
					break
				end
			end
		end
		if not wasAnchored then
			(instance :: BasePart).Anchored = true
		end
	end

	instance.Parent = parent

	local response = {
		created = true,
		name = instance.Name,
		className = instance.ClassName,
		path = getInstancePath(instance),
	}

	return HttpService:JSONEncode(response)
end

return handleCreateInstance :: Types.ToolFunction
