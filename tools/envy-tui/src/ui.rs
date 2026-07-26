use ratatui::{
    prelude::*,
    widgets::{Block, Borders, Cell, Clear, Paragraph, Row, Table, TableState, Tabs, Wrap},
};
use serde_json::Value;

use crate::{
    app::{App, InputMode},
    model::{search_entries, text, DetailView, Screen, SoftwareAction},
};

const BACKGROUND: Color = Color::Rgb(8, 15, 24);
const PANEL: Color = Color::Rgb(18, 22, 30);
const SELECTED: Color = Color::Rgb(25, 45, 60);

pub fn row_offset(scroll: usize, row_count: usize, area: Rect) -> usize {
    let visible_rows = area.height.saturating_sub(3) as usize;
    scroll.min(row_count.saturating_sub(visible_rows))
}

fn selected_state(selected: usize, offset: usize, empty: bool) -> TableState {
    TableState::default().with_selected((!empty).then(|| selected.saturating_sub(offset)))
}

fn card<'a>(widget: Paragraph<'a>) -> Paragraph<'a> {
    widget.block(
        Block::default()
            .borders(Borders::ALL)
            .border_style(Color::DarkGray),
    )
}

fn render_header(frame: &mut Frame, app: &App, area: Rect) {
    let titles = Screen::ALL
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
        .collect::<Vec<_>>();
    frame.render_widget(
        Tabs::new(titles)
            .select(app.screen.index())
            .divider("│")
            .block(
                Block::default()
                    .title(" ENVY ")
                    .borders(Borders::ALL)
                    .border_style(Color::Cyan),
            ),
        area,
    );
}

fn page_keys(screen: Screen) -> &'static str {
    match screen {
        Screen::Software => "Enter toggle  w why  / filter",
        Screen::Search => "Enter add  / query",
        Screen::Doctor => "Enter details",
        Screen::History => "Space mark  d diff",
        Screen::Dashboard => "s search",
    }
}

fn render_footer(frame: &mut Frame, app: &App, area: Rect) {
    let mode = match app.input_mode {
        InputMode::Normal => "NORMAL",
        InputMode::Search => "SEARCH",
        InputMode::SoftwareFilter => "FILTER",
    };
    let context = match app.screen {
        Screen::Search => format!(
            "  query: {}",
            if app.query.is_empty() {
                "<empty>"
            } else {
                &app.query
            }
        ),
        Screen::Software if !app.software_filter.is_empty() => {
            format!("  filter: {}", app.software_filter)
        }
        _ => String::new(),
    };
    let activity = if app.mutation_loading {
        "  ◌ verifying"
    } else if app.loading() {
        if app.current_has_content() {
            "  ◌ refreshing"
        } else {
            "  ◌ loading"
        }
    } else {
        ""
    };
    frame.render_widget(
        Paragraph::new(Line::from(vec![
            Span::styled(
                format!(" {mode} "),
                Style::default().fg(Color::Black).bg(Color::Green).bold(),
            ),
            Span::styled(
                format!("  {}  ", app.status),
                Style::default().fg(Color::Gray),
            ),
            Span::styled(context, Style::default().fg(Color::Yellow)),
            Span::styled(activity, Style::default().fg(Color::Yellow)),
            Span::styled(
                format!(
                    "  {}  │  q quit  ? help  r refresh  Tab next",
                    page_keys(app.screen)
                ),
                Style::default().fg(Color::DarkGray),
            ),
        ])),
        area,
    );
}

fn render_dashboard(frame: &mut Frame, app: &App, area: Rect) {
    let payload = app.payload().unwrap_or(&Value::Null);
    let config = payload.get("config").unwrap_or(&Value::Null);
    let software = payload.get("software").unwrap_or(&Value::Null);
    let doctor = payload.get("doctor").unwrap_or(&Value::Null);
    let values = config.get("values").unwrap_or(&Value::Null);
    let machine = config
        .get("device")
        .and_then(|value| value.get("machineId"));
    let user = values
        .get("envy.user.name")
        .or_else(|| values.get("user.name"));
    let platform = config
        .get("platform")
        .or_else(|| values.get("envy.platform"))
        .or_else(|| config.get("device").and_then(|value| value.get("platform")));
    let summary = doctor.get("summary").unwrap_or(&Value::Null);
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
            "Workflow",
            Style::default().fg(Color::Cyan).bold(),
        )),
        Line::from("  Inspect policy → search registries → preview change"),
        Line::from("  Every write requires verified dry-run + confirmation"),
        Line::from("  1 dashboard  2 software  3 search  4 doctor  5 history"),
    ];
    if area.width >= 88 {
        let columns = Layout::horizontal([Constraint::Percentage(50), Constraint::Percentage(50)])
            .split(area);
        frame.render_widget(card(Paragraph::new(left)), columns[0]);
        frame.render_widget(card(Paragraph::new(right)), columns[1]);
    } else {
        let rows =
            Layout::vertical([Constraint::Percentage(50), Constraint::Percentage(50)]).split(area);
        frame.render_widget(card(Paragraph::new(left)), rows[0]);
        frame.render_widget(card(Paragraph::new(right)), rows[1]);
    }
}

fn render_software(frame: &mut Frame, app: &App, area: Rect) {
    let entries = app.software_entries();
    let total = crate::model::software_entries(app.payload()).len();
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
    let title = if app.software_filter.is_empty() {
        format!(" Software policy — {total} items ")
    } else {
        format!(" Software policy — {} / {total} visible ", entries.len())
    };
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
    .row_highlight_style(Style::default().bg(SELECTED))
    .highlight_symbol("▸ ")
    .block(
        Block::default()
            .title(title)
            .borders(Borders::ALL)
            .border_style(Color::DarkGray),
    );
    let mut state = selected_state(app.software_selected, offset, entries.is_empty());
    frame.render_stateful_widget(table, area, &mut state);
}

fn render_search(frame: &mut Frame, app: &App, area: Rect) {
    let entries = search_entries(app.payload());
    let offset = row_offset(app.scroll, entries.len(), area);
    let rows = entries
        .iter()
        .skip(offset)
        .map(|entry| {
            Row::new(vec![
                Cell::from(entry.source.clone()),
                Cell::from(entry.kind.clone()),
                Cell::from(entry.name.clone()),
                Cell::from(entry.version.clone()),
                Cell::from(entry.description.clone()),
                Cell::from(entry.reference.clone()),
            ])
        })
        .collect::<Vec<_>>();
    let title = if app.submitted_query.is_empty() {
        " Search registries — press / to query ".to_string()
    } else {
        format!(
            " Search: {} — {} results ",
            app.submitted_query,
            entries.len()
        )
    };
    let table = Table::new(
        rows,
        [
            Constraint::Length(12),
            Constraint::Length(12),
            Constraint::Length(26),
            Constraint::Length(12),
            Constraint::Min(24),
            Constraint::Length(34),
        ],
    )
    .header(
        Row::new([
            "SOURCE",
            "KIND",
            "NAME",
            "VERSION",
            "DESCRIPTION",
            "REFERENCE",
        ])
        .style(Style::default().fg(Color::Cyan).bold()),
    )
    .row_highlight_style(Style::default().bg(SELECTED))
    .highlight_symbol("▸ ")
    .block(
        Block::default()
            .title(title)
            .borders(Borders::ALL)
            .border_style(Color::DarkGray),
    );
    let mut state = selected_state(app.search_selected, offset, entries.is_empty());
    frame.render_stateful_widget(table, area, &mut state);
}

fn status_style(status: &str) -> Style {
    match status {
        "ok" => Style::default().fg(Color::Green),
        "warn" => Style::default().fg(Color::Yellow),
        "error" => Style::default().fg(Color::Red),
        _ => Style::default().fg(Color::Gray),
    }
}

fn render_doctor(frame: &mut Frame, app: &App, area: Rect) {
    let results = app
        .payload()
        .and_then(|payload| payload.get("results"))
        .and_then(Value::as_array);
    let count = results.map(Vec::len).unwrap_or(0);
    let offset = row_offset(app.scroll, count, area);
    let rows = results
        .map(|results| {
            results
                .iter()
                .skip(offset)
                .map(|result| {
                    let status = text(result.get("status"));
                    Row::new(vec![
                        Cell::from(status.clone()).style(status_style(&status)),
                        Cell::from(text(result.get("section"))),
                        Cell::from(text(result.get("name"))),
                        Cell::from(text(result.get("message"))),
                    ])
                })
                .collect::<Vec<_>>()
        })
        .unwrap_or_default();
    let table = Table::new(
        rows,
        [
            Constraint::Length(10),
            Constraint::Length(16),
            Constraint::Length(30),
            Constraint::Min(40),
        ],
    )
    .header(
        Row::new(["STATUS", "SECTION", "CHECK", "RESULT"])
            .style(Style::default().fg(Color::Cyan).bold()),
    )
    .row_highlight_style(Style::default().bg(SELECTED))
    .highlight_symbol("▸ ")
    .block(
        Block::default()
            .title(" Doctor — Enter shows complete details ")
            .borders(Borders::ALL)
            .border_style(Color::DarkGray),
    );
    let mut state = selected_state(app.doctor_selected, offset, count == 0);
    frame.render_stateful_widget(table, area, &mut state);
}

fn render_history(frame: &mut Frame, app: &App, area: Rect) {
    let generations = app
        .payload()
        .and_then(|payload| payload.get("generations"))
        .and_then(Value::as_array);
    let count = generations.map(Vec::len).unwrap_or(0);
    let offset = row_offset(app.scroll, count, area);
    let rows = generations
        .map(|generations| {
            generations
                .iter()
                .skip(offset)
                .map(|generation| {
                    let number = generation.get("number").and_then(Value::as_u64);
                    let current = generation.get("current").and_then(Value::as_bool) == Some(true);
                    let state = match (current, number == app.history_marked) {
                        (true, true) => "current · marked",
                        (true, false) => "current",
                        (false, true) => "marked",
                        _ => "",
                    };
                    Row::new(vec![
                        Cell::from(text(generation.get("number"))),
                        Cell::from(state),
                        Cell::from(text(generation.get("createdAt"))),
                        Cell::from(text(generation.get("path"))),
                        Cell::from(text(generation.get("target"))),
                    ])
                })
                .collect::<Vec<_>>()
        })
        .unwrap_or_default();
    let table = Table::new(
        rows,
        [
            Constraint::Length(12),
            Constraint::Length(18),
            Constraint::Length(28),
            Constraint::Length(38),
            Constraint::Min(40),
        ],
    )
    .header(
        Row::new(["GENERATION", "STATE", "CREATED", "PROFILE", "STORE TARGET"])
            .style(Style::default().fg(Color::Cyan).bold()),
    )
    .row_highlight_style(Style::default().bg(SELECTED))
    .highlight_symbol("▸ ")
    .block(
        Block::default()
            .title(" Generations — Space marks first, d compares ")
            .borders(Borders::ALL)
            .border_style(Color::DarkGray),
    );
    let mut state = selected_state(app.history_selected, offset, count == 0);
    frame.render_stateful_widget(table, area, &mut state);
}

fn render_body(frame: &mut Frame, app: &App, area: Rect) {
    if let Some(error) = app.current_error().filter(|_| !app.current_has_content()) {
        frame.render_widget(
            Paragraph::new(vec![
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
            ),
            area,
        );
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
        frame.render_widget(Clear, area);
        frame.render_widget(
            Paragraph::new("  Loading complete Envy data…")
                .style(Style::default().fg(Color::Yellow))
                .block(Block::default().borders(Borders::ALL)),
            area,
        );
    }
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

fn popup(frame: &mut Frame, area: Rect, title: &str, lines: Vec<Line<'static>>, scroll: usize) {
    frame.render_widget(Clear, area);
    let block = Block::default()
        .title(format!(" {title} "))
        .borders(Borders::ALL)
        .border_style(Color::Cyan)
        .style(Style::default().bg(PANEL));
    let inner = inset_rect(block.inner(area), 2, 1);
    frame.render_widget(block, area);
    frame.render_widget(
        Paragraph::new(lines)
            .wrap(Wrap { trim: false })
            .scroll((scroll.min(u16::MAX as usize) as u16, 0)),
        inner,
    );
}

fn key_footer() -> Line<'static> {
    Line::from(vec![
        Span::styled(
            " ENTER ",
            Style::default().fg(Color::Black).bg(Color::Cyan).bold(),
        ),
        Span::raw(" close    "),
        Span::styled(
            " ↑↓ ",
            Style::default().fg(Color::White).bg(Color::DarkGray).bold(),
        ),
        Span::raw(" scroll"),
    ])
}

fn bool_line(label: &'static str, value: Option<&Value>) -> Line<'static> {
    let enabled = value.and_then(Value::as_bool).unwrap_or(false);
    Line::from(vec![
        Span::styled(format!("{label:<18}"), Style::default().fg(Color::DarkGray)),
        Span::styled(
            if enabled { "yes" } else { "no" },
            Style::default().fg(if enabled { Color::Green } else { Color::Gray }),
        ),
    ])
}

fn software_detail_lines(payload: &Value) -> Vec<Line<'static>> {
    let matched = payload
        .get("matches")
        .and_then(Value::as_array)
        .and_then(|matches| matches.first())
        .unwrap_or(&Value::Null);
    let reason = if matched.get("machineExclude").and_then(Value::as_bool) == Some(true) {
        "Disabled by this machine's managed exclusion."
    } else if matched.get("externalExclude").and_then(Value::as_bool) == Some(true) {
        "Blocked by policy outside the machine-managed block."
    } else if matched.get("machineInclude").and_then(Value::as_bool) == Some(true) {
        "Included directly by this machine's managed policy."
    } else if matched.get("externalInclude").and_then(Value::as_bool) == Some(true) {
        "Included by shared or feature-owned policy."
    } else if matched.get("effective").and_then(Value::as_bool) == Some(true) {
        "Effective through evaluated policy."
    } else {
        "Not effective in the evaluated machine policy."
    };
    vec![
        Line::from(vec![
            Span::styled("ITEM  ", Style::default().fg(Color::DarkGray)),
            Span::styled(
                text(matched.get("item")),
                Style::default().fg(Color::White).bold(),
            ),
        ]),
        Line::from(format!("Group       {}", text(matched.get("group")))),
        Line::from(format!("Label       {}", text(matched.get("label")))),
        Line::from(format!("Name        {}", text(matched.get("name")))),
        Line::from(format!("Reference   {}", text(matched.get("ref")))),
        Line::from(""),
        Line::from(Span::styled(
            "Evaluated state",
            Style::default().fg(Color::Cyan).bold(),
        )),
        bool_line("Included", matched.get("included")),
        bool_line("Excluded", matched.get("excluded")),
        bool_line("Effective", matched.get("effective")),
        Line::from(""),
        Line::from(Span::styled(
            "Ownership",
            Style::default().fg(Color::Cyan).bold(),
        )),
        bool_line("Machine include", matched.get("machineInclude")),
        bool_line("Machine exclude", matched.get("machineExclude")),
        bool_line("External include", matched.get("externalInclude")),
        bool_line("External exclude", matched.get("externalExclude")),
        Line::from(""),
        Line::from(Span::styled("Why", Style::default().fg(Color::Cyan).bold())),
        Line::from(reason),
        Line::from(""),
        key_footer(),
    ]
}

fn json_lines(value: Option<&Value>) -> Vec<Line<'static>> {
    match value {
        None | Some(Value::Null) => vec![Line::from("None")],
        Some(value) => serde_json::to_string_pretty(value)
            .unwrap_or_else(|_| value.to_string())
            .lines()
            .map(|line| Line::from(line.to_string()))
            .collect(),
    }
}

fn doctor_detail_lines(result: &Value) -> Vec<Line<'static>> {
    let status = text(result.get("status"));
    let mut lines = vec![
        Line::from(vec![
            Span::styled(
                format!(" {} ", status.to_uppercase()),
                status_style(&status)
                    .fg(Color::Black)
                    .bg(match status.as_str() {
                        "ok" => Color::Green,
                        "warn" => Color::Yellow,
                        "error" => Color::Red,
                        _ => Color::Gray,
                    })
                    .bold(),
            ),
            Span::styled(
                format!("  {}", text(result.get("name"))),
                Style::default().fg(Color::White).bold(),
            ),
        ]),
        Line::from(format!("Section  {}", text(result.get("section")))),
        Line::from(""),
        Line::from(Span::styled(
            "Result",
            Style::default().fg(Color::Cyan).bold(),
        )),
        Line::from(text(result.get("message"))),
        Line::from(""),
        Line::from(Span::styled(
            "Hint",
            Style::default().fg(Color::Cyan).bold(),
        )),
        Line::from(text(result.get("hint"))),
        Line::from(""),
        Line::from(Span::styled(
            "Details",
            Style::default().fg(Color::Cyan).bold(),
        )),
    ];
    lines.extend(json_lines(result.get("details")));
    lines.push(Line::from(""));
    lines.push(Line::from(Span::styled(
        "Action (not executed)",
        Style::default().fg(Color::Cyan).bold(),
    )));
    lines.extend(json_lines(result.get("action")));
    lines.push(Line::from(""));
    lines.push(key_footer());
    lines
}

fn strip_ansi(value: &str) -> String {
    let mut result = String::new();
    let mut chars = value.chars().peekable();
    while let Some(character) = chars.next() {
        if character == '\u{1b}' && chars.peek() == Some(&'[') {
            chars.next();
            for next in chars.by_ref() {
                if next.is_ascii_alphabetic() {
                    break;
                }
            }
        } else {
            result.push(character);
        }
    }
    result
}

fn history_diff_lines(payload: &Value) -> Vec<Line<'static>> {
    let before = payload.get("before").unwrap_or(&Value::Null);
    let after = payload.get("after").unwrap_or(&Value::Null);
    let diff = payload
        .get("closureDiff")
        .and_then(Value::as_str)
        .map(strip_ansi)
        .unwrap_or_else(|| "No closure changes reported.".to_string());
    let mut lines = vec![
        Line::from(vec![
            Span::styled(
                text(before.get("number")),
                Style::default().fg(Color::Yellow).bold(),
            ),
            Span::raw("  →  "),
            Span::styled(
                text(after.get("number")),
                Style::default().fg(Color::Green).bold(),
            ),
        ]),
        Line::from(""),
        Line::from(Span::styled(
            "Before",
            Style::default().fg(Color::Cyan).bold(),
        )),
        Line::from(format!("Created  {}", text(before.get("createdAt")))),
        Line::from(format!("Profile  {}", text(before.get("path")))),
        Line::from(format!("Target   {}", text(before.get("target")))),
        Line::from(""),
        Line::from(Span::styled(
            "After",
            Style::default().fg(Color::Cyan).bold(),
        )),
        Line::from(format!("Created  {}", text(after.get("createdAt")))),
        Line::from(format!("Profile  {}", text(after.get("path")))),
        Line::from(format!("Target   {}", text(after.get("target")))),
        Line::from(""),
        Line::from(Span::styled(
            "Closure diff",
            Style::default().fg(Color::Cyan).bold(),
        )),
    ];
    lines.extend(diff.lines().map(|line| Line::from(line.to_string())));
    lines.push(Line::from(""));
    lines.push(key_footer());
    lines
}

fn render_detail(frame: &mut Frame, app: &App, area: Rect, detail: &DetailView) {
    match detail {
        DetailView::Loading { title } => popup(
            frame,
            centered_size(64, 8, area),
            title,
            vec![
                Line::from(""),
                Line::from(Span::styled(
                    "Loading complete details…",
                    Style::default().fg(Color::Yellow).bold(),
                )),
            ],
            0,
        ),
        DetailView::Software(payload) => popup(
            frame,
            centered_size(82, 25, area),
            "SOFTWARE WHY",
            software_detail_lines(payload),
            app.detail_scroll,
        ),
        DetailView::Doctor(result) => popup(
            frame,
            centered_size(90, 28, area),
            "DOCTOR DETAILS",
            doctor_detail_lines(result),
            app.detail_scroll,
        ),
        DetailView::HistoryDiff(payload) => popup(
            frame,
            centered_size(100, 28, area),
            "GENERATION DIFF",
            history_diff_lines(payload),
            app.detail_scroll,
        ),
    }
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

fn render_mutation(frame: &mut Frame, app: &App, area: Rect) {
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
        let color = match preview.intent.action {
            SoftwareAction::Add => Color::Green,
            SoftwareAction::Remove => Color::Yellow,
        };
        let mut lines = vec![
            Line::from(vec![
                Span::styled(
                    format!(" {} ", preview.intent.action.label().to_uppercase()),
                    Style::default().fg(Color::Black).bg(color).bold(),
                ),
                Span::styled(
                    format!("  {}", preview.intent.item),
                    Style::default().fg(Color::White).bold(),
                ),
            ]),
            Line::from(""),
            Line::from(format!("Group       {}", preview.intent.group)),
            Line::from(format!("Operand     {}", preview.intent.operand)),
            Line::from(format!("Result      {effective}")),
            Line::from(format!("Changed     {changed}")),
            Line::from("Verified    dry-run JSON schema v1"),
            Line::from(""),
            Line::from(Span::styled(
                "Policy operations",
                Style::default().fg(Color::Cyan).bold(),
            )),
        ];
        let mut operation_count = 0;
        for (label, color, value) in [
            ("Add include", Color::Green, plan.get("includeAdded")),
            ("Remove include", Color::Red, plan.get("includeRemoved")),
            ("Add exclusion", Color::Yellow, plan.get("excludeAdded")),
            ("Remove exclusion", Color::Cyan, plan.get("excludeRemoved")),
        ] {
            if let Some(items) = joined_strings(value) {
                operation_count += 1;
                lines.push(Line::from(vec![
                    Span::styled(format!("{label:<18}"), Style::default().fg(color)),
                    Span::styled(items, Style::default().fg(Color::White).bold()),
                ]));
            }
        }
        if operation_count == 0 {
            lines.push(Line::from(Span::styled(
                "No policy edits are required.",
                Style::default().fg(Color::DarkGray),
            )));
        }
        if let Some(reason) = blocked {
            lines.push(Line::from(""));
            lines.push(Line::from(Span::styled(
                format!("Blocked: {reason}"),
                Style::default().fg(Color::Red).bold(),
            )));
        } else {
            lines.push(Line::from(""));
            lines.push(Line::from(vec![
                Span::styled(
                    " ENTER ",
                    Style::default().fg(Color::Black).bg(Color::Green).bold(),
                ),
                Span::raw(" Apply    "),
                Span::styled(
                    " ESC ",
                    Style::default().fg(Color::White).bg(Color::DarkGray).bold(),
                ),
                Span::raw(" Cancel"),
            ]));
        }
        popup(
            frame,
            centered_size(86, 22, area),
            "CONFIRM SOFTWARE CHANGE",
            lines,
            0,
        );
    } else if app.mutation_loading {
        popup(
            frame,
            centered_size(64, 8, area),
            "VERIFYING SOFTWARE CHANGE",
            vec![
                Line::from(""),
                Line::from(Span::styled(
                    "Preparing dry-run policy plan…",
                    Style::default().fg(Color::Yellow).bold(),
                )),
            ],
            0,
        );
    }
}

fn render_group_chooser(frame: &mut Frame, app: &App, area: Rect) {
    let Some(chooser) = &app.group_chooser else {
        return;
    };
    let mut lines = vec![
        Line::from(vec![
            Span::styled("ADD  ", Style::default().fg(Color::Green).bold()),
            Span::styled(
                chooser.entry.name.clone(),
                Style::default().fg(Color::White).bold(),
            ),
        ]),
        Line::from(format!(
            "{} · {} · {}",
            chooser.entry.ecosystem, chooser.entry.kind, chooser.entry.reference
        )),
        Line::from(format!("Publisher    {}", chooser.entry.publisher)),
        Line::from(format!("Homepage     {}", chooser.entry.homepage)),
        Line::from(format!("Description  {}", chooser.entry.description)),
        Line::from(""),
        Line::from(Span::styled(
            "Choose a compatible managed group",
            Style::default().fg(Color::Cyan).bold(),
        )),
    ];
    for (index, group) in chooser.groups.iter().enumerate() {
        lines.push(Line::from(vec![
            Span::styled(
                if index == chooser.selected {
                    "▸ "
                } else {
                    "  "
                },
                Style::default().fg(Color::Cyan),
            ),
            Span::styled(
                group.id.clone(),
                if index == chooser.selected {
                    Style::default().fg(Color::White).bg(SELECTED).bold()
                } else {
                    Style::default().fg(Color::Gray)
                },
            ),
            Span::raw(format!("  {} · {}", group.scope, group.label)),
        ]));
    }
    lines.push(Line::from(""));
    lines.push(Line::from(
        "Enter prepares a verified dry-run; Esc cancels.",
    ));
    popup(
        frame,
        centered_size(88, (chooser.groups.len() as u16 + 14).min(27), area),
        "SELECT SOFTWARE GROUP",
        lines,
        0,
    );
}

fn render_help(frame: &mut Frame, area: Rect) {
    popup(
        frame,
        centered_size(78, 27, area),
        "KEYBOARD",
        vec![
            Line::from("1..5        jump to a page"),
            Line::from("Tab / ←→    switch pages"),
            Line::from("↑↓ / j k    select rows; detail dialogs scroll"),
            Line::from("s           search from any page"),
            Line::from("r           refresh current page"),
            Line::from(""),
            Line::from(Span::styled(
                "Software",
                Style::default().fg(Color::Cyan).bold(),
            )),
            Line::from("Enter/Space  preview availability toggle"),
            Line::from("w / i        explain selected software policy"),
            Line::from("/            local text filter (no backend request)"),
            Line::from("Esc          clear active filter"),
            Line::from(""),
            Line::from(Span::styled(
                "Search",
                Style::default().fg(Color::Cyan).bold(),
            )),
            Line::from("/            edit registry query"),
            Line::from("Enter / a    choose group, then preview add"),
            Line::from(""),
            Line::from(Span::styled(
                "Doctor / History",
                Style::default().fg(Color::Cyan).bold(),
            )),
            Line::from("Doctor Enter opens all check details; actions stay read-only"),
            Line::from("History Space marks one generation; d compares another"),
            Line::from(""),
            Line::from("Every mutation: dry-run → contract validation → explicit confirmation."),
            Line::from("Press ? or Esc to close."),
        ],
        0,
    );
}

fn render_overlays(frame: &mut Frame, app: &App) {
    let area = frame.area();
    if let Some(error) = &app.overlay_error {
        popup(
            frame,
            centered_size(78, 12, area),
            "REQUEST FAILED",
            vec![
                Line::from(""),
                Line::from(Span::styled(error.clone(), Style::default().fg(Color::Red))),
                Line::from(""),
                Line::from("Enter or Esc closes this message; cached data remains available."),
            ],
            0,
        );
    } else if app.pending_mutation.is_some() || app.mutation_loading {
        render_mutation(frame, app, area);
    } else if app.group_chooser.is_some() {
        render_group_chooser(frame, app, area);
    } else if let Some(detail) = &app.detail {
        render_detail(frame, app, area, detail);
    } else if app.show_help {
        render_help(frame, area);
    }
}

pub fn draw(frame: &mut Frame, app: &App) {
    let layout = Layout::vertical([
        Constraint::Length(3),
        Constraint::Min(4),
        Constraint::Length(1),
    ])
    .split(frame.area());
    frame.render_widget(
        Block::default().style(Style::default().bg(BACKGROUND)),
        frame.area(),
    );
    render_header(frame, app, layout[0]);
    render_body(frame, app, layout[1]);
    render_footer(frame, app, layout[2]);
    render_overlays(frame, app);
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn scroll_is_clamped_to_last_full_viewport() {
        assert_eq!(row_offset(200, 30, Rect::new(0, 0, 100, 13)), 20);
    }

    #[test]
    fn popup_is_fixed_and_centered_on_tall_terminal() {
        assert_eq!(
            centered_size(94, 18, Rect::new(0, 0, 150, 60)),
            Rect::new(28, 21, 94, 18)
        );
    }

    #[test]
    fn ansi_is_removed_from_closure_diff() {
        assert_eq!(
            strip_ansi("envy: \u{1b}[31;1m16 KiB\u{1b}[0m"),
            "envy: 16 KiB"
        );
    }
}
