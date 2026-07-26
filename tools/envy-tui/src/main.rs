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
    widgets::{Block, Borders, Cell, Clear, Paragraph, Row, Table, Tabs, Wrap},
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
    request_id: u64,
    tx: Sender<Message>,
    rx: Receiver<Message>,
    should_quit: bool,
    show_help: bool,
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
            request_id: 0,
            tx,
            rx,
            should_quit: false,
            show_help: false,
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
        let visible_rows = body_height.saturating_sub(3) as usize;
        let maximum = self.row_count().saturating_sub(visible_rows);
        self.scroll = self.scroll.min(maximum);
    }

    fn handle_key(&mut self, key: KeyEvent) {
        if key.kind != KeyEventKind::Press {
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
            KeyCode::Down | KeyCode::Char('j') => self.scroll = self.scroll.saturating_add(1),
            KeyCode::Up | KeyCode::Char('k') => self.scroll = self.scroll.saturating_sub(1),
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

fn text(value: Option<&Value>) -> String {
    match value {
        Some(Value::String(value)) => value.clone(),
        Some(Value::Bool(value)) => value.to_string(),
        Some(Value::Number(value)) => value.to_string(),
        Some(value) => value.to_string(),
        None => "—".to_string(),
    }
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
    let activity = if app.loading() {
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
            "  q quit  ? help  r refresh  Tab next  ↑↓ scroll",
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
    let mut rows = Vec::new();
    if let Some(groups) = app
        .payload()
        .and_then(|payload| payload.get("groups"))
        .and_then(Value::as_array)
    {
        for group in groups {
            let group_id = text(group.get("id"));
            if let Some(items) = group.get("items").and_then(Value::as_array) {
                for item in items {
                    let state = if item
                        .get("effective")
                        .and_then(Value::as_bool)
                        .unwrap_or(false)
                    {
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
                    rows.push(Row::new(vec![
                        Cell::from(group_id.clone()),
                        Cell::from(text(item.get("id"))),
                        Cell::from(text(item.get("version"))),
                        Cell::from(state),
                        Cell::from(text(item.get("ref"))),
                    ]));
                }
            }
        }
    }
    let offset = row_offset(app.scroll, rows.len(), area);
    let table = Table::new(
        rows.into_iter().skip(offset).collect::<Vec<_>>(),
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
    .block(
        Block::default()
            .title(" Software policy ")
            .borders(Borders::ALL)
            .border_style(Color::DarkGray),
    );
    frame.render_widget(table, area);
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
