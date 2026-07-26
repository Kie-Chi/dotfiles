use std::{
    collections::{HashMap, VecDeque},
    sync::mpsc::{Receiver, Sender},
};

use crossterm::event::{KeyCode, KeyEvent, KeyEventKind, KeyModifiers, MouseEvent, MouseEventKind};
use serde_json::Value;

use crate::{
    backend::{
        spawn_history_diff, spawn_mutation, spawn_request, spawn_search_groups, spawn_software_why,
    },
    model::{
        compatible_groups, filtered_software_entries, generation_number, generation_rows,
        result_rows, search_entries, DetailView, GroupChooser, LoadTarget, Message, MutationIntent,
        MutationPreview, MutationStage, PageState, Pages, Screen, SoftwareAction,
    },
};

const SEARCH_CACHE_LIMIT: usize = 12;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum InputMode {
    Normal,
    Search,
    SoftwareFilter,
}

pub struct App {
    pub screen: Screen,
    pub pages: Pages,
    pub search_cache: HashMap<String, PageState>,
    search_order: VecDeque<String>,
    pub status: String,
    pub query: String,
    pub submitted_query: String,
    pub software_filter: String,
    pub input_mode: InputMode,
    pub scroll: usize,
    pub visible_rows: usize,
    pub software_selected: usize,
    pub search_selected: usize,
    pub doctor_selected: usize,
    pub history_selected: usize,
    pub history_marked: Option<u64>,
    request_id: u64,
    tx: Sender<Message>,
    rx: Receiver<Message>,
    pub should_quit: bool,
    pub show_help: bool,
    mutation_request: Option<u64>,
    pub mutation_loading: bool,
    pub pending_mutation: Option<MutationPreview>,
    pub overlay_error: Option<String>,
    detail_request: Option<u64>,
    pub detail: Option<DetailView>,
    pub detail_scroll: usize,
    pub detail_scroll_max: usize,
    group_request: Option<u64>,
    pub group_chooser: Option<GroupChooser>,
}

impl App {
    pub fn new(tx: Sender<Message>, rx: Receiver<Message>) -> Self {
        Self {
            screen: Screen::Dashboard,
            pages: HashMap::new(),
            search_cache: HashMap::new(),
            search_order: VecDeque::new(),
            status: "Loading dashboard".to_string(),
            query: String::new(),
            submitted_query: String::new(),
            software_filter: String::new(),
            input_mode: InputMode::Normal,
            scroll: 0,
            visible_rows: 1,
            software_selected: 0,
            search_selected: 0,
            doctor_selected: 0,
            history_selected: 0,
            history_marked: None,
            request_id: 0,
            tx,
            rx,
            should_quit: false,
            show_help: false,
            mutation_request: None,
            mutation_loading: false,
            pending_mutation: None,
            overlay_error: None,
            detail_request: None,
            detail: None,
            detail_scroll: 0,
            detail_scroll_max: 0,
            group_request: None,
            group_chooser: None,
        }
    }

    pub fn current_target(&self) -> Option<LoadTarget> {
        match self.screen {
            Screen::Search if self.submitted_query.is_empty() => None,
            Screen::Search => Some(LoadTarget::Search(self.submitted_query.clone())),
            screen => Some(LoadTarget::Screen(screen)),
        }
    }

    pub fn state_for_target(&self, target: &LoadTarget) -> Option<&PageState> {
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

    pub fn current_state(&self) -> Option<&PageState> {
        self.current_target()
            .as_ref()
            .and_then(|target| self.state_for_target(target))
    }

    pub fn payload(&self) -> Option<&Value> {
        self.current_state()
            .and_then(|state| state.payload.as_ref())
    }

    pub fn loading(&self) -> bool {
        self.current_state()
            .map(|state| state.loading)
            .unwrap_or(false)
    }

    pub fn current_error(&self) -> Option<&str> {
        self.current_state()
            .and_then(|state| state.error.as_deref())
    }

    pub fn current_has_content(&self) -> bool {
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

    pub fn load_current(&mut self, force: bool) {
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
        self.input_mode = InputMode::Normal;
        self.load_current(false);
    }

    fn next_screen(&mut self, delta: isize) {
        let count = Screen::ALL.len() as isize;
        let next = (self.screen.index() as isize + delta).rem_euclid(count) as usize;
        self.set_screen(Screen::ALL[next]);
    }

    pub fn software_entries(&self) -> Vec<crate::model::SoftwareEntry> {
        filtered_software_entries(self.payload(), &self.software_filter)
    }

    pub fn row_count(&self) -> usize {
        match self.screen {
            Screen::Software => self.software_entries().len(),
            Screen::Search | Screen::Doctor => result_rows(self.payload()),
            Screen::History => generation_rows(self.payload()),
            Screen::Dashboard => 0,
        }
    }

    fn selected(&self) -> usize {
        match self.screen {
            Screen::Software => self.software_selected,
            Screen::Search => self.search_selected,
            Screen::Doctor => self.doctor_selected,
            Screen::History => self.history_selected,
            Screen::Dashboard => 0,
        }
    }

    fn set_selected(&mut self, value: usize) {
        match self.screen {
            Screen::Software => self.software_selected = value,
            Screen::Search => self.search_selected = value,
            Screen::Doctor => self.doctor_selected = value,
            Screen::History => self.history_selected = value,
            Screen::Dashboard => {}
        }
    }

    fn move_selection(&mut self, delta: isize) {
        let count = self.row_count();
        if count == 0 {
            self.set_selected(0);
            self.scroll = 0;
            return;
        }
        let selected =
            (self.selected() as isize + delta).clamp(0, count.saturating_sub(1) as isize) as usize;
        self.set_selected(selected);
        if selected < self.scroll {
            self.scroll = selected;
        } else if selected >= self.scroll + self.visible_rows {
            self.scroll = selected.saturating_add(1).saturating_sub(self.visible_rows);
        }
    }

    fn move_selection_to(&mut self, target: usize) {
        let count = self.row_count();
        if count == 0 {
            self.set_selected(0);
            self.scroll = 0;
            return;
        }
        let selected = target.min(count - 1);
        self.set_selected(selected);
        if selected < self.scroll {
            self.scroll = selected;
        } else if selected >= self.scroll + self.visible_rows {
            self.scroll = selected.saturating_add(1).saturating_sub(self.visible_rows);
        }
    }

    fn move_selection_page(&mut self, direction: isize) {
        let distance = self.visible_rows.max(1) as isize;
        self.move_selection(direction.saturating_mul(distance));
    }

    pub fn selection_position(&self) -> Option<(usize, usize)> {
        let count = self.row_count();
        (count > 0).then(|| (self.selected() + 1, count))
    }

    pub fn input_bar_height(&self) -> u16 {
        match self.screen {
            Screen::Search => 3,
            Screen::Software
                if self.input_mode == InputMode::SoftwareFilter
                    || !self.software_filter.is_empty() =>
            {
                3
            }
            _ => 0,
        }
    }

    pub fn clamp_scroll(&mut self, body_height: u16) {
        self.visible_rows = (body_height.saturating_sub(3) as usize).max(1);
        let count = self.row_count();
        let selected = self.selected().min(count.saturating_sub(1));
        self.set_selected(selected);
        if selected < self.scroll {
            self.scroll = selected;
        } else if selected >= self.scroll + self.visible_rows {
            self.scroll = selected.saturating_add(1).saturating_sub(self.visible_rows);
        }
        self.scroll = self.scroll.min(count.saturating_sub(self.visible_rows));
    }

    fn begin_mutation(&mut self, intent: MutationIntent) {
        self.request_id += 1;
        let request = self.request_id;
        self.mutation_request = Some(request);
        self.mutation_loading = true;
        self.overlay_error = None;
        self.group_chooser = None;
        self.status = format!(
            "Preparing {} plan for {}",
            intent.action.label(),
            intent.item
        );
        spawn_mutation(self.tx.clone(), request, MutationStage::Preview, intent);
    }

    fn begin_selected_mutation(&mut self) {
        let Some(entry) = self.software_entries().get(self.software_selected).cloned() else {
            self.status = "No software item selected".to_string();
            return;
        };
        self.begin_mutation(MutationIntent {
            action: if entry.effective {
                SoftwareAction::Remove
            } else {
                SoftwareAction::Add
            },
            group: entry.group,
            operand: entry.item.clone(),
            item: entry.item,
        });
    }

    fn apply_pending_mutation(&mut self) {
        let Some(preview) = self.pending_mutation.as_ref() else {
            return;
        };
        if let Some(reason) = preview
            .payload
            .get("data")
            .and_then(|data| data.get("plan"))
            .and_then(|plan| plan.get("blocked"))
            .and_then(Value::as_str)
        {
            let reason = reason.to_string();
            self.pending_mutation = None;
            self.overlay_error = Some(format!("Policy blocks this change: {reason}"));
            self.status = "Software change blocked".to_string();
            return;
        }
        let intent = preview.intent.clone();
        self.request_id += 1;
        let request = self.request_id;
        self.mutation_request = Some(request);
        self.mutation_loading = true;
        self.status = format!("Applying {} for {}", intent.action.label(), intent.item);
        spawn_mutation(self.tx.clone(), request, MutationStage::Apply, intent);
    }

    fn begin_why(&mut self) {
        let Some(entry) = self.software_entries().get(self.software_selected).cloned() else {
            self.status = "No software item selected".to_string();
            return;
        };
        self.request_id += 1;
        let request = self.request_id;
        self.detail_request = Some(request);
        self.detail = Some(DetailView::Loading {
            title: format!("WHY {}", entry.item),
        });
        self.detail_scroll = 0;
        self.detail_scroll_max = 0;
        spawn_software_why(self.tx.clone(), request, entry.group, entry.item);
    }

    fn begin_search_add(&mut self) {
        let Some(entry) = search_entries(self.payload())
            .get(self.search_selected)
            .cloned()
        else {
            self.status = "No search result selected".to_string();
            return;
        };
        if let Some(payload) = self
            .pages
            .get(&Screen::Software)
            .and_then(|state| state.payload.as_ref())
            .cloned()
        {
            self.open_group_chooser(entry, Some(&payload));
            return;
        }
        self.request_id += 1;
        let request = self.request_id;
        self.group_request = Some(request);
        self.detail = Some(DetailView::Loading {
            title: "FINDING COMPATIBLE GROUPS".to_string(),
        });
        spawn_search_groups(self.tx.clone(), request, entry);
    }

    fn open_group_chooser(&mut self, entry: crate::model::SearchEntry, payload: Option<&Value>) {
        let groups = compatible_groups(&entry, payload);
        self.detail = None;
        if groups.is_empty() {
            self.overlay_error = Some(format!(
                "No managed group accepts {} {} results. Search remains read-only.",
                entry.ecosystem, entry.kind
            ));
        } else {
            self.group_chooser = Some(GroupChooser {
                entry,
                groups,
                selected: 0,
            });
        }
    }

    fn confirm_group(&mut self) {
        let Some(chooser) = self.group_chooser.as_ref() else {
            return;
        };
        let Some(group) = chooser.groups.get(chooser.selected) else {
            return;
        };
        let operand = if chooser.entry.reference == "—" || chooser.entry.reference.is_empty() {
            chooser.entry.name.clone()
        } else {
            chooser.entry.reference.clone()
        };
        self.begin_mutation(MutationIntent {
            action: SoftwareAction::Add,
            group: group.id.clone(),
            operand,
            item: chooser.entry.name.clone(),
        });
    }

    fn open_doctor_detail(&mut self) {
        let Some(result) = self
            .payload()
            .and_then(|payload| payload.get("results"))
            .and_then(Value::as_array)
            .and_then(|results| results.get(self.doctor_selected))
            .cloned()
        else {
            return;
        };
        self.detail = Some(DetailView::Doctor(result));
        self.detail_scroll = 0;
        self.detail_scroll_max = 0;
    }

    fn begin_history_diff(&mut self) {
        let Some(selected) = generation_number(self.payload(), self.history_selected) else {
            self.status = "No generation selected".to_string();
            return;
        };
        let current = self
            .payload()
            .and_then(|payload| payload.get("generations"))
            .and_then(Value::as_array)
            .and_then(|generations| {
                generations.iter().find(|generation| {
                    generation.get("current").and_then(Value::as_bool) == Some(true)
                })
            })
            .and_then(|generation| generation.get("number"))
            .and_then(Value::as_u64);
        let other = self.history_marked.or(current);
        let Some(other) = other else {
            self.overlay_error = Some("Mark another generation with Space first.".to_string());
            return;
        };
        if other == selected {
            self.overlay_error = Some("Select two different generations to compare.".to_string());
            return;
        }
        let (before, after) = if other < selected {
            (other, selected)
        } else {
            (selected, other)
        };
        self.request_id += 1;
        let request = self.request_id;
        self.detail_request = Some(request);
        self.detail = Some(DetailView::Loading {
            title: format!("DIFF {before} → {after}"),
        });
        self.detail_scroll = 0;
        self.detail_scroll_max = 0;
        spawn_history_diff(self.tx.clone(), request, before, after);
    }

    fn invalidate_after_mutation(&mut self) {
        for screen in [Screen::Dashboard, Screen::Software, Screen::Doctor] {
            self.pages.remove(&screen);
        }
        self.search_cache.clear();
        self.search_order.clear();
        self.scroll = 0;
    }

    pub fn receive_messages(&mut self) {
        while let Ok(message) = self.rx.try_recv() {
            match message {
                Message::Loaded {
                    request,
                    target,
                    payload,
                } => {
                    let is_current = self.current_target().as_ref() == Some(&target);
                    let dashboard_doctor = (target == LoadTarget::Screen(Screen::Dashboard))
                        .then(|| payload.get("doctor").cloned())
                        .flatten();
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
                        let count = self.row_count();
                        self.set_selected(self.selected().min(count.saturating_sub(1)));
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
                            self.status = format!("{description}; refreshing data");
                        }
                        (_, Err(error)) => {
                            self.pending_mutation = None;
                            self.overlay_error = Some(error);
                            self.status = format!("{} failed", intent.action.label());
                        }
                    }
                }
                Message::MutationFinished { .. } => {}
                Message::SoftwareWhyFinished { request, result }
                    if self.detail_request == Some(request) =>
                {
                    self.detail_request = None;
                    match result {
                        Ok(payload) => self.detail = Some(DetailView::Software(payload)),
                        Err(error) => {
                            self.detail = None;
                            self.overlay_error = Some(error);
                        }
                    }
                }
                Message::SearchGroupsFinished {
                    request,
                    entry,
                    software,
                } if self.group_request == Some(request) => {
                    self.group_request = None;
                    match software {
                        Ok(payload) => {
                            self.pages.entry(Screen::Software).or_default().payload =
                                Some(payload.clone());
                            self.open_group_chooser(entry, Some(&payload));
                        }
                        Err(error) => {
                            self.detail = None;
                            self.overlay_error = Some(error);
                        }
                    }
                }
                Message::HistoryDiffFinished { request, result }
                    if self.detail_request == Some(request) =>
                {
                    self.detail_request = None;
                    match result {
                        Ok(payload) => self.detail = Some(DetailView::HistoryDiff(payload)),
                        Err(error) => {
                            self.detail = None;
                            self.overlay_error = Some(error);
                        }
                    }
                }
                _ => {}
            }
        }
    }

    fn handle_input(&mut self, key: KeyEvent) -> bool {
        match self.input_mode {
            InputMode::Normal => false,
            InputMode::Search => {
                match key.code {
                    KeyCode::Esc => {
                        self.input_mode = InputMode::Normal;
                        self.query = self.submitted_query.clone();
                        self.status = "Search cancelled".to_string();
                    }
                    KeyCode::Enter => {
                        self.input_mode = InputMode::Normal;
                        self.scroll = 0;
                        self.search_selected = 0;
                        self.submitted_query = self.query.trim().to_string();
                        self.load_current(false);
                    }
                    KeyCode::Backspace => {
                        self.query.pop();
                    }
                    KeyCode::Char('u') if key.modifiers.contains(KeyModifiers::CONTROL) => {
                        self.query.clear();
                    }
                    KeyCode::Char(character) if !key.modifiers.contains(KeyModifiers::CONTROL) => {
                        self.query.push(character);
                    }
                    _ => {}
                }
                true
            }
            InputMode::SoftwareFilter => {
                match key.code {
                    KeyCode::Esc => {
                        self.software_filter.clear();
                        self.software_selected = 0;
                        self.scroll = 0;
                        self.input_mode = InputMode::Normal;
                        self.status = "Software filter cleared".to_string();
                    }
                    KeyCode::Enter => {
                        self.input_mode = InputMode::Normal;
                        self.status = if self.software_filter.is_empty() {
                            "Software filter cleared".to_string()
                        } else {
                            format!("Filtered by ‘{}’", self.software_filter)
                        };
                    }
                    KeyCode::Backspace => {
                        self.software_filter.pop();
                        self.software_selected = 0;
                        self.scroll = 0;
                    }
                    KeyCode::Char('u') if key.modifiers.contains(KeyModifiers::CONTROL) => {
                        self.software_filter.clear();
                        self.software_selected = 0;
                        self.scroll = 0;
                    }
                    KeyCode::Char(character) if !key.modifiers.contains(KeyModifiers::CONTROL) => {
                        self.software_filter.push(character);
                        self.software_selected = 0;
                        self.scroll = 0;
                    }
                    _ => {}
                }
                true
            }
        }
    }

    pub fn handle_paste(&mut self, value: &str) {
        let normalized = value.split_whitespace().collect::<Vec<_>>().join(" ");
        if normalized.is_empty() {
            return;
        }
        match self.input_mode {
            InputMode::Search => self.query.push_str(&normalized),
            InputMode::SoftwareFilter => {
                self.software_filter.push_str(&normalized);
                self.software_selected = 0;
                self.scroll = 0;
            }
            InputMode::Normal => {}
        }
    }

    pub fn handle_mouse(&mut self, mouse: MouseEvent) {
        let direction = match mouse.kind {
            MouseEventKind::ScrollDown => 1,
            MouseEventKind::ScrollUp => -1,
            _ => return,
        };
        if self.pending_mutation.is_some() || self.mutation_loading || self.overlay_error.is_some()
        {
            return;
        }
        if let Some(chooser) = self.group_chooser.as_mut() {
            if direction > 0 {
                chooser.selected = (chooser.selected + 1).min(chooser.groups.len() - 1);
            } else {
                chooser.selected = chooser.selected.saturating_sub(1);
            }
            return;
        }
        if self.detail.is_some() {
            if direction > 0 {
                self.detail_scroll = self
                    .detail_scroll
                    .saturating_add(3)
                    .min(self.detail_scroll_max);
            } else {
                self.detail_scroll = self.detail_scroll.saturating_sub(3);
            }
            return;
        }
        self.move_selection(direction * 3);
    }

    pub fn handle_key(&mut self, key: KeyEvent) {
        if key.kind != KeyEventKind::Press {
            return;
        }
        if self.overlay_error.is_some() {
            if matches!(key.code, KeyCode::Esc | KeyCode::Enter) {
                self.overlay_error = None;
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
        if let Some(chooser) = self.group_chooser.as_mut() {
            match key.code {
                KeyCode::Down | KeyCode::Char('j') => {
                    chooser.selected = (chooser.selected + 1).min(chooser.groups.len() - 1);
                }
                KeyCode::Up | KeyCode::Char('k') => {
                    chooser.selected = chooser.selected.saturating_sub(1);
                }
                KeyCode::Enter => self.confirm_group(),
                KeyCode::Esc => self.group_chooser = None,
                _ => {}
            }
            return;
        }
        if self.detail.is_some() {
            match key.code {
                KeyCode::Down | KeyCode::Char('j') => {
                    self.detail_scroll = self
                        .detail_scroll
                        .saturating_add(1)
                        .min(self.detail_scroll_max)
                }
                KeyCode::Up | KeyCode::Char('k') => {
                    self.detail_scroll = self.detail_scroll.saturating_sub(1)
                }
                KeyCode::Esc | KeyCode::Enter => {
                    self.detail = None;
                    self.detail_request = None;
                    self.group_request = None;
                    self.detail_scroll = 0;
                    self.detail_scroll_max = 0;
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
        if self.handle_input(key) {
            return;
        }

        match key.code {
            KeyCode::Char('q') => self.should_quit = true,
            KeyCode::Esc if self.screen == Screen::Software && !self.software_filter.is_empty() => {
                self.software_filter.clear();
                self.software_selected = 0;
                self.scroll = 0;
                self.status = "Software filter cleared".to_string();
            }
            KeyCode::Esc if self.screen == Screen::History && self.history_marked.is_some() => {
                self.history_marked = None;
                self.status = "Generation mark cleared".to_string();
            }
            KeyCode::Esc => {
                self.status = "Nothing to dismiss; press q to quit".to_string();
            }
            KeyCode::Char('?') => self.show_help = true,
            KeyCode::Char('r') => self.load_current(true),
            KeyCode::Tab | KeyCode::Right => self.next_screen(1),
            KeyCode::BackTab | KeyCode::Left => self.next_screen(-1),
            KeyCode::Char('/') if self.screen == Screen::Software => {
                self.input_mode = InputMode::SoftwareFilter;
                self.status = "Type to filter locally; Enter keeps it, Esc exits input".to_string();
            }
            KeyCode::Char('/') | KeyCode::Char('s') if self.screen == Screen::Search => {
                self.input_mode = InputMode::Search;
                self.status = "Type a query and press Enter".to_string();
            }
            KeyCode::Char('/') | KeyCode::Char('s') => {
                self.screen = Screen::Search;
                self.scroll = 0;
                self.input_mode = InputMode::Search;
                self.sync_status();
            }
            KeyCode::Char(character) if ('1'..='5').contains(&character) => {
                self.set_screen(Screen::ALL[character as usize - '1' as usize]);
            }
            KeyCode::Enter | KeyCode::Char(' ') if self.screen == Screen::Software => {
                self.begin_selected_mutation();
            }
            KeyCode::Char('w') | KeyCode::Char('i') if self.screen == Screen::Software => {
                self.begin_why();
            }
            KeyCode::Enter | KeyCode::Char('a') if self.screen == Screen::Search => {
                self.begin_search_add();
            }
            KeyCode::Enter | KeyCode::Char('i') if self.screen == Screen::Doctor => {
                self.open_doctor_detail();
            }
            KeyCode::Char(' ') if self.screen == Screen::History => {
                self.history_marked = generation_number(self.payload(), self.history_selected);
                if let Some(number) = self.history_marked {
                    self.status = format!("Generation {number} marked; select another and press d");
                }
            }
            KeyCode::Enter | KeyCode::Char('d') if self.screen == Screen::History => {
                self.begin_history_diff();
            }
            KeyCode::Home | KeyCode::Char('g') => self.move_selection_to(0),
            KeyCode::End | KeyCode::Char('G') => {
                self.move_selection_to(self.row_count().saturating_sub(1));
            }
            KeyCode::PageDown => self.move_selection_page(1),
            KeyCode::PageUp => self.move_selection_page(-1),
            KeyCode::Down | KeyCode::Char('j') => self.move_selection(1),
            KeyCode::Up | KeyCode::Char('k') => self.move_selection(-1),
            _ => {}
        }
    }
}

#[cfg(test)]
mod tests {
    use std::sync::mpsc;

    use serde_json::json;

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
        assert_eq!(app.status, "Software cached");
    }

    #[test]
    fn all_table_selections_stay_inside_the_viewport() {
        let mut app = app();
        app.screen = Screen::Doctor;
        app.visible_rows = 2;
        app.pages.insert(
            Screen::Doctor,
            PageState {
                payload: Some(
                    json!({"results": (0..5).map(|i| json!({"name": i})).collect::<Vec<_>>() }),
                ),
                ..PageState::default()
            },
        );
        app.move_selection(1);
        app.move_selection(1);
        app.move_selection(1);
        assert_eq!(app.doctor_selected, 3);
        assert_eq!(app.scroll, 2);
    }

    #[test]
    fn search_result_only_offers_compatible_manifest_groups() {
        let mut app = app();
        let entry = crate::model::SearchEntry {
            source: "homebrew".into(),
            ecosystem: "homebrew".into(),
            kind: "formula".into(),
            name: "git".into(),
            version: "—".into(),
            description: "—".into(),
            homepage: "—".into(),
            publisher: "—".into(),
            reference: "homebrew:formula/git".into(),
            managed_group: None,
        };
        let payload = json!({"groups": [
            {"id": "homebrew.system.formula", "label": "Formulae", "ecosystem": "homebrew", "scope": "system", "kind": "formula"},
            {"id": "homebrew.system.cask", "label": "Casks", "ecosystem": "homebrew", "scope": "system", "kind": "cask"}
        ]});
        app.open_group_chooser(entry, Some(&payload));
        assert_eq!(app.group_chooser.unwrap().groups.len(), 1);
    }

    #[test]
    fn successful_apply_invalidates_dependent_caches() {
        let mut app = app();
        app.pages.insert(Screen::Software, PageState::default());
        app.pages.insert(Screen::Doctor, PageState::default());
        app.search_cache.insert("git".into(), PageState::default());
        app.invalidate_after_mutation();
        assert!(!app.pages.contains_key(&Screen::Software));
        assert!(!app.pages.contains_key(&Screen::Doctor));
        assert!(app.search_cache.is_empty());
    }

    #[test]
    fn blocked_preview_cannot_reach_apply_stage() {
        let mut app = app();
        app.pending_mutation = Some(MutationPreview {
            intent: MutationIntent {
                action: SoftwareAction::Add,
                group: "nix.user.package".into(),
                operand: "git".into(),
                item: "git".into(),
            },
            payload: json!({"data": {"plan": {"blocked": "shared exclusion"}}}),
        });

        app.apply_pending_mutation();

        assert!(app.pending_mutation.is_none());
        assert!(!app.mutation_loading);
        assert_eq!(
            app.overlay_error.as_deref(),
            Some("Policy blocks this change: shared exclusion")
        );
    }

    #[test]
    fn escape_clears_an_in_progress_software_filter() {
        let mut app = app();
        app.screen = Screen::Software;
        app.input_mode = InputMode::SoftwareFilter;
        app.software_filter = "git".into();

        app.handle_key(KeyEvent::new(KeyCode::Esc, KeyModifiers::NONE));

        assert_eq!(app.input_mode, InputMode::Normal);
        assert!(app.software_filter.is_empty());
        assert!(!app.should_quit);
    }

    #[test]
    fn escape_does_not_accidentally_quit_normal_mode() {
        let mut app = app();

        app.handle_key(KeyEvent::new(KeyCode::Esc, KeyModifiers::NONE));

        assert!(!app.should_quit);
        assert_eq!(app.status, "Nothing to dismiss; press q to quit");
    }

    #[test]
    fn viewport_and_boundary_navigation_keep_selection_visible() {
        let mut app = app();
        app.screen = Screen::Doctor;
        app.visible_rows = 3;
        app.pages.insert(
            Screen::Doctor,
            PageState {
                payload: Some(json!({
                    "results": (0..10).map(|index| json!({"name": index})).collect::<Vec<_>>()
                })),
                ..PageState::default()
            },
        );

        app.handle_key(KeyEvent::new(KeyCode::PageDown, KeyModifiers::NONE));
        assert_eq!(app.doctor_selected, 3);
        assert_eq!(app.scroll, 1);

        app.handle_key(KeyEvent::new(KeyCode::End, KeyModifiers::NONE));
        assert_eq!(app.doctor_selected, 9);
        assert_eq!(app.scroll, 7);

        app.handle_key(KeyEvent::new(KeyCode::Home, KeyModifiers::NONE));
        assert_eq!(app.doctor_selected, 0);
        assert_eq!(app.scroll, 0);
    }

    #[test]
    fn bracketed_paste_is_normalized_into_the_active_input() {
        let mut app = app();
        app.input_mode = InputMode::Search;

        app.handle_paste("  visual\n studio\tcode  ");

        assert_eq!(app.query, "visual studio code");
    }
}
