use crate::error::Result;
use axum::http::StatusCode;
use axum::response::IntoResponse;
use axum::{extract::State, Json};
use color_eyre::eyre::{Error, OptionExt};
use rmcp::{
    handler::server::{router::tool::ToolRouter, wrapper::Parameters},
    model::{
        CallToolResult, Content, Implementation, ProtocolVersion, ServerCapabilities, ServerInfo,
    },
    schemars, tool, tool_handler, tool_router, ErrorData, ServerHandler,
};
use serde::{Deserialize, Serialize};
use std::collections::{HashMap, VecDeque};
use std::sync::Arc;
use tokio::sync::oneshot::Receiver;
use tokio::sync::{mpsc, watch, Mutex};
use tokio::time::Duration;
use uuid::Uuid;

pub const STUDIO_PLUGIN_PORT: u16 = 44755;
const LONG_POLL_DURATION: Duration = Duration::from_secs(15);
const TOOL_RESPONSE_TIMEOUT: Duration = Duration::from_secs(120);

#[derive(Deserialize, Serialize, Clone, Debug)]
pub struct ToolArguments {
    args: ToolArgumentValues,
    id: Option<Uuid>,
}

#[derive(Deserialize, Serialize, Clone, Debug)]
pub struct RunCommandResponse {
    response: String,
    id: Uuid,
}

pub struct AppState {
    process_queue: VecDeque<ToolArguments>,
    output_map: HashMap<Uuid, mpsc::UnboundedSender<Result<String>>>,
    waiter: watch::Receiver<()>,
    trigger: watch::Sender<()>,
}
pub type PackedState = Arc<Mutex<AppState>>;

impl AppState {
    pub fn new() -> Self {
        let (trigger, waiter) = watch::channel(());
        Self {
            process_queue: VecDeque::new(),
            output_map: HashMap::new(),
            waiter,
            trigger,
        }
    }
}

impl ToolArguments {
    fn new(args: ToolArgumentValues) -> (Self, Uuid) {
        Self { args, id: None }.with_id()
    }
    fn with_id(self) -> (Self, Uuid) {
        let id = Uuid::new_v4();
        (
            Self {
                args: self.args,
                id: Some(id),
            },
            id,
        )
    }
}
#[derive(Clone)]
pub struct RoVibeServer {
    state: PackedState,
    trigger: watch::Sender<()>,
    tool_router: ToolRouter<Self>,
}

#[tool_handler]
impl ServerHandler for RoVibeServer {
    fn get_info(&self) -> ServerInfo {
        ServerInfo {
            protocol_version: ProtocolVersion::LATEST,
            capabilities: ServerCapabilities::builder().enable_tools().build(),
            server_info: Implementation {
                name: "RoVibe_Studio".to_string(),
                version: env!("CARGO_PKG_VERSION").to_string(),
                title: Some("RoVibe Roblox MCP Server".to_string()),
                icons: None,
                website_url: None,
            },
            instructions: Some(r#"
# RoVibe Roblox MCP - Building Guide

## Coordinate System
- Roblox uses (X, Y, Z) where Y is UP. Ground level is Y=0.
- Position is the CENTER of a part. A Part at Position(0, 5, 0) with Size(4, 10, 4) has its bottom at Y=0 and top at Y=10.
- To place a part ON the ground: Position.Y = Size.Y / 2
- To stack part B on top of part A: B.Position.Y = A.Position.Y + A.Size.Y/2 + B.Size.Y/2

## Building Strategy
1. ALWAYS call get_descendants first to see what already exists before building
2. Use run_code for bulk operations - create multiple parts in a single Luau script
3. Group related parts into Models using Instance.new("Model")
4. Set Model.PrimaryPart for easy repositioning with Model:PivotTo()
5. Anchor all parts (Anchored = true) unless they need physics
6. Use CFrame for rotation: part.CFrame = CFrame.new(pos) * CFrame.Angles(rx, ry, rz)

## Common Building Patterns (use with run_code)
- Wall: Part with Size(length, height, thickness), e.g. Size(20, 10, 1)
- Floor: Part with Size(length, thickness, width), e.g. Size(20, 1, 20)
- Door opening: Create two wall segments with a gap, plus a top piece
- Window: Transparent Part (Transparency=0.5) inset into a wall gap
- Cylinder: Part with Shape="Cylinder", Size(diameter, length, diameter), rotated with CFrame

## Spatial Math Tips
- Parts touching: gap = 0 means adjacent edges meet. For two parts side by side along X: part2.X = part1.X + part1.Size.X/2 + part2.Size.X/2
- Rotation: CFrame.Angles uses radians. 90° = math.pi/2, 45° = math.pi/4
- To rotate around Y axis (turn left/right): CFrame.Angles(0, angle, 0)

## Materials & Colors
- Materials: Plastic, Wood, Brick, Concrete, Metal, Glass, SmoothPlastic, Neon, Foil, Granite, Marble, Slate, Sand, Ice, Fabric, Cobblestone, DiamondPlate, CorrodedMetal, WoodPlanks, Grass
- Colors: Use Color3.fromRGB(r, g, b) or BrickColor names

## Tools Available
- get_descendants: Explore instance hierarchy. ALWAYS use this first to understand the scene.
- get_properties: Inspect a specific instance's properties.
- get_selection: See what the user has selected in Studio.
- read_script: Read script source code.
- create_instance: Create a single instance with properties (good for one-off parts).
- run_code: Execute Luau code. Best for bulk creation - write a script that creates an entire structure. Use print() to return data. The output of print() is returned to you.
- insert_model: Search and insert marketplace models.

## run_code Best Practices
- Print a summary at the end: print("Created 5 walls, 1 floor, 1 roof")
- After building, verify with: print(#workspace.ModelName:GetDescendants() .. " total parts")
- Use variables for repeated values: local wallHeight = 10; local wallThick = 1
- Create a parent Model first, then parent all parts to it
- ALWAYS use pcall for operations that might fail
"#.to_string()),
        }
    }
}

#[derive(Debug, Deserialize, Serialize, schemars::JsonSchema, Clone)]
struct RunCode {
    #[schemars(description = "Code to run")]
    command: String,
}
#[derive(Debug, Deserialize, Serialize, schemars::JsonSchema, Clone)]
struct InsertModel {
    #[schemars(description = "Query to search for the model")]
    query: String,
}

#[derive(Debug, Deserialize, Serialize, schemars::JsonSchema, Clone)]
struct GetConsoleOutput {}

#[derive(Debug, Deserialize, Serialize, schemars::JsonSchema, Clone)]
struct GetStudioMode {}

#[derive(Debug, Deserialize, Serialize, schemars::JsonSchema, Clone)]
struct StartStopPlay {
    #[schemars(description = "Mode to start or stop, must be start_play, stop, or run_server")]
    mode: String,
}

#[derive(Debug, Deserialize, Serialize, schemars::JsonSchema, Clone)]
struct RunScriptInPlayMode {
    #[schemars(description = "Code to run")]
    code: String,
    #[schemars(description = "Timeout in seconds, defaults to 100 seconds")]
    timeout: Option<u32>,
    #[schemars(description = "Mode to run in, must be start_play or run_server")]
    mode: String,
}

#[derive(Debug, Deserialize, Serialize, schemars::JsonSchema, Clone)]
struct GetDescendants {
    #[schemars(
        description = "Path to the root instance, e.g. 'Workspace' or 'ServerScriptService.GameManager'. Defaults to 'Workspace'."
    )]
    path: Option<String>,
    #[schemars(description = "How many levels deep to traverse. Defaults to 3, max 10.")]
    depth: Option<u32>,
}

#[derive(Debug, Deserialize, Serialize, schemars::JsonSchema, Clone)]
struct ReadScript {
    #[schemars(
        description = "Path to the script, e.g. 'ServerScriptService.GameManager' or 'Workspace.Part.Script'"
    )]
    path: String,
}

#[derive(Debug, Deserialize, Serialize, schemars::JsonSchema, Clone)]
struct GetProperties {
    #[schemars(description = "Path to the instance, e.g. 'Workspace.Part' or 'Lighting'")]
    path: String,
}

#[derive(Debug, Deserialize, Serialize, schemars::JsonSchema, Clone)]
struct GetSelection {}

#[derive(Debug, Deserialize, Serialize, schemars::JsonSchema, Clone)]
struct CreateInstance {
    #[schemars(
        description = "The ClassName to create, e.g. 'Part', 'Model', 'Script', 'PointLight', 'Frame'"
    )]
    #[serde(rename = "className")]
    class_name: String,
    #[schemars(description = "Path to the parent instance. Defaults to 'Workspace'.")]
    parent: Option<String>,
    #[schemars(description = "Name for the new instance")]
    name: Option<String>,
    #[schemars(
        description = "Properties to set on the instance. For BaseParts: Position={X,Y,Z}, Size={X,Y,Z}, Color={R,G,B} (0-255), Material='Plastic', Anchored=true, Transparency=0. For scripts: Source='code'."
    )]
    properties: Option<serde_json::Value>,
}

#[derive(Debug, Deserialize, Serialize, schemars::JsonSchema, Clone)]
enum ToolArgumentValues {
    RunCode(RunCode),
    InsertModel(InsertModel),
    GetConsoleOutput(GetConsoleOutput),
    StartStopPlay(StartStopPlay),
    RunScriptInPlayMode(RunScriptInPlayMode),
    GetStudioMode(GetStudioMode),
    GetDescendants(GetDescendants),
    ReadScript(ReadScript),
    GetProperties(GetProperties),
    GetSelection(GetSelection),
    CreateInstance(CreateInstance),
}
#[tool_router]
impl RoVibeServer {
    pub fn new(state: PackedState) -> Self {
        let trigger = state.blocking_lock().trigger.clone();
        Self {
            state,
            trigger,
            tool_router: Self::tool_router(),
        }
    }

    #[tool(
        description = "Runs a command in Roblox Studio and returns the printed output. Can be used to both make changes and retrieve information"
    )]
    async fn run_code(
        &self,
        Parameters(args): Parameters<RunCode>,
    ) -> Result<CallToolResult, ErrorData> {
        self.generic_tool_run(ToolArgumentValues::RunCode(args))
            .await
    }

    #[tool(
        description = "Inserts a model from the Roblox marketplace into the workspace. Returns the inserted model name."
    )]
    async fn insert_model(
        &self,
        Parameters(args): Parameters<InsertModel>,
    ) -> Result<CallToolResult, ErrorData> {
        self.generic_tool_run(ToolArgumentValues::InsertModel(args))
            .await
    }

    #[tool(description = "Get the console output from Roblox Studio.")]
    async fn get_console_output(
        &self,
        Parameters(args): Parameters<GetConsoleOutput>,
    ) -> Result<CallToolResult, ErrorData> {
        self.generic_tool_run(ToolArgumentValues::GetConsoleOutput(args))
            .await
    }

    #[tool(description = "Start or stop play mode or run the server.")]
    async fn start_stop_play(
        &self,
        Parameters(args): Parameters<StartStopPlay>,
    ) -> Result<CallToolResult, ErrorData> {
        self.generic_tool_run(ToolArgumentValues::StartStopPlay(args))
            .await
    }

    #[tool(
        description = "Run a script in play mode and automatically stop play after script finishes or timeout. Returns the output of the script.
        Result format: { success: boolean, value: string, error: string, logs: { level: string, message: string, ts: number }[], errors: { level: string, message: string, ts: number }[], duration: number, isTimeout: boolean }"
    )]
    async fn run_script_in_play_mode(
        &self,
        Parameters(args): Parameters<RunScriptInPlayMode>,
    ) -> Result<CallToolResult, ErrorData> {
        self.generic_tool_run(ToolArgumentValues::RunScriptInPlayMode(args))
            .await
    }

    #[tool(
        description = "Get the current studio mode. Returns the studio mode. The result will be one of start_play, run_server, or stop."
    )]
    async fn get_studio_mode(
        &self,
        Parameters(args): Parameters<GetStudioMode>,
    ) -> Result<CallToolResult, ErrorData> {
        self.generic_tool_run(ToolArgumentValues::GetStudioMode(args))
            .await
    }

    #[tool(
        description = "Get the instance tree (descendants) starting from a root path. Returns a JSON tree with Name, ClassName, Path, and Children for each instance. BaseParts include Position and Size. Scripts include HasSource flag. Use this to explore the workspace hierarchy before making changes."
    )]
    async fn get_descendants(
        &self,
        Parameters(args): Parameters<GetDescendants>,
    ) -> Result<CallToolResult, ErrorData> {
        self.generic_tool_run(ToolArgumentValues::GetDescendants(args))
            .await
    }

    #[tool(
        description = "Read the source code of a Script, LocalScript, or ModuleScript by its path. Returns the script's source code, className, and line count."
    )]
    async fn read_script(
        &self,
        Parameters(args): Parameters<ReadScript>,
    ) -> Result<CallToolResult, ErrorData> {
        self.generic_tool_run(ToolArgumentValues::ReadScript(args))
            .await
    }

    #[tool(
        description = "Get properties of an instance by its path. Returns common properties based on the instance's class (e.g. Position, Size, Color for BaseParts; Text, TextSize for TextLabels; Source for Scripts). Use this to inspect instances before modifying them."
    )]
    async fn get_properties(
        &self,
        Parameters(args): Parameters<GetProperties>,
    ) -> Result<CallToolResult, ErrorData> {
        self.generic_tool_run(ToolArgumentValues::GetProperties(args))
            .await
    }

    #[tool(
        description = "Get the currently selected instances in Roblox Studio. Returns details about each selected instance including name, className, path, and class-specific properties (position/size for parts, descendant count for models, source length for scripts)."
    )]
    async fn get_selection(
        &self,
        Parameters(args): Parameters<GetSelection>,
    ) -> Result<CallToolResult, ErrorData> {
        self.generic_tool_run(ToolArgumentValues::GetSelection(args))
            .await
    }

    #[tool(
        description = "Create a new instance in the game. Supports common classes like Part, Model, Script, SpawnLocation, PointLight, Frame, TextLabel, etc. BaseParts are auto-anchored. Properties can include Position, Size, Color (RGB 0-255), Material, Transparency, Source (for scripts), and more."
    )]
    async fn create_instance(
        &self,
        Parameters(args): Parameters<CreateInstance>,
    ) -> Result<CallToolResult, ErrorData> {
        self.generic_tool_run(ToolArgumentValues::CreateInstance(args))
            .await
    }

    async fn generic_tool_run(
        &self,
        args: ToolArgumentValues,
    ) -> Result<CallToolResult, ErrorData> {
        let (command, id) = ToolArguments::new(args);
        tracing::debug!("Running command: {:?}", command);
        let (tx, mut rx) = mpsc::unbounded_channel::<Result<String>>();
        {
            let mut state = self.state.lock().await;
            state.process_queue.push_back(command);
            state.output_map.insert(id, tx);
        }
        self.trigger
            .send(())
            .map_err(|e| ErrorData::internal_error(format!("Unable to trigger send {e}"), None))?;
        let result = tokio::time::timeout(TOOL_RESPONSE_TIMEOUT, rx.recv()).await;
        {
            let mut state = self.state.lock().await;
            state.output_map.remove(&id);
        }
        match result {
            Ok(Some(Ok(result))) => {
                tracing::debug!("Sending to MCP: {result:?}");
                Ok(CallToolResult::success(vec![Content::text(result)]))
            }
            Ok(Some(Err(err))) => {
                tracing::debug!("Sending error to MCP: {err:?}");
                Ok(CallToolResult::error(vec![Content::text(err.to_string())]))
            }
            Ok(None) => Err(ErrorData::internal_error(
                "Couldn't receive response: channel closed",
                None,
            )),
            Err(_) => Err(ErrorData::internal_error(
                "Timed out waiting for Roblox Studio response. Is the plugin running?",
                None,
            )),
        }
    }
}

pub async fn request_handler(State(state): State<PackedState>) -> Result<impl IntoResponse> {
    let mut waiter = { state.lock().await.waiter.clone() };
    let timeout = tokio::time::timeout(LONG_POLL_DURATION, async {
        loop {
            {
                let mut state = state.lock().await;
                if let Some(task) = state.process_queue.pop_front() {
                    return Ok::<ToolArguments, Error>(task);
                }
            }
            waiter.changed().await?
        }
    })
    .await;
    match timeout {
        Ok(result) => Ok(Json(result?).into_response()),
        _ => Ok((StatusCode::LOCKED, String::new()).into_response()),
    }
}

pub async fn response_handler(
    State(state): State<PackedState>,
    Json(payload): Json<RunCommandResponse>,
) -> Result<impl IntoResponse> {
    tracing::debug!("Received reply from studio {payload:?}");
    let mut state = state.lock().await;
    let tx = state
        .output_map
        .remove(&payload.id)
        .ok_or_eyre("Unknown ID")?;
    Ok(tx.send(Ok(payload.response))?)
}

pub async fn proxy_handler(
    State(state): State<PackedState>,
    Json(command): Json<ToolArguments>,
) -> Result<impl IntoResponse> {
    let id = command.id.ok_or_eyre("Got proxy command with no id")?;
    tracing::debug!("Received request to proxy {command:?}");
    let (tx, mut rx) = mpsc::unbounded_channel();
    {
        let mut state = state.lock().await;
        state.process_queue.push_back(command);
        state.output_map.insert(id, tx);
        state.trigger.send(()).ok();
    }
    let result = tokio::time::timeout(TOOL_RESPONSE_TIMEOUT, rx.recv()).await;
    {
        let mut state = state.lock().await;
        state.output_map.remove(&id);
    }
    match result {
        Ok(Some(Ok(response))) => {
            tracing::debug!("Sending proxied response: {response:?}");
            Ok(Json(RunCommandResponse { response, id }))
        }
        Ok(Some(Err(e))) => Err(e.into()),
        Ok(None) => Err(color_eyre::eyre::eyre!("Couldn't receive response: channel closed").into()),
        Err(_) => Err(color_eyre::eyre::eyre!("Timed out waiting for proxied response").into()),
    }
}

pub async fn secondary_proxy_loop(state: PackedState, exit: Receiver<()>) {
    let client = reqwest::Client::new();

    let mut waiter = { state.lock().await.waiter.clone() };
    while exit.is_empty() {
        let entry = { state.lock().await.process_queue.pop_front() };
        if let Some(entry) = entry {
            let id = match entry.id {
                Some(id) => id,
                None => {
                    tracing::error!("Proxy entry has no id, skipping");
                    continue;
                }
            };
            let res = client
                .post(format!("http://127.0.0.1:{STUDIO_PLUGIN_PORT}/proxy"))
                .json(&entry)
                .send()
                .await;
            match res {
                Ok(res) => {
                    let tx = {
                        state.lock().await.output_map.remove(&id)
                    };
                    if let Some(tx) = tx {
                        let res = res
                            .json::<RunCommandResponse>()
                            .await
                            .map(|r| r.response)
                            .map_err(Into::into);
                        if tx.send(res).is_err() {
                            tracing::error!("Failed to send proxy response: receiver dropped");
                        }
                    } else {
                        tracing::error!("No output channel found for proxy id {id}");
                    }
                }
                Err(e) => {
                    tracing::error!("Failed to proxy: {e:?}");
                    let tx = { state.lock().await.output_map.remove(&id) };
                    if let Some(tx) = tx {
                        let _ = tx.send(Err(e.into()));
                    }
                }
            };
        } else if waiter.changed().await.is_err() {
            tracing::info!("Proxy loop trigger channel closed, exiting");
            break;
        }
    }
}
