use std::{
    collections::{HashMap, VecDeque},
    env,
    io::{self, Stdout},
    path::Path,
    process::Command,
    sync::mpsc::{self, Receiver, Sender},
    thread,
    time::{Duration, Instant},
};

use crossterm::{
    event::{self, Event, KeyCode, KeyEvent, KeyEventKind, KeyModifiers},
    execute,
    terminal::{disable_raw_mode, enable_raw_mode, EnterAlternateScreen, LeaveAlternateScreen},
};
use ratatui::{
    prelude::*,
    widgets::{Block, Borders, Cell, Clear, Paragraph, Row, Table, TableState, Tabs, Wrap},
};
use serde_json::{json, Value};

const POLL_INTERVAL: Duration = Duration::from_millis(80);
const SEARCH_CACHE_LIMIT: usize = 12;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
enum Screen {
    Dashboard,
    Software,
    Search,
    Doctor,
    History,
}

impl Screen {
    const ALL: [Self; 5] = [
        Self::Dashboard,
        Self::Software,
        Self::Search,
        Self::Doctor,
        Self::History,
    ];

    fn title(self) -> &'static str {
        match self {
            Self::Dashboard => "Dashboard",
            Self::Software => "Software",
            Self::Search => "Search",
            Self::Doctor => "Doctor",
            Self::History => "History",
        }
    }

    fn index(self) -> usize {
        Self::ALL.iter().position(|item| *item == self).unwrap_or(0)
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
enum LoadTarget {
    Screen(Screen),
    Search(String),
}

impl LoadTarget {
    fn title(&self) -> &'static str {
        match self {
            Self::Screen(screen) => screen.title(),
            Self::Search(_) => "Search",
        }
    }
}

#[derive(Debug, Default)]
struct PageState {
    payload: Option<Value>,
    loading: bool,
    error: Option<String>,
    request: Option<u64>,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum MutationStage {
    Preview,
    Apply,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum SoftwareAction {
    Add,
    Remove,
}

impl SoftwareAction {
    fn command(self) -> &'static str {
        match self {
            Self::Add => "add",
            Self::Remove => "rm",
        }
    }

    fn label(self) -> &'static str {
        match self {
            Self::Add => "enable",
            Self::Remove => "disable",
        }
    }
}

#[derive(Clone, Debug, PartialEq, Eq)]
struct MutationIntent {
    action: SoftwareAction,
    group: String,
    item: String,
}

#[derive(Clone, Debug)]
struct MutationPreview {
    intent: MutationIntent,
    payload: Value,
}

#[derive(Clone, Debug, PartialEq, Eq)]
struct SoftwareEntry {
    group: String,
    item: String,
    version: String,
    state: String,
    reference: String,
    effective: bool,
}

impl PageState {
    fn has_content(&self) -> bool {
        self.payload.is_some()
    }
}

#[derive(Debug)]
enum Message {
    Loaded {
        request: u64,
        target: LoadTarget,
        payload: Value,
    },
    Failed {
        request: u64,
        target: LoadTarget,
        error: String,
    },
    MutationFinished {
        request: u64,
        stage: MutationStage,
        intent: MutationIntent,
        result: Result<Value, String>,
    },
}

struct App {
    screen: Screen,
    pages: HashMap<Screen, PageState>,
    search_cache: HashMap<String, PageState>,
    search_order: VecDeque<String>,
    status: String,
    query: String,
    submitted_query: String,
    input_mode: bool,
    scroll: usize,
    visible_rows: usize,
    software_selected: usize,
    request_id: u64,
    tx: Sender<Message>,
    rx: Receiver<Message>,
    should_quit: bool,
    show_help: bool,
    mutation_request: Option<u64>,
    mutation_loading: bool,
    pending_mutation: Option<MutationPreview>,
    mutation_error: Option<String>,
}

impl App {
    fn new(tx: Sender<Message>, rx: Receiver<Message>) -> Self {
        Self {
            screen: Screen::Dashboard,
            pages: HashMap::new(),
            search_cache: HashMap::new(),
            search_order: VecDeque::new(),
            status: "Loading dashboard".to_string(),
            query: String::new(),
            submitted_query: String::new(),
            input_mode: false,
            scroll: 0,
            visible_rows: 1,
            software_selected: 0,
            request_id: 0,
            tx,
            rx,
            should_quit: false,
            show_help: false,
            mutation_request: None,
            mutation_loading: false,
            pending_mutation: None,
            mutation_error: None,
        }
    }

    fn current_target(&self) -> Option<LoadTarget> {
        match self.screen {
            Screen::Search if self.submitted_query.is_empty() => None,
            Screen::Search => Some(LoadTarget::Search(self.submitted_query.clone())),
            screen => Some(LoadTarget::Screen(screen)),
        }
    }

    fn state_for_target(&self, target: &LoadTarget) -> Option<&PageState> {
        match target {
            LoadTarget::Screen(screen) => self.pages.get(screen),
            LoadTarget::Search(query) => self.search_cache.get(query),
        }
    }

    fn state_for_target_mut(&mut self, target: &LoadTarget) -> Option<&mut PageState> {
        match target {
            LoadTarget::Screen(screen) => self.pages.get_mut(screen),
            LoadTarget::Search(query) => self.search_cache.get_mut(query),
        }
    }

    fn current_state(&self) -> Option<&PageState> {
        self.current_target()
            .as_ref()
            .and_then(|target| self.state_for_target(target))
    }

    fn payload(&self) -> Option<&Value> {
        self.current_state()
            .and_then(|state| state.payload.as_ref())
    }

    fn loading(&self) -> bool {
        self.current_state()
            .map(|state| state.loading)
            .unwrap_or(false)
    }

    fn current_error(&self) -> Option<&str> {
        self.current_state()
            .and_then(|state| state.error.as_deref())
    }

    fn current_has_content(&self) -> bool {
        self.current_state()
            .map(PageState::has_content)
            .unwrap_or(false)
    }

    fn prepare_target(&mut self, target: &LoadTarget) {
        match target {
            LoadTarget::Screen(screen) => {
                self.pages.entry(*screen).or_default();
            }
            LoadTarget::Search(query) => {
                if let Some(index) = self.search_order.iter().position(|item| item == query) {
                    self.search_order.remove(index);
                } else if self.search_order.len() >= SEARCH_CACHE_LIMIT {
                    if let Some(oldest) = self.search_order.pop_front() {
                        self.search_cache.remove(&oldest);
                    }
                }
                self.search_order.push_back(query.clone());
                self.search_cache.entry(query.clone()).or_default();
            }
        }
    }

    fn load_current(&mut self, force: bool) {
        let Some(target) = self.current_target() else {
            self.status = "Type a query and press Enter".to_string();
            return;
        };
        self.prepare_target(&target);
        let should_start = self
            .state_for_target(&target)
            .map(|state| !state.loading && (force || !state.has_content()))
            .unwrap_or(true);
        if !should_start {
            self.sync_status();
            return;
        }

        self.request_id += 1;
        let request = self.request_id;
        let has_content = self
            .state_for_target(&target)
            .map(PageState::has_content)
            .unwrap_or(false);
        if let Some(state) = self.state_for_target_mut(&target) {
            state.loading = true;
            state.error = None;
            state.request = Some(request);
        }
        self.status = if has_content {
            format!("Refreshing {}", target.title().to_lowercase())
        } else {
            format!("Loading {}", target.title().to_lowercase())
        };
        spawn_request(self.tx.clone(), request, target);
    }

    fn sync_status(&mut self) {
        let Some(target) = self.current_target() else {
            self.status = "Type a query and press Enter".to_string();
            return;
        };
        let Some(state) = self.state_for_target(&target) else {
            self.status = format!("{} not loaded", target.title());
            return;
        };
        self.status = if state.loading && state.has_content() {
            format!("Refreshing {}", target.title().to_lowercase())
        } else if state.loading {
            format!("Loading {}", target.title().to_lowercase())
        } else if state.error.is_some() && state.has_content() {
            format!("{} refresh failed; showing cached data", target.title())
        } else if state.error.is_some() {
            format!("{} load failed", target.title())
        } else if state.has_content() {
            format!("{} cached", target.title())
        } else {
            format!("{} not loaded", target.title())
        };
    }

    fn set_screen(&mut self, screen: Screen) {
        self.screen = screen;
        self.scroll = 0;
        self.input_mode = false;
        self.load_current(false);
    }

    fn next_screen(&mut self, delta: isize) {
        let count = Screen::ALL.len() as isize;
        let next = (self.screen.index() as isize + delta).rem_euclid(count) as usize;
        self.set_screen(Screen::ALL[next]);
    }

    fn move_software_selection(&mut self, delta: isize) {
        let count = software_entries(self.payload()).len();
        if count == 0 {
            self.software_selected = 0;
            self.scroll = 0;
            return;
        }
        self.software_selected = (self.software_selected as isize + delta)
            .clamp(0, count.saturating_sub(1) as isize) as usize;
        if self.software_selected < self.scroll {
            self.scroll = self.software_selected;
        } else if self.software_selected >= self.scroll + self.visible_rows {
            self.scroll = self
                .software_selected
                .saturating_add(1)
                .saturating_sub(self.visible_rows);
        }
    }

    fn begin_selected_mutation(&mut self) {
        if self.screen != Screen::Software || self.mutation_loading {
            return;
        }
        let Some(entry) = software_entries(self.payload())
            .get(self.software_selected)
            .cloned()
        else {
            self.status = "No software item selected".to_string();
            return;
        };
        let intent = MutationIntent {
            action: if entry.effective {
                SoftwareAction::Remove
            } else {
                SoftwareAction::Add
            },
            group: entry.group,
            item: entry.item,
        };
        self.request_id += 1;
        let request = self.request_id;
        self.mutation_request = Some(request);
        self.mutation_loading = true;
        self.mutation_error = None;
        self.status = format!(
            "Preparing {} plan for {}",
            intent.action.label(),
            intent.item
        );
        spawn_mutation(self.tx.clone(), request, MutationStage::Preview, intent);
    }

    fn apply_pending_mutation(&mut self) {
        if self.mutation_loading {
            return;
        }
        let Some(preview) = self.pending_mutation.as_ref() else {
            return;
        };
        let intent = preview.intent.clone();
        self.request_id += 1;
        let request = self.request_id;
        self.mutation_request = Some(request);
        self.mutation_loading = true;
        self.status = format!("Applying {} for {}", intent.action.label(), intent.item);
        spawn_mutation(self.tx.clone(), request, MutationStage::Apply, intent);
    }

    fn invalidate_after_mutation(&mut self) {
        for screen in [Screen::Dashboard, Screen::Software, Screen::Doctor] {
            self.pages.remove(&screen);
        }
        self.search_cache.clear();
        self.search_order.clear();
        self.scroll = 0;
    }

    fn receive_messages(&mut self) {
        while let Ok(message) = self.rx.try_recv() {
            match message {
                Message::Loaded {
                    request,
                    target,
                    payload,
                } => {
                    let is_current = self.current_target().as_ref() == Some(&target);
                    let dashboard_doctor = if target == LoadTarget::Screen(Screen::Dashboard) {
                        payload.get("doctor").cloned()
                    } else {
                        None
                    };
                    let accepted = self
                        .state_for_target_mut(&target)
                        .filter(|state| state.request == Some(request))
                        .map(|state| {
                            state.payload = Some(payload);
                            state.loading = false;
                            state.error = None;
                            state.request = None;
                        })
                        .is_some();
                    if accepted {
                        if let Some(doctor) = dashboard_doctor {
                            let state = self.pages.entry(Screen::Doctor).or_default();
                            if !state.loading {
                                state.payload = Some(doctor);
                                state.error = None;
                            }
                        }
                    }
                    if accepted && is_current {
                        self.status = format!("{} ready", target.title());
                    }
                    if accepted && target == LoadTarget::Screen(Screen::Software) {
                        let count = software_entries(
                            self.state_for_target(&target)
                                .and_then(|state| state.payload.as_ref()),
                        )
                        .len();
                        self.software_selected =
                            self.software_selected.min(count.saturating_sub(1));
                    }
                }
                Message::Failed {
                    request,
                    target,
                    error,
                } => {
                    let is_current = self.current_target().as_ref() == Some(&target);
                    let accepted = self
                        .state_for_target_mut(&target)
                        .filter(|state| state.request == Some(request))
                        .map(|state| {
                            state.loading = false;
                            state.error = Some(error);
                            state.request = None;
                        })
                        .is_some();
                    if accepted && is_current {
                        self.sync_status();
                    }
                }
                Message::MutationFinished {
                    request,
                    stage,
                    intent,
                    result,
                } if self.mutation_request == Some(request) => {
                    self.mutation_request = None;
                    self.mutation_loading = false;
                    match (stage, result) {
                        (MutationStage::Preview, Ok(payload)) => {
                            self.status =
                                format!("{} plan ready for {}", intent.action.label(), intent.item);
                            self.pending_mutation = Some(MutationPreview { intent, payload });
                        }
                        (MutationStage::Apply, Ok(_)) => {
                            let description =
                                format!("{} applied for {}", intent.action.label(), intent.item);
                            self.pending_mutation = None;
                            self.invalidate_after_mutation();
                            self.load_current(true);
                            self.status = format!("{description}; refreshing software");
                        }
                        (_, Err(error)) => {
                            self.pending_mutation = None;
                            self.mutation_error = Some(error);
                            self.status = format!("{} failed", intent.action.label());
                        }
                    }
                }
                Message::MutationFinished { .. } => {}
            }
        }
    }

    fn row_count(&self) -> usize {
        match self.screen {
            Screen::Software => self
                .payload()
                .unwrap_or(&Value::Null)
                .get("groups")
                .and_then(Value::as_array)
                .map(|groups| {
                    groups
                        .iter()
                        .filter_map(|group| group.get("items").and_then(Value::as_array))
                        .map(Vec::len)
                        .sum()
                })
                .unwrap_or(0),
            Screen::Search | Screen::Doctor => self
                .payload()
                .unwrap_or(&Value::Null)
                .get("results")
                .and_then(Value::as_array)
                .map(Vec::len)
                .unwrap_or(0),
            Screen::History => self
                .payload()
                .unwrap_or(&Value::Null)
                .get("generations")
                .and_then(Value::as_array)
                .map(Vec::len)
                .unwrap_or(0),
            Screen::Dashboard => 0,
        }
    }

    fn clamp_scroll(&mut self, body_height: u16) {
        self.visible_rows = (body_height.saturating_sub(3) as usize).max(1);
        let row_count = self.row_count();
        let maximum = row_count.saturating_sub(self.visible_rows);
        if self.screen == Screen::Software {
            self.software_selected = self.software_selected.min(row_count.saturating_sub(1));
            if self.software_selected < self.scroll {
                self.scroll = self.software_selected;
            } else if self.software_selected >= self.scroll + self.visible_rows {
                self.scroll = self
                    .software_selected
                    .saturating_add(1)
                    .saturating_sub(self.visible_rows);
            }
        }
        self.scroll = self.scroll.min(maximum);
    }

    fn handle_key(&mut self, key: KeyEvent) {
        if key.kind != KeyEventKind::Press {
            return;
        }
        if self.mutation_error.is_some() {
            if matches!(key.code, KeyCode::Esc | KeyCode::Enter) {
                self.mutation_error = None;
                self.sync_status();
            }
            return;
        }
        if self.pending_mutation.is_some() {
            match key.code {
                KeyCode::Enter | KeyCode::Char('y') if !self.mutation_loading => {
                    self.apply_pending_mutation();
                }
                KeyCode::Esc | KeyCode::Char('n') if !self.mutation_loading => {
                    self.pending_mutation = None;
                    self.status = "Software change cancelled".to_string();
                }
                _ => {}
            }
            return;
        }
        if self.mutation_loading {
            return;
        }
        if self.show_help {
            if matches!(key.code, KeyCode::Esc | KeyCode::Char('?') | KeyCode::Enter) {
                self.show_help = false;
            }
            return;
        }
        if self.input_mode {
            match key.code {
                KeyCode::Esc => {
                    self.input_mode = false;
                    self.query = self.submitted_query.clone();
                    self.status = "Search cancelled".to_string();
                }
                KeyCode::Enter => {
                    self.input_mode = false;
                    self.scroll = 0;
                    self.submitted_query = self.query.trim().to_string();
                    self.load_current(false);
                }
                KeyCode::Backspace => {
                    self.query.pop();
                }
                KeyCode::Char(character) if !key.modifiers.contains(KeyModifiers::CONTROL) => {
                    self.query.push(character);
                }
                _ => {}
            }
            return;
        }

        match key.code {
            KeyCode::Char('q') | KeyCode::Esc => self.should_quit = true,
            KeyCode::Char('?') => self.show_help = true,
            KeyCode::Char('r') => self.load_current(true),
            KeyCode::Tab | KeyCode::Right => self.next_screen(1),
            KeyCode::BackTab | KeyCode::Left => self.next_screen(-1),
            KeyCode::Char('/') | KeyCode::Char('s') if self.screen == Screen::Search => {
                self.input_mode = true;
                self.status = "Type a query and press Enter".to_string();
            }
            KeyCode::Char('/') => {
                self.screen = Screen::Search;
                self.scroll = 0;
                self.input_mode = true;
                self.sync_status();
            }
            KeyCode::Char(character) if ('1'..='5').contains(&character) => {
                self.set_screen(Screen::ALL[character as usize - '1' as usize]);
            }
            KeyCode::Enter | KeyCode::Char(' ') if self.screen == Screen::Software => {
                self.begin_selected_mutation();
            }
            KeyCode::Down | KeyCode::Char('j') if self.screen == Screen::Software => {
                self.move_software_selection(1);
            }
            KeyCode::Up | KeyCode::Char('k') if self.screen == Screen::Software => {
                self.move_software_selection(-1);
            }
            KeyCode::Down | KeyCode::Char('j') => {
                self.scroll = self.scroll.saturating_add(1);
            }
            KeyCode::Up | KeyCode::Char('k') => {
                self.scroll = self.scroll.saturating_sub(1);
            }
            _ => {}
        }
    }
}

fn envy_binary() -> String {
    env::var("ENVY_BIN").unwrap_or_else(|_| "envy".to_string())
}

fn run_json(args: &[&str]) -> Result<Value, String> {
    let binary = envy_binary();
    let command = if Path::new(&binary).is_file() {
        binary
    } else {
        "envy".to_string()
    };
    let output = Command::new(command)
        .args(args)
        .output()
        .map_err(|error| format!("could not start envy: {error}"))?;
    let stdout = String::from_utf8_lossy(&output.stdout);
    match serde_json::from_str::<Value>(&stdout) {
        Ok(value) => Ok(value),
        Err(error) => {
            let stderr = String::from_utf8_lossy(&output.stderr).trim().to_string();
            if stderr.is_empty() {
                Err(format!("envy returned invalid JSON: {error}"))
            } else {
                Err(stderr)
            }
        }
    }
}

fn load_target(target: &LoadTarget) -> Result<Value, String> {
    match target {
        LoadTarget::Screen(Screen::Dashboard) => {
            // These commands are independent and can each involve Nix or
            // app probes. Running them together makes the first paint wait
            // for the slowest command instead of the sum of all three.
            let config = thread::spawn(|| run_json(&["config", "show", "--json"]));
            let software = thread::spawn(|| run_json(&["sw", "st", "--json"]));
            let doctor = thread::spawn(|| run_json(&["doctor", "--json"]));

            let join = |worker: thread::JoinHandle<Result<Value, String>>, name: &str| {
                worker
                    .join()
                    .map_err(|_| format!("{name} worker panicked"))?
            };
            Ok(json!({
                "config": join(config, "config")?,
                "software": join(software, "software")?,
                "doctor": join(doctor, "doctor")?,
            }))
        }
        LoadTarget::Screen(Screen::Software) => run_json(&["sw", "ls", "--details", "--json"]),
        LoadTarget::Search(query) => {
            // Search every configured provider. The request runs in the
            // background, and Envy's own query/index caches avoid doing
            // network work again when the same query is revisited.
            run_json(&["sw", "search", query, "--json"])
        }
        LoadTarget::Screen(Screen::Doctor) => run_json(&["doctor", "--json"]),
        LoadTarget::Screen(Screen::History) => run_json(&["history", "--json"]),
        LoadTarget::Screen(Screen::Search) => {
            Ok(json!({"query": "", "results": [], "providers": []}))
        }
    }
}

fn spawn_request(tx: Sender<Message>, request: u64, target: LoadTarget) {
    thread::spawn(move || match load_target(&target) {
        Ok(payload) => {
            let _ = tx.send(Message::Loaded {
                request,
                target,
                payload,
            });
        }
        Err(error) => {
            let _ = tx.send(Message::Failed {
                request,
                target,
                error,
            });
        }
    });
}

fn mutation_result(payload: Value) -> Result<Value, String> {
    if payload.get("ok").and_then(Value::as_bool) == Some(false) {
        let message = payload
            .get("error")
            .and_then(|error| error.get("message"))
            .and_then(Value::as_str)
            .unwrap_or("software mutation failed");
        Err(message.to_string())
    } else {
        Ok(payload)
    }
}

fn mutation_args(stage: MutationStage, intent: &MutationIntent) -> Vec<String> {
    let mut args = vec![
        "sw".to_string(),
        intent.action.command().to_string(),
        intent.group.clone(),
        intent.item.clone(),
    ];
    match stage {
        MutationStage::Preview => args.push("--dry-run".to_string()),
        MutationStage::Apply => args.push("--yes".to_string()),
    }
    args.push("--json".to_string());
    args
}

fn validate_mutation_response(
    stage: MutationStage,
    intent: &MutationIntent,
    payload: Value,
) -> Result<Value, String> {
    let payload = mutation_result(payload)?;
    if payload.get("schemaVersion").and_then(Value::as_u64) != Some(1) {
        return Err("unsupported software mutation schema".to_string());
    }
    let expected_command = format!("software.{}", intent.action.command());
    if payload.get("command").and_then(Value::as_str) != Some(expected_command.as_str()) {
        return Err("software mutation command does not match the request".to_string());
    }
    let data = payload.get("data").unwrap_or(&Value::Null);
    let plan = data.get("plan").unwrap_or(&Value::Null);
    let group = plan
        .get("group")
        .and_then(|group| group.get("id"))
        .and_then(Value::as_str);
    let item = plan.get("item").and_then(Value::as_str);
    let action = plan.get("action").and_then(Value::as_str);
    let effective = plan
        .get("expected")
        .and_then(|expected| expected.get("effective"))
        .and_then(Value::as_bool);
    if group != Some(intent.group.as_str())
        || item != Some(intent.item.as_str())
        || action != Some(intent.action.command())
        || effective != Some(intent.action == SoftwareAction::Add)
    {
        return Err("software mutation plan does not match the selected item".to_string());
    }
    let result = data.get("result").and_then(Value::as_str);
    let valid_result = match stage {
        MutationStage::Preview => result == Some("dry-run"),
        MutationStage::Apply => matches!(result, Some("applied" | "already-satisfied")),
    };
    if !valid_result {
        return Err("software mutation returned an unexpected result".to_string());
    }
    Ok(payload)
}

fn spawn_mutation(tx: Sender<Message>, request: u64, stage: MutationStage, intent: MutationIntent) {
    thread::spawn(move || {
        let args = mutation_args(stage, &intent);
        let arg_refs = args.iter().map(String::as_str).collect::<Vec<_>>();
        let result = run_json(&arg_refs)
            .and_then(|payload| validate_mutation_response(stage, &intent, payload));
        let _ = tx.send(Message::MutationFinished {
            request,
            stage,
            intent,
            result,
        });
    });
}

fn text(value: Option<&Value>) -> String {
    match value {
        Some(Value::String(value)) => value.clone(),
        Some(Value::Bool(value)) => value.to_string(),
        Some(Value::Number(value)) => value.to_string(),
        Some(Value::Null) => "—".to_string(),
        Some(value) => value.to_string(),
        None => "—".to_string(),
    }
}

fn software_entries(payload: Option<&Value>) -> Vec<SoftwareEntry> {
    let mut entries = Vec::new();
    let Some(groups) = payload
        .and_then(|value| value.get("groups"))
        .and_then(Value::as_array)
    else {
        return entries;
    };
    for group in groups {
        let group_id = text(group.get("id"));
        let Some(items) = group.get("items").and_then(Value::as_array) else {
            continue;
        };
        for item in items {
            let effective = item
                .get("effective")
                .and_then(Value::as_bool)
                .unwrap_or(false);
            let state = if effective {
                "effective"
            } else if item
                .get("externalExclude")
                .and_then(Value::as_bool)
                .unwrap_or(false)
            {
                "blocked"
            } else if item.get("stale").and_then(Value::as_bool).unwrap_or(false) {
                "stale"
            } else {
                "excluded"
            };
            entries.push(SoftwareEntry {
                group: group_id.clone(),
                item: text(item.get("id")),
                version: text(item.get("version")),
                state: state.to_string(),
                reference: text(item.get("ref")),
                effective,
            });
        }
    }
    entries
}

/// Compute the largest useful table offset for a viewport.
///
/// A table has a one-line header and a two-line border, so subtracting three
/// keeps the final page filled with rows. Ratatui clips the rows to the area;
/// without this bound, repeatedly pressing j/↓ could skip every row and leave
/// an apparently empty page.
fn row_offset(scroll: usize, row_count: usize, area: Rect) -> usize {
    let visible_rows = area.height.saturating_sub(3) as usize;
    scroll.min(row_count.saturating_sub(visible_rows))
}

fn render_header(frame: &mut Frame, app: &App, area: Rect) {
    let titles: Vec<Line> = Screen::ALL
        .iter()
        .enumerate()
        .map(|(index, screen)| {
            Line::from(vec![
                Span::styled(
                    format!(" {} ", index + 1),
                    Style::default().fg(Color::DarkGray),
                ),
                Span::styled(
                    screen.title(),
                    if *screen == app.screen {
                        Style::default().fg(Color::Black).bg(Color::Cyan).bold()
                    } else {
                        Style::default().fg(Color::Gray)
                    },
                ),
            ])
        })
        .collect();
    let tabs = Tabs::new(titles)
        .select(app.screen.index())
        .divider("│")
        .block(
            Block::default()
                .title(" ENVY ")
                .borders(Borders::ALL)
                .border_style(Color::Cyan),
        );
    frame.render_widget(tabs, area);
}

fn render_footer(frame: &mut Frame, app: &App, area: Rect) {
    let mode = if app.input_mode { "SEARCH" } else { "NORMAL" };
    let query = if app.screen == Screen::Search {
        format!(
            "  query: {}",
            if app.query.is_empty() {
                "<empty>"
            } else {
                &app.query
            }
        )
    } else {
        String::new()
    };
    let activity = if app.mutation_loading {
        "  ◌ working"
    } else if app.loading() {
        if app.current_has_content() {
            "  ◌ refreshing"
        } else {
            "  ◌ loading"
        }
    } else {
        ""
    };
    let line = Line::from(vec![
        Span::styled(
            format!(" {mode} "),
            Style::default().fg(Color::Black).bg(Color::Green).bold(),
        ),
        Span::styled(
            format!("  {}  ", app.status),
            Style::default().fg(Color::Gray),
        ),
        Span::styled(query, Style::default().fg(Color::Yellow)),
        Span::styled(activity, Style::default().fg(Color::Yellow)),
        Span::styled(
            if app.screen == Screen::Software {
                "  Enter toggle  q quit  ? help  r refresh  Tab next"
            } else {
                "  q quit  ? help  r refresh  Tab next  ↑↓ scroll"
            },
            Style::default().fg(Color::DarkGray),
        ),
    ]);
    frame.render_widget(Paragraph::new(line), area);
}

fn render_dashboard(frame: &mut Frame, app: &App, area: Rect) {
    let columns =
        Layout::horizontal([Constraint::Percentage(50), Constraint::Percentage(50)]).split(area);
    let payload = app.payload().unwrap_or(&Value::Null);
    let config = payload.get("config").unwrap_or(&Value::Null);
    let software = payload.get("software").unwrap_or(&Value::Null);
    let doctor = payload.get("doctor").unwrap_or(&Value::Null);
    let values = config.get("values").unwrap_or(&Value::Null);
    let user = values
        .get("envy.user.name")
        .or_else(|| values.get("user.name"));
    let machine = config
        .get("device")
        .and_then(|value| value.get("machineId"));
    let platform = config.get("platform").or_else(|| {
        config
            .get("values")
            .and_then(|value| value.get("envy.platform"))
    });
    let left = vec![
        Line::from(Span::styled(
            "Machine",
            Style::default().fg(Color::Cyan).bold(),
        )),
        Line::from(format!("  {}", text(machine))),
        Line::from(format!("  user      {}", text(user))),
        Line::from(format!("  platform  {}", text(platform))),
        Line::from(""),
        Line::from(Span::styled(
            "Software",
            Style::default().fg(Color::Cyan).bold(),
        )),
        Line::from(format!("  groups    {}", text(software.get("groups")))),
        Line::from(format!("  included  {}", text(software.get("included")))),
        Line::from(format!("  effective {}", text(software.get("effective")))),
        Line::from(format!("  excluded  {}", text(software.get("excluded")))),
    ];
    let summary = doctor.get("summary").unwrap_or(&Value::Null);
    let right = vec![
        Line::from(Span::styled(
            "Doctor",
            Style::default().fg(Color::Cyan).bold(),
        )),
        Line::from(format!("  ok       {}", text(summary.get("ok")))),
        Line::from(format!("  warnings {}", text(summary.get("warn")))),
        Line::from(format!("  errors   {}", text(summary.get("error")))),
        Line::from(""),
        Line::from(Span::styled(
            "Shortcuts",
            Style::default().fg(Color::Cyan).bold(),
        )),
        Line::from("  1 dashboard   2 software   3 search"),
        Line::from("  4 doctor      5 history"),
        Line::from("  / search from any screen"),
    ];
    frame.render_widget(card(Paragraph::new(left)), columns[0]);
    frame.render_widget(card(Paragraph::new(right)), columns[1]);
}

fn card<'a>(widget: Paragraph<'a>) -> Paragraph<'a> {
    widget.block(
        Block::default()
            .borders(Borders::ALL)
            .border_style(Style::default().fg(Color::DarkGray)),
    )
}

fn render_software(frame: &mut Frame, app: &App, area: Rect) {
    let entries = software_entries(app.payload());
    let offset = row_offset(app.scroll, entries.len(), area);
    let rows = entries
        .iter()
        .skip(offset)
        .map(|entry| {
            let state_style = match entry.state.as_str() {
                "effective" => Style::default().fg(Color::Green),
                "blocked" => Style::default().fg(Color::Red),
                "stale" => Style::default().fg(Color::Yellow),
                _ => Style::default().fg(Color::DarkGray),
            };
            Row::new(vec![
                Cell::from(entry.group.clone()),
                Cell::from(entry.item.clone()),
                Cell::from(entry.version.clone()),
                Cell::from(entry.state.clone()).style(state_style),
                Cell::from(entry.reference.clone()),
            ])
        })
        .collect::<Vec<_>>();
    let table = Table::new(
        rows,
        [
            Constraint::Length(28),
            Constraint::Length(22),
            Constraint::Length(12),
            Constraint::Length(12),
            Constraint::Min(20),
        ],
    )
    .header(
        Row::new(["GROUP", "ITEM", "VERSION", "STATE", "REFERENCE"])
            .style(Style::default().fg(Color::Cyan).bold()),
    )
    .row_highlight_style(Style::default().bg(Color::Rgb(25, 45, 60)))
    .highlight_symbol("▸ ")
    .block(
        Block::default()
            .title(" Software policy — Enter/Space toggles availability ")
            .borders(Borders::ALL)
            .border_style(Color::DarkGray),
    );
    let selected = if entries.is_empty() {
        None
    } else {
        Some(app.software_selected.saturating_sub(offset))
    };
    let mut state = TableState::default().with_selected(selected);
    frame.render_stateful_widget(table, area, &mut state);
}

fn render_search(frame: &mut Frame, app: &App, area: Rect) {
    let rows = app
        .payload()
        .and_then(|payload| payload.get("results"))
        .and_then(Value::as_array)
        .map(|results| {
            results
                .iter()
                .map(|result| {
                    Row::new(vec![
                        Cell::from(text(result.get("source"))),
                        Cell::from(text(result.get("kind"))),
                        Cell::from(text(result.get("name"))),
                        Cell::from(text(result.get("version"))),
                        Cell::from(text(result.get("managedGroup"))),
                        Cell::from(text(result.get("ref"))),
                    ])
                })
                .collect::<Vec<_>>()
        })
        .unwrap_or_default();
    let title = if app.submitted_query.is_empty() {
        " Search (press /) ".to_string()
    } else {
        format!(" Search: {} ", app.submitted_query)
    };
    let offset = row_offset(app.scroll, rows.len(), area);
    let table = Table::new(
        rows.into_iter().skip(offset).collect::<Vec<_>>(),
        [
            Constraint::Length(12),
            Constraint::Length(12),
            Constraint::Length(28),
            Constraint::Length(12),
            Constraint::Length(28),
            Constraint::Min(20),
        ],
    )
    .header(
        Row::new(["SOURCE", "KIND", "NAME", "VERSION", "MANAGED", "REFERENCE"])
            .style(Style::default().fg(Color::Cyan).bold()),
    )
    .block(
        Block::default()
            .title(title)
            .borders(Borders::ALL)
            .border_style(Color::DarkGray),
    );
    frame.render_widget(table, area);
}

fn render_doctor(frame: &mut Frame, app: &App, area: Rect) {
    let rows = app
        .payload()
        .and_then(|payload| payload.get("results"))
        .and_then(Value::as_array)
        .map(|results| {
            results
                .iter()
                .map(|result| {
                    let status = text(result.get("status"));
                    let style = match status.as_str() {
                        "ok" => Style::default().fg(Color::Green),
                        "warn" => Style::default().fg(Color::Yellow),
                        "error" => Style::default().fg(Color::Red),
                        _ => Style::default().fg(Color::Gray),
                    };
                    Row::new(vec![
                        Cell::from(status).style(style),
                        Cell::from(text(result.get("name"))),
                        Cell::from(text(result.get("message"))),
                        Cell::from(text(result.get("hint"))),
                    ])
                })
                .collect::<Vec<_>>()
        })
        .unwrap_or_default();
    let offset = row_offset(app.scroll, rows.len(), area);
    let table = Table::new(
        rows.into_iter().skip(offset).collect::<Vec<_>>(),
        [
            Constraint::Length(10),
            Constraint::Length(28),
            Constraint::Min(30),
            Constraint::Length(45),
        ],
    )
    .header(
        Row::new(["STATUS", "CHECK", "RESULT", "HINT"])
            .style(Style::default().fg(Color::Cyan).bold()),
    )
    .block(
        Block::default()
            .title(" Doctor ")
            .borders(Borders::ALL)
            .border_style(Color::DarkGray),
    );
    frame.render_widget(table, area);
}

fn render_history(frame: &mut Frame, app: &App, area: Rect) {
    let rows = app
        .payload()
        .and_then(|payload| payload.get("generations"))
        .and_then(Value::as_array)
        .map(|generations| {
            generations
                .iter()
                .map(|generation| {
                    let current = generation
                        .get("current")
                        .and_then(Value::as_bool)
                        .unwrap_or(false);
                    Row::new(vec![
                        Cell::from(text(generation.get("number"))),
                        Cell::from(if current { "current" } else { "" }),
                        Cell::from(text(generation.get("createdAt"))),
                        Cell::from(text(generation.get("target"))),
                    ])
                })
                .collect::<Vec<_>>()
        })
        .unwrap_or_default();
    let offset = row_offset(app.scroll, rows.len(), area);
    let table = Table::new(
        rows.into_iter().skip(offset).collect::<Vec<_>>(),
        [
            Constraint::Length(12),
            Constraint::Length(12),
            Constraint::Length(28),
            Constraint::Min(40),
        ],
    )
    .header(
        Row::new(["GENERATION", "STATE", "CREATED", "STORE TARGET"])
            .style(Style::default().fg(Color::Cyan).bold()),
    )
    .block(
        Block::default()
            .title(" Generations ")
            .borders(Borders::ALL)
            .border_style(Color::DarkGray),
    );
    frame.render_widget(table, area);
}

fn render_body(frame: &mut Frame, app: &App, area: Rect) {
    if let Some(error) = app.current_error().filter(|_| !app.current_has_content()) {
        let paragraph = Paragraph::new(vec![
            Line::from(Span::styled(
                "Unable to load data",
                Style::default().fg(Color::Red).bold(),
            )),
            Line::from(""),
            Line::from(error),
            Line::from(""),
            Line::from("Press r to retry or q to quit."),
        ])
        .wrap(Wrap { trim: false })
        .block(
            Block::default()
                .title(" Error ")
                .borders(Borders::ALL)
                .border_style(Color::Red),
        );
        frame.render_widget(paragraph, area);
        return;
    }
    match app.screen {
        Screen::Dashboard => render_dashboard(frame, app, area),
        Screen::Software => render_software(frame, app, area),
        Screen::Search => render_search(frame, app, area),
        Screen::Doctor => render_doctor(frame, app, area),
        Screen::History => render_history(frame, app, area),
    }
    if app.loading() && !app.current_has_content() {
        let loading = Clear;
        frame.render_widget(loading, area);
        frame.render_widget(
            Paragraph::new("  Loading…")
                .style(Style::default().fg(Color::Yellow))
                .block(Block::default().borders(Borders::ALL)),
            area,
        );
    }
}

fn render_help(frame: &mut Frame, area: Rect) {
    let popup = centered_rect(70, 60, area);
    frame.render_widget(Clear, popup);
    let help = Paragraph::new(vec![
        Line::from(Span::styled(
            "Keyboard",
            Style::default().fg(Color::Cyan).bold(),
        )),
        Line::from(""),
        Line::from("  1..5       jump to a page"),
        Line::from("  Tab / ←→   switch pages"),
        Line::from("  /          search from any page"),
        Line::from("  Enter      submit search"),
        Line::from("  r          refresh current page"),
        Line::from("  ↑↓ / j k   scroll"),
        Line::from("  Enter/Space toggle selected software"),
        Line::from("  q / Esc    quit"),
        Line::from(""),
        Line::from("Press ? or Esc to close"),
    ])
    .block(
        Block::default()
            .title(" Help ")
            .borders(Borders::ALL)
            .border_style(Color::Cyan),
    )
    .wrap(Wrap { trim: false });
    frame.render_widget(help, popup);
}

fn joined_strings(value: Option<&Value>) -> Option<String> {
    value
        .and_then(Value::as_array)
        .map(|items| {
            items
                .iter()
                .filter_map(Value::as_str)
                .collect::<Vec<_>>()
                .join(", ")
        })
        .filter(|value| !value.is_empty())
}

fn inset_rect(area: Rect, horizontal: u16, vertical: u16) -> Rect {
    let horizontal = horizontal.min(area.width / 2);
    let vertical = vertical.min(area.height / 2);
    Rect {
        x: area.x.saturating_add(horizontal),
        y: area.y.saturating_add(vertical),
        width: area.width.saturating_sub(horizontal.saturating_mul(2)),
        height: area.height.saturating_sub(vertical.saturating_mul(2)),
    }
}

fn centered_size(width: u16, height: u16, area: Rect) -> Rect {
    let width = width.min(area.width.saturating_sub(4)).max(1);
    let height = height.min(area.height.saturating_sub(2)).max(1);
    Rect {
        x: area.x + area.width.saturating_sub(width) / 2,
        y: area.y + area.height.saturating_sub(height) / 2,
        width,
        height,
    }
}

fn render_popup_panel(frame: &mut Frame, area: Rect, title: &str, lines: Vec<Line<'static>>) {
    let block = Block::default()
        .title(format!(" {title} "))
        .borders(Borders::ALL)
        .border_style(Color::DarkGray)
        .style(Style::default().bg(Color::Rgb(18, 22, 30)));
    let inner = inset_rect(block.inner(area), 1, 0);
    frame.render_widget(block, area);
    frame.render_widget(Paragraph::new(lines).wrap(Wrap { trim: false }), inner);
}

fn render_mutation_overlay(frame: &mut Frame, app: &App, area: Rect) {
    if let Some(error) = &app.mutation_error {
        let popup = centered_size(76, 11, area);
        frame.render_widget(Clear, popup);
        render_popup_panel(
            frame,
            popup,
            "SOFTWARE CHANGE FAILED",
            vec![
                Line::from(""),
                Line::from(Span::styled(error.clone(), Style::default().fg(Color::Red))),
                Line::from(""),
                Line::from(vec![
                    Span::styled(
                        " ENTER ",
                        Style::default().fg(Color::Black).bg(Color::Cyan).bold(),
                    ),
                    Span::raw("  close"),
                ]),
            ],
        );
        return;
    }

    if let Some(preview) = &app.pending_mutation {
        let plan = preview
            .payload
            .get("data")
            .and_then(|data| data.get("plan"))
            .unwrap_or(&Value::Null);
        let expected = plan.get("expected").unwrap_or(&Value::Null);
        let effective = expected
            .get("effective")
            .and_then(Value::as_bool)
            .map(|value| if value { "enabled" } else { "disabled" })
            .unwrap_or("unknown");
        let changed = plan
            .get("changed")
            .and_then(Value::as_bool)
            .unwrap_or(false);
        let blocked = plan.get("blocked").and_then(Value::as_str);
        let wide = area.width >= 100;
        let popup = centered_size(if wide { 94 } else { 76 }, if wide { 18 } else { 24 }, area);
        frame.render_widget(Clear, popup);

        let outer = Block::default()
            .title(" CONFIRM SOFTWARE CHANGE ")
            .borders(Borders::ALL)
            .border_style(Color::Cyan)
            .style(Style::default().bg(Color::Rgb(18, 22, 30)));
        let inner = inset_rect(outer.inner(popup), 2, 1);
        frame.render_widget(outer, popup);
        let sections = Layout::vertical([
            Constraint::Length(3),
            Constraint::Min(8),
            Constraint::Length(3),
        ])
        .split(inner);

        let action_color = match preview.intent.action {
            SoftwareAction::Add => Color::Green,
            SoftwareAction::Remove => Color::Yellow,
        };
        let action_badge = preview.intent.action.label().to_uppercase();
        let change_badge = if changed { " CHANGES " } else { " NO CHANGES " };
        frame.render_widget(
            Paragraph::new(vec![
                Line::from(vec![
                    Span::styled(
                        format!(" {action_badge} "),
                        Style::default().fg(Color::Black).bg(action_color).bold(),
                    ),
                    Span::styled(
                        format!("  {}", preview.intent.item),
                        Style::default().fg(Color::White).bold(),
                    ),
                    Span::raw("  "),
                    Span::styled(
                        change_badge,
                        Style::default().fg(Color::Black).bg(Color::DarkGray).bold(),
                    ),
                ]),
                Line::from(Span::styled(
                    "Review the verified Envy policy plan before applying it.",
                    Style::default().fg(Color::DarkGray),
                )),
            ]),
            sections[0],
        );

        let summary_lines = vec![
            Line::from(vec![
                Span::styled("Group     ", Style::default().fg(Color::DarkGray)),
                Span::styled(
                    preview.intent.group.clone(),
                    Style::default().fg(Color::White),
                ),
            ]),
            Line::from(vec![
                Span::styled("Item      ", Style::default().fg(Color::DarkGray)),
                Span::styled(
                    preview.intent.item.clone(),
                    Style::default().fg(Color::White),
                ),
            ]),
            Line::from(vec![
                Span::styled("Result    ", Style::default().fg(Color::DarkGray)),
                Span::styled(effective, Style::default().fg(action_color).bold()),
            ]),
            Line::from(vec![
                Span::styled("Verified  ", Style::default().fg(Color::DarkGray)),
                Span::styled("dry-run", Style::default().fg(Color::Cyan)),
            ]),
        ];
        let mut plan_lines = Vec::new();
        for (label, color, value) in [
            ("Add include       ", Color::Green, plan.get("includeAdded")),
            ("Remove include    ", Color::Red, plan.get("includeRemoved")),
            (
                "Add exclusion     ",
                Color::Yellow,
                plan.get("excludeAdded"),
            ),
            (
                "Remove exclusion  ",
                Color::Cyan,
                plan.get("excludeRemoved"),
            ),
        ] {
            if let Some(items) = joined_strings(value) {
                plan_lines.push(Line::from(vec![
                    Span::styled(label, Style::default().fg(color)),
                    Span::styled(items, Style::default().fg(Color::White).bold()),
                ]));
            }
        }
        if plan_lines.is_empty() {
            plan_lines.push(Line::from(Span::styled(
                "No policy edits are required.",
                Style::default().fg(Color::DarkGray),
            )));
        }

        if wide {
            let columns = Layout::horizontal([
                Constraint::Percentage(48),
                Constraint::Length(2),
                Constraint::Percentage(48),
            ])
            .split(sections[1]);
            render_popup_panel(frame, columns[0], "SUMMARY", summary_lines);
            render_popup_panel(frame, columns[2], "POLICY PLAN", plan_lines);
        } else {
            let body = Layout::vertical([
                Constraint::Length(7),
                Constraint::Length(1),
                Constraint::Min(7),
            ])
            .split(sections[1]);
            render_popup_panel(frame, body[0], "SUMMARY", summary_lines);
            render_popup_panel(frame, body[2], "POLICY PLAN", plan_lines);
        }

        let footer = if app.mutation_loading {
            Line::from(Span::styled(
                "Applying verified change…",
                Style::default().fg(Color::Yellow).bold(),
            ))
        } else if let Some(reason) = blocked {
            Line::from(Span::styled(
                format!("Blocked: {reason}"),
                Style::default().fg(Color::Red).bold(),
            ))
        } else {
            Line::from(vec![
                Span::styled(
                    " ENTER ",
                    Style::default().fg(Color::Black).bg(Color::Green).bold(),
                ),
                Span::raw("  Apply     "),
                Span::styled(
                    " ESC ",
                    Style::default().fg(Color::White).bg(Color::DarkGray).bold(),
                ),
                Span::raw("  Cancel"),
            ])
        };
        frame.render_widget(
            Paragraph::new(vec![Line::from(""), footer]).alignment(Alignment::Center),
            sections[2],
        );
        return;
    }

    if app.mutation_loading {
        let popup = centered_size(60, 7, area);
        frame.render_widget(Clear, popup);
        render_popup_panel(
            frame,
            popup,
            "VERIFYING SOFTWARE CHANGE",
            vec![
                Line::from(""),
                Line::from(Span::styled(
                    "Preparing dry-run policy plan…",
                    Style::default().fg(Color::Yellow).bold(),
                )),
            ],
        );
    }
}

fn centered_rect(percent_x: u16, percent_y: u16, area: Rect) -> Rect {
    let vertical = Layout::vertical([
        Constraint::Percentage((100 - percent_y) / 2),
        Constraint::Percentage(percent_y),
        Constraint::Percentage((100 - percent_y) / 2),
    ])
    .split(area);
    Layout::horizontal([
        Constraint::Percentage((100 - percent_x) / 2),
        Constraint::Percentage(percent_x),
        Constraint::Percentage((100 - percent_x) / 2),
    ])
    .split(vertical[1])[1]
}

fn draw(frame: &mut Frame, app: &App) {
    let layout = Layout::vertical([
        Constraint::Length(3),
        Constraint::Min(4),
        Constraint::Length(1),
    ])
    .split(frame.area());
    frame.render_widget(
        Block::default().style(Style::default().bg(Color::Rgb(8, 15, 24))),
        frame.area(),
    );
    render_header(frame, app, layout[0]);
    render_body(frame, app, layout[1]);
    render_footer(frame, app, layout[2]);
    if app.show_help {
        render_help(frame, frame.area());
    }
    render_mutation_overlay(frame, app, frame.area());
}

fn run_app(terminal: &mut Terminal<CrosstermBackend<Stdout>>) -> io::Result<()> {
    let (tx, rx) = mpsc::channel();
    let mut app = App::new(tx, rx);
    app.load_current(false);
    let mut last_tick = Instant::now();
    while !app.should_quit {
        let body_height = terminal.size()?.height.saturating_sub(4);
        app.clamp_scroll(body_height);
        terminal.draw(|frame| draw(frame, &app))?;
        if event::poll(POLL_INTERVAL)? {
            if let Event::Key(key) = event::read()? {
                app.handle_key(key);
            }
        }
        app.receive_messages();
        if last_tick.elapsed() >= Duration::from_millis(250) {
            last_tick = Instant::now();
        }
    }
    Ok(())
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    enable_raw_mode()?;
    let mut stdout = io::stdout();
    execute!(stdout, EnterAlternateScreen)?;
    let backend = CrosstermBackend::new(stdout);
    let mut terminal = Terminal::new(backend)?;
    let result = run_app(&mut terminal);
    disable_raw_mode()?;
    execute!(terminal.backend_mut(), LeaveAlternateScreen)?;
    terminal.show_cursor()?;
    result?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn app() -> App {
        let (tx, rx) = mpsc::channel();
        App::new(tx, rx)
    }

    #[test]
    fn cached_page_does_not_start_another_request() {
        let mut app = app();
        app.pages.insert(
            Screen::Software,
            PageState {
                payload: Some(json!({"groups": []})),
                ..PageState::default()
            },
        );

        app.set_screen(Screen::Software);

        assert_eq!(app.request_id, 0);
        assert!(!app.loading());
        assert_eq!(app.status, "Software cached");
    }

    #[test]
    fn completed_background_page_is_cached_offscreen() {
        let mut app = app();
        let target = LoadTarget::Screen(Screen::Doctor);
        app.pages.insert(
            Screen::Doctor,
            PageState {
                loading: true,
                request: Some(7),
                ..PageState::default()
            },
        );
        app.tx
            .send(Message::Loaded {
                request: 7,
                target: target.clone(),
                payload: json!({"results": [{"status": "ok"}]}),
            })
            .unwrap();

        app.receive_messages();

        let state = app.state_for_target(&target).unwrap();
        assert!(state.has_content());
        assert!(!state.loading);
        assert_eq!(app.screen, Screen::Dashboard);
    }

    #[test]
    fn dashboard_result_seeds_the_doctor_page_cache() {
        let mut app = app();
        let target = LoadTarget::Screen(Screen::Dashboard);
        app.pages.insert(
            Screen::Dashboard,
            PageState {
                loading: true,
                request: Some(3),
                ..PageState::default()
            },
        );
        app.tx
            .send(Message::Loaded {
                request: 3,
                target,
                payload: json!({
                    "config": {},
                    "software": {},
                    "doctor": {"results": [{"status": "ok"}]}
                }),
            })
            .unwrap();

        app.receive_messages();
        app.set_screen(Screen::Doctor);

        assert_eq!(app.request_id, 0);
        assert!(app.current_has_content());
        assert_eq!(app.status, "Doctor cached");
    }

    #[test]
    fn search_cache_is_bounded_and_keeps_recent_queries() {
        let mut app = app();
        for index in 0..=SEARCH_CACHE_LIMIT {
            app.prepare_target(&LoadTarget::Search(format!("query-{index}")));
        }

        assert_eq!(app.search_cache.len(), SEARCH_CACHE_LIMIT);
        assert!(!app.search_cache.contains_key("query-0"));
        assert!(app
            .search_cache
            .contains_key(&format!("query-{SEARCH_CACHE_LIMIT}")));
    }

    #[test]
    fn software_entries_preserve_identity_and_availability() {
        let payload = json!({
            "groups": [{
                "id": "nix.user.package",
                "items": [{
                    "id": "git",
                    "version": "2.50",
                    "ref": "nix:git",
                    "effective": true,
                    "externalExclude": false,
                    "stale": false
                }]
            }]
        });

        let entries = software_entries(Some(&payload));

        assert_eq!(entries.len(), 1);
        assert_eq!(entries[0].group, "nix.user.package");
        assert_eq!(entries[0].item, "git");
        assert!(entries[0].effective);
        assert_eq!(entries[0].state, "effective");
    }

    #[test]
    fn mutation_envelope_error_is_not_treated_as_success() {
        let result = mutation_result(json!({
            "ok": false,
            "error": {"code": "blocked", "message": "shared policy blocks this item"}
        }));

        assert_eq!(result.unwrap_err(), "shared policy blocks this item");
    }

    #[test]
    fn mutation_commands_keep_preview_and_apply_separate() {
        let intent = MutationIntent {
            action: SoftwareAction::Add,
            group: "homebrew.system.cask".to_string(),
            item: "firefox".to_string(),
        };

        assert_eq!(
            mutation_args(MutationStage::Preview, &intent),
            [
                "sw",
                "add",
                "homebrew.system.cask",
                "firefox",
                "--dry-run",
                "--json"
            ]
        );
        assert_eq!(
            mutation_args(MutationStage::Apply, &intent),
            [
                "sw",
                "add",
                "homebrew.system.cask",
                "firefox",
                "--yes",
                "--json"
            ]
        );
    }

    #[test]
    fn mutation_response_must_match_the_previewed_item() {
        let intent = MutationIntent {
            action: SoftwareAction::Remove,
            group: "nix.user.package".to_string(),
            item: "git".to_string(),
        };
        let response = |item: &str| {
            json!({
                "schemaVersion": 1,
                "command": "software.rm",
                "ok": true,
                "data": {
                    "result": "dry-run",
                    "plan": {
                        "action": "rm",
                        "group": {"id": "nix.user.package"},
                        "item": item,
                        "expected": {"effective": false}
                    }
                }
            })
        };

        assert!(
            validate_mutation_response(MutationStage::Preview, &intent, response("git")).is_ok()
        );
        assert_eq!(
            validate_mutation_response(MutationStage::Preview, &intent, response("different-item"))
                .unwrap_err(),
            "software mutation plan does not match the selected item"
        );
    }

    #[test]
    fn preview_message_opens_confirmation_without_writing() {
        let mut app = app();
        let intent = MutationIntent {
            action: SoftwareAction::Remove,
            group: "nix.user.package".to_string(),
            item: "git".to_string(),
        };
        app.mutation_request = Some(9);
        app.mutation_loading = true;
        app.tx
            .send(Message::MutationFinished {
                request: 9,
                stage: MutationStage::Preview,
                intent: intent.clone(),
                result: Ok(json!({
                    "ok": true,
                    "data": {"result": "dry-run", "plan": {"changed": true}}
                })),
            })
            .unwrap();

        app.receive_messages();

        assert!(!app.mutation_loading);
        assert_eq!(app.pending_mutation.as_ref().unwrap().intent, intent);
    }

    #[test]
    fn successful_apply_invalidates_dependent_caches() {
        let mut app = app();
        app.screen = Screen::Search;
        app.pages.insert(
            Screen::Software,
            PageState {
                payload: Some(json!({"groups": []})),
                ..PageState::default()
            },
        );
        app.pages.insert(
            Screen::Doctor,
            PageState {
                payload: Some(json!({"results": []})),
                ..PageState::default()
            },
        );
        app.search_cache
            .insert("git".to_string(), PageState::default());
        app.search_order.push_back("git".to_string());
        app.mutation_request = Some(11);
        app.mutation_loading = true;
        app.pending_mutation = Some(MutationPreview {
            intent: MutationIntent {
                action: SoftwareAction::Remove,
                group: "nix.user.package".to_string(),
                item: "git".to_string(),
            },
            payload: json!({}),
        });
        app.tx
            .send(Message::MutationFinished {
                request: 11,
                stage: MutationStage::Apply,
                intent: app.pending_mutation.as_ref().unwrap().intent.clone(),
                result: Ok(json!({"ok": true})),
            })
            .unwrap();

        app.receive_messages();

        assert!(!app.pages.contains_key(&Screen::Software));
        assert!(!app.pages.contains_key(&Screen::Doctor));
        assert!(app.search_cache.is_empty());
        assert!(app.pending_mutation.is_none());
        assert!(!app.mutation_loading);
    }

    #[test]
    fn software_selection_stays_inside_the_viewport() {
        let mut app = app();
        app.screen = Screen::Software;
        app.visible_rows = 2;
        app.pages.insert(
            Screen::Software,
            PageState {
                payload: Some(json!({
                    "groups": [{
                        "id": "nix.user.package",
                        "items": (0..5).map(|index| json!({
                            "id": format!("item-{index}"),
                            "effective": true
                        })).collect::<Vec<_>>()
                    }]
                })),
                ..PageState::default()
            },
        );

        app.move_software_selection(1);
        app.move_software_selection(1);
        app.move_software_selection(1);

        assert_eq!(app.software_selected, 3);
        assert_eq!(app.scroll, 2);
    }

    #[test]
    fn empty_policy_operations_are_hidden() {
        assert_eq!(joined_strings(Some(&json!([]))), None);
        assert_eq!(
            joined_strings(Some(&json!(["neteasemusic"]))),
            Some("neteasemusic".to_string())
        );
    }

    #[test]
    fn fixed_popup_is_centered_without_filling_a_tall_terminal() {
        let area = Rect::new(0, 0, 150, 60);
        let popup = centered_size(94, 18, area);

        assert_eq!(popup, Rect::new(28, 21, 94, 18));
    }

    #[test]
    fn scroll_is_clamped_to_last_full_viewport() {
        let mut app = app();
        app.screen = Screen::Doctor;
        app.scroll = 200;
        app.pages.insert(
            Screen::Doctor,
            PageState {
                payload: Some(json!({
                    "results": (0..30).map(|index| json!({"name": index})).collect::<Vec<_>>()
                })),
                ..PageState::default()
            },
        );

        app.clamp_scroll(13);

        assert_eq!(app.scroll, 20);
    }
}
