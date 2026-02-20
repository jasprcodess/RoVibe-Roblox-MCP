export type InsertModelArgs = {
	query: string,
}

export type RunCodeArgs = {
	command: string,
}

export type TestMode = "start_play" | "run_server"

export type StartStopPlayMode = TestMode | "stop"

export type StartStopPlayArgs = {
	mode: StartStopPlayMode,
}

export type RunScriptInPlayModeArgs = {
	code: string,
	timeout: number?,
	mode: TestMode,
}

export type GetDescendantsArgs = {
	path: string?,
	depth: number?,
}

export type ReadScriptArgs = {
	path: string,
}

export type GetPropertiesArgs = {
	path: string,
}

export type CreateInstanceArgs = {
	className: string,
	parent: string?,
	name: string?,
	properties: { [string]: any }?,
}

export type ToolArgs =
	{}
	| { InsertModel: InsertModelArgs }
	| { RunCode: RunCodeArgs }
	| { StartStopPlay: StartStopPlayArgs }
	| { RunScriptInPlayMode: RunScriptInPlayModeArgs }
	| { GetConsoleOutput: {} }
	| { GetStudioMode: {} }
	| { GetDescendants: GetDescendantsArgs }
	| { ReadScript: ReadScriptArgs }
	| { GetProperties: GetPropertiesArgs }
	| { GetSelection: {} }
	| { CreateInstance: CreateInstanceArgs }

export type ToolFunction = (ToolArgs) -> string?

return {}
