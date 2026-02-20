local Main = script:FindFirstAncestor("MCPStudioPlugin")
local Types = require(Main.Types)
local resolveInstance = require(Main.Utils.ResolveInstance)

local HttpService = game:GetService("HttpService")

local function serializeValue(value: any): any
	local t = typeof(value)

	if t == "string" or t == "number" or t == "boolean" then
		return value
	elseif t == "nil" then
		return nil
	elseif t == "Vector3" then
		return { X = value.X, Y = value.Y, Z = value.Z }
	elseif t == "Vector2" then
		return { X = value.X, Y = value.Y }
	elseif t == "CFrame" then
		return { Position = serializeValue(value.Position), LookVector = serializeValue(value.LookVector) }
	elseif t == "Color3" then
		return { R = math.round(value.R * 255), G = math.round(value.G * 255), B = math.round(value.B * 255) }
	elseif t == "BrickColor" then
		return value.Name
	elseif t == "UDim2" then
		return { X = { Scale = value.X.Scale, Offset = value.X.Offset }, Y = { Scale = value.Y.Scale, Offset = value.Y.Offset } }
	elseif t == "UDim" then
		return { Scale = value.Scale, Offset = value.Offset }
	elseif t == "EnumItem" then
		return tostring(value)
	elseif t == "Instance" then
		return value:GetFullName()
	elseif t == "Rect" then
		return { Min = serializeValue(value.Min), Max = serializeValue(value.Max) }
	elseif t == "NumberRange" then
		return { Min = value.Min, Max = value.Max }
	elseif t == "NumberSequence" or t == "ColorSequence" then
		return tostring(value)
	else
		return tostring(value)
	end
end

local CLASS_PROPERTIES: { [string]: { string } } = {
	Instance = { "Name", "ClassName", "Parent" },
	BasePart = { "Position", "Size", "CFrame", "Anchored", "CanCollide", "Transparency", "Color", "BrickColor", "Material", "Shape" },
	MeshPart = { "MeshId", "TextureID" },
	Model = { "PrimaryPart" },
	LuaSourceContainer = { "Source" },
	GuiObject = { "Position", "Size", "AnchorPoint", "Visible", "BackgroundColor3", "BackgroundTransparency", "BorderSizePixel", "LayoutOrder", "ZIndex" },
	TextLabel = { "Text", "TextColor3", "TextSize", "Font", "TextWrapped", "TextScaled" },
	TextButton = { "Text", "TextColor3", "TextSize", "Font" },
	TextBox = { "Text", "PlaceholderText", "TextColor3", "TextSize", "Font" },
	ImageLabel = { "Image", "ImageColor3", "ScaleType" },
	ImageButton = { "Image", "ImageColor3", "ScaleType" },
	Frame = {},
	Camera = { "CFrame", "FieldOfView", "CameraType" },
	Lighting = { "Ambient", "Brightness", "ClockTime", "FogEnd", "FogStart", "OutdoorAmbient" },
	PointLight = { "Brightness", "Color", "Range", "Enabled" },
	SpotLight = { "Brightness", "Color", "Range", "Angle", "Face", "Enabled" },
	SurfaceLight = { "Brightness", "Color", "Range", "Angle", "Face", "Enabled" },
	Sound = { "SoundId", "Volume", "Playing", "Looped", "PlaybackSpeed" },
	Humanoid = { "Health", "MaxHealth", "WalkSpeed", "JumpPower" },
	Tool = { "ToolTip", "RequiresHandle", "CanBeDropped" },
}

local function getPropertiesForInstance(instance: Instance): { [string]: any }
	local properties: { [string]: any } = {}

	for _, prop in CLASS_PROPERTIES.Instance do
		local ok, val = pcall(function() return (instance :: any)[prop] end)
		if ok then
			properties[prop] = serializeValue(val)
		end
	end

	for className, props in CLASS_PROPERTIES do
		if className ~= "Instance" and instance:IsA(className) then
			for _, prop in props do
				local ok, val = pcall(function() return (instance :: any)[prop] end)
				if ok then
					properties[prop] = serializeValue(val)
				end
			end
		end
	end

	return properties
end

local function handleGetProperties(args: Types.ToolArgs): string?
	if not args["GetProperties"] then
		return nil
	end

	local getPropertiesArgs: Types.GetPropertiesArgs = args["GetProperties"]
	if type(getPropertiesArgs.path) ~= "string" or getPropertiesArgs.path == "" then
		error("Missing path in GetProperties")
	end

	local instance = resolveInstance(getPropertiesArgs.path)
	if not instance then
		error("Could not find instance at path: " .. getPropertiesArgs.path)
	end

	local properties = getPropertiesForInstance(instance)

	local response = {
		path = getPropertiesArgs.path,
		className = instance.ClassName,
		properties = properties,
		childCount = #instance:GetChildren(),
	}

	return HttpService:JSONEncode(response)
end

return handleGetProperties :: Types.ToolFunction
