use std::collections::HashMap;

use serde_json::Value;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Screen {
    Dashboard,
    Software,
    Search,
    Doctor,
    History,
    Journal,
    Hosts,
    Mirror,
    Config,
}

impl Screen {
    /// Top-level tabs, in bar order. Journal, Hosts, and Config are intentionally
    /// absent: Journal is a sub-view of History, and Hosts/Config are edited inline
    /// on the Dashboard. They remain enum variants so their backend commands,
    /// cached `PageState`, and selection indices keep working off-tab.
    pub const ALL: [Self; 6] = [
        Self::Dashboard,
        Self::Software,
        Self::Search,
        Self::Doctor,
        Self::History,
        Self::Mirror,
    ];

    pub fn title(self) -> &'static str {
        match self {
            Self::Dashboard => "Dashboard",
            Self::Software => "Software",
            Self::Search => "Search",
            Self::Doctor => "Doctor",
            Self::History => "History",
            Self::Journal => "Journal",
            Self::Hosts => "Hosts",
            Self::Mirror => "Mirror",
            Self::Config => "Config",
        }
    }

    pub fn index(self) -> usize {
        Self::ALL.iter().position(|item| *item == self).unwrap_or(0)
    }
}

/// The two time-ordered views merged under the History tab.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Default)]
pub enum HistoryView {
    #[default]
    Generations,
    Operations,
}

impl HistoryView {
    pub fn toggled(self) -> Self {
        match self {
            Self::Generations => Self::Operations,
            Self::Operations => Self::Generations,
        }
    }

    /// The backing screen whose command and cached payload feed this view.
    pub fn screen(self) -> Screen {
        match self {
            Self::Generations => Screen::History,
            Self::Operations => Screen::Journal,
        }
    }

    pub fn label(self) -> &'static str {
        match self {
            Self::Generations => "Generations",
            Self::Operations => "Operations",
        }
    }
}

#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub enum LoadTarget {
    Screen(Screen),
    Search(String),
}

impl LoadTarget {
    pub fn title(&self) -> &'static str {
        match self {
            Self::Screen(screen) => screen.title(),
            Self::Search(_) => "Search",
        }
    }
}

#[derive(Debug, Default)]
pub struct PageState {
    pub payload: Option<Value>,
    pub loading: bool,
    pub error: Option<String>,
    pub request: Option<u64>,
}

impl PageState {
    pub fn has_content(&self) -> bool {
        self.payload.is_some()
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum MutationStage {
    Preview,
    Apply,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum SoftwareAction {
    Add,
    Remove,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum WorkflowAction {
    Plan,
    Apply,
    Doctor,
    OpenApp(String),
    OpenSettings(String),
}

impl WorkflowAction {
    pub fn title(&self) -> String {
        match self {
            Self::Plan => "Preview configuration".to_string(),
            Self::Apply => "Apply configuration".to_string(),
            Self::Doctor => "Verify with doctor".to_string(),
            Self::OpenApp(name) => format!("Open {name}"),
            Self::OpenSettings(_) => "Open System Settings".to_string(),
        }
    }

    pub fn command(&self, envy: String) -> (String, Vec<String>) {
        match self {
            Self::Plan => (envy, vec!["plan".to_string()]),
            Self::Apply => (envy, vec!["apply".to_string()]),
            Self::Doctor => (envy, vec!["doctor".to_string()]),
            Self::OpenApp(name) => ("open".to_string(), vec!["-a".to_string(), name.clone()]),
            Self::OpenSettings(target) => (
                "open".to_string(),
                vec![match target.as_str() {
                    "privacy-full-disk-access" => {
                        "x-apple.systempreferences:com.apple.preference.security?Privacy_AllFiles"
                            .to_string()
                    }
                    _ => "x-apple.systempreferences:com.apple.preference.security".to_string(),
                }],
            ),
        }
    }

    pub fn display_command(&self) -> String {
        match self {
            Self::Plan => "envy plan".to_string(),
            Self::Apply => "envy apply".to_string(),
            Self::Doctor => "envy doctor".to_string(),
            Self::OpenApp(name) => format!("open -a {name:?}"),
            Self::OpenSettings(_) => "open macOS Privacy & Security settings".to_string(),
        }
    }
}

impl SoftwareAction {
    pub fn command(self) -> &'static str {
        match self {
            Self::Add => "add",
            Self::Remove => "rm",
        }
    }

    pub fn label(self) -> &'static str {
        match self {
            Self::Add => "enable",
            Self::Remove => "disable",
        }
    }
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct MutationIntent {
    pub action: SoftwareAction,
    pub group: String,
    /// Operand passed to Envy. Search uses a canonical registry reference.
    pub operand: String,
    /// Stable item ID that the verified plan must resolve to.
    pub item: String,
}

#[derive(Clone, Debug)]
pub struct MutationPreview {
    pub intent: MutationIntent,
    pub payload: Value,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct SoftwareEntry {
    pub group: String,
    pub label: String,
    pub item: String,
    pub version: String,
    pub state: String,
    pub reference: String,
    pub effective: bool,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct SoftwareGroup {
    pub id: String,
    pub label: String,
    pub ecosystem: String,
    pub scope: String,
    pub kind: String,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct SearchEntry {
    pub source: String,
    pub ecosystem: String,
    pub kind: String,
    pub name: String,
    pub version: String,
    pub description: String,
    pub homepage: String,
    pub publisher: String,
    pub reference: String,
    pub managed_group: Option<String>,
}

#[derive(Clone, Debug)]
pub struct GroupChooser {
    pub entry: SearchEntry,
    pub groups: Vec<SoftwareGroup>,
    pub selected: usize,
}

/// A Dashboard-editable setting: either the active host or one managed config field.
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum SettingKey {
    Host,
    Config(String),
}

impl SettingKey {
    pub fn label(&self) -> String {
        match self {
            Self::Host => "host".to_string(),
            Self::Config(path) => path.clone(),
        }
    }
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct SettingRow {
    pub key: SettingKey,
    pub label: String,
    pub value: String,
    /// Non-empty = enumerated (dropdown); empty = freeform (text input).
    pub choices: Vec<String>,
}

impl SettingRow {
    pub fn freeform(&self) -> bool {
        self.choices.is_empty()
    }
}

/// A dropdown over an enumerated setting or the known host list.
#[derive(Clone, Debug)]
pub struct SettingChooser {
    pub key: SettingKey,
    pub title: String,
    pub options: Vec<String>,
    pub selected: usize,
    pub current: String,
}

/// A freeform text edit in progress for one setting.
#[derive(Clone, Debug)]
pub struct SettingEdit {
    pub key: SettingKey,
    pub title: String,
    pub buffer: String,
    pub previous: String,
}

/// A chosen value awaiting explicit confirmation before it is written.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct PendingSetting {
    pub key: SettingKey,
    pub value: String,
    pub previous: String,
}

#[derive(Clone, Debug)]
pub enum DetailView {
    Loading { title: String },
    Software(Value),
    Doctor(Value),
    HistoryDiff(Value),
}

#[derive(Debug)]
pub enum Message {
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
    SoftwareWhyFinished {
        request: u64,
        result: Result<Value, String>,
    },
    SearchGroupsFinished {
        request: u64,
        entry: SearchEntry,
        software: Result<Value, String>,
    },
    HistoryDiffFinished {
        request: u64,
        result: Result<Value, String>,
    },
    SettingApplied {
        request: u64,
        key: SettingKey,
        result: Result<Value, String>,
    },
}

pub fn text(value: Option<&Value>) -> String {
    match value {
        Some(Value::String(value)) => value.clone(),
        Some(Value::Bool(value)) => value.to_string(),
        Some(Value::Number(value)) => value.to_string(),
        Some(Value::Null) | None => "—".to_string(),
        Some(value) => value.to_string(),
    }
}

pub fn software_groups(payload: Option<&Value>) -> Vec<SoftwareGroup> {
    payload
        .and_then(|value| value.get("groups"))
        .and_then(Value::as_array)
        .map(|groups| {
            groups
                .iter()
                .map(|group| SoftwareGroup {
                    id: text(group.get("id")),
                    label: text(group.get("label")),
                    ecosystem: text(group.get("ecosystem")),
                    scope: text(group.get("scope")),
                    kind: text(group.get("kind")),
                })
                .collect()
        })
        .unwrap_or_default()
}

pub fn software_entries(payload: Option<&Value>) -> Vec<SoftwareEntry> {
    let mut entries = Vec::new();
    let Some(groups) = payload
        .and_then(|value| value.get("groups"))
        .and_then(Value::as_array)
    else {
        return entries;
    };
    for group in groups {
        let group_id = text(group.get("id"));
        let group_label = text(group.get("label"));
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
                label: group_label.clone(),
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

pub fn filtered_software_entries(payload: Option<&Value>, filter: &str) -> Vec<SoftwareEntry> {
    let needle = filter.trim().to_lowercase();
    software_entries(payload)
        .into_iter()
        .filter(|entry| {
            needle.is_empty()
                || [
                    &entry.group,
                    &entry.label,
                    &entry.item,
                    &entry.version,
                    &entry.state,
                    &entry.reference,
                ]
                .iter()
                .any(|value| value.to_lowercase().contains(&needle))
        })
        .collect()
}

pub fn search_entries(payload: Option<&Value>) -> Vec<SearchEntry> {
    payload
        .and_then(|value| value.get("results"))
        .and_then(Value::as_array)
        .map(|results| {
            results
                .iter()
                .map(|result| SearchEntry {
                    source: text(result.get("source")),
                    ecosystem: text(result.get("ecosystem")),
                    kind: text(result.get("kind")),
                    name: text(result.get("name")),
                    version: text(result.get("version")),
                    description: text(result.get("description")),
                    homepage: text(result.get("homepage")),
                    publisher: text(result.get("publisher")),
                    reference: text(result.get("ref")),
                    managed_group: result
                        .get("managed_group")
                        .or_else(|| result.get("managedGroup"))
                        .and_then(Value::as_str)
                        .map(str::to_string),
                })
                .collect()
        })
        .unwrap_or_default()
}

pub fn compatible_groups(entry: &SearchEntry, payload: Option<&Value>) -> Vec<SoftwareGroup> {
    let groups = software_groups(payload);
    if let Some(managed) = &entry.managed_group {
        if let Some(group) = groups.iter().find(|group| &group.id == managed) {
            return vec![group.clone()];
        }
    }
    groups
        .into_iter()
        .filter(|group| group.ecosystem == entry.ecosystem && group.kind == entry.kind)
        .collect()
}

pub fn result_rows(payload: Option<&Value>) -> usize {
    payload
        .and_then(|value| value.get("results"))
        .and_then(Value::as_array)
        .map(Vec::len)
        .unwrap_or(0)
}

pub fn generation_rows(payload: Option<&Value>) -> usize {
    payload
        .and_then(|value| value.get("generations"))
        .and_then(Value::as_array)
        .map(Vec::len)
        .unwrap_or(0)
}

pub fn generation_number(payload: Option<&Value>, index: usize) -> Option<u64> {
    payload
        .and_then(|value| value.get("generations"))
        .and_then(Value::as_array)
        .and_then(|generations| generations.get(index))
        .and_then(|generation| generation.get("number"))
        .and_then(Value::as_u64)
}

pub type Pages = HashMap<Screen, PageState>;

// ==========================================
// READ-ONLY SCREEN VIEW MODELS
// ==========================================

fn format_detail(value: Option<&Value>) -> String {
    match value {
        Some(Value::Object(map)) if !map.is_empty() => map
            .iter()
            .map(|(key, val)| format!("{key}={}", text(Some(val))))
            .collect::<Vec<_>>()
            .join("  "),
        _ => "—".to_string(),
    }
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct JournalEntry {
    pub timestamp: String,
    pub operation: String,
    pub result: String,
    pub duration: String,
    pub machine: String,
    pub detail: String,
}

fn duration_text(duration_ms: Option<&Value>) -> String {
    match duration_ms.and_then(Value::as_u64) {
        Some(ms) => format!("{:.1}s", ms as f64 / 1000.0),
        None => "—".to_string(),
    }
}

pub fn journal_entries(payload: Option<&Value>) -> Vec<JournalEntry> {
    payload
        .and_then(|value| value.get("entries"))
        .and_then(Value::as_array)
        .map(|entries| {
            entries
                .iter()
                .map(|entry| JournalEntry {
                    timestamp: text(entry.get("timestamp")),
                    operation: text(entry.get("operation")),
                    result: text(entry.get("result")),
                    duration: duration_text(entry.get("durationMs")),
                    machine: text(entry.get("machine")),
                    detail: format_detail(entry.get("detail")),
                })
                .collect()
        })
        .unwrap_or_default()
}

pub fn journal_rows(payload: Option<&Value>) -> usize {
    payload
        .and_then(|value| value.get("entries"))
        .and_then(Value::as_array)
        .map(Vec::len)
        .unwrap_or(0)
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct HostRow {
    pub platform: String,
    pub machine: String,
    pub current: bool,
    pub file: String,
}

pub fn host_rows(payload: Option<&Value>) -> Vec<HostRow> {
    payload
        .and_then(|value| value.get("machines"))
        .and_then(Value::as_array)
        .map(|machines| {
            machines
                .iter()
                .map(|machine| HostRow {
                    platform: text(machine.get("platform")),
                    machine: text(machine.get("machineId")),
                    current: machine.get("current").and_then(Value::as_bool) == Some(true),
                    file: text(machine.get("file")),
                })
                .collect()
        })
        .unwrap_or_default()
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct KeyValueRow {
    pub key: String,
    pub value: String,
}

pub fn mirror_rows(payload: Option<&Value>) -> Vec<KeyValueRow> {
    payload
        .and_then(|value| value.get("settings"))
        .and_then(Value::as_object)
        .map(|settings| {
            settings
                .iter()
                .map(|(key, value)| KeyValueRow {
                    key: key.clone(),
                    value: text(Some(value)),
                })
                .collect()
        })
        .unwrap_or_default()
}

/// Build the Dashboard's editable settings list from the cached host list and
/// config payloads. Row 0 is the active host; the rest are managed config fields
/// (`fields[]` from `config show --json`), where a non-empty `choices` marks an
/// enumerated field that should render as a dropdown.
pub fn dashboard_settings(hosts: Option<&Value>, config: Option<&Value>) -> Vec<SettingRow> {
    let mut rows = Vec::new();
    let current_host = config
        .and_then(|value| value.get("device"))
        .and_then(|device| device.get("machineId"))
        .and_then(Value::as_str)
        .unwrap_or("")
        .to_string();
    let machine_ids = host_rows(hosts)
        .into_iter()
        .map(|host| host.machine)
        .filter(|machine| machine != "—" && !machine.is_empty())
        .collect::<Vec<_>>();
    rows.push(SettingRow {
        key: SettingKey::Host,
        label: "host".to_string(),
        value: current_host,
        choices: machine_ids,
    });
    if let Some(fields) = config
        .and_then(|value| value.get("fields"))
        .and_then(Value::as_array)
    {
        for field in fields {
            let path = field
                .get("path")
                .and_then(Value::as_str)
                .unwrap_or("")
                .to_string();
            if path.is_empty() {
                continue;
            }
            let value = field
                .get("value")
                .and_then(Value::as_str)
                .unwrap_or("")
                .to_string();
            let choices = field
                .get("choices")
                .and_then(Value::as_array)
                .map(|items| {
                    items
                        .iter()
                        .filter_map(Value::as_str)
                        .map(str::to_string)
                        .collect::<Vec<_>>()
                })
                .unwrap_or_default();
            rows.push(SettingRow {
                key: SettingKey::Config(path.clone()),
                label: path,
                value,
                choices,
            });
        }
    }
    rows
}

pub fn count_rows(payload: Option<&Value>, key: &str) -> usize {
    payload
        .and_then(|value| value.get(key))
        .and_then(Value::as_array)
        .map(Vec::len)
        .unwrap_or(0)
}

#[cfg(test)]
mod tests {
    use serde_json::json;

    use super::*;

    #[test]
    fn local_filter_matches_identity_reference_and_state() {
        let payload = json!({"groups": [{
            "id": "nix.user.package",
            "label": "Nix packages",
            "items": [{"id": "ripgrep", "ref": "nix:rg", "effective": true}]
        }]});
        assert_eq!(filtered_software_entries(Some(&payload), "RIP").len(), 1);
        assert_eq!(filtered_software_entries(Some(&payload), "nix:rg").len(), 1);
        assert_eq!(
            filtered_software_entries(Some(&payload), "blocked").len(),
            0
        );
    }

    #[test]
    fn snake_case_managed_group_is_supported() {
        let payload = json!({"results": [{
            "source": "homebrew", "ecosystem": "homebrew", "kind": "formula",
            "name": "git", "ref": "homebrew:formula/git",
            "managed_group": "homebrew.system.formula"
        }]});
        assert_eq!(
            search_entries(Some(&payload))[0].managed_group.as_deref(),
            Some("homebrew.system.formula")
        );
    }

    #[test]
    fn journal_entries_parse_and_format() {
        let payload = json!({"entries": [{
            "timestamp": "2026-07-27T14:52:03+08:00",
            "operation": "push",
            "result": "fail",
            "durationMs": 18420,
            "machine": "mac",
            "detail": {"remote": "origin", "branch": "master"}
        }]});
        let entries = journal_entries(Some(&payload));
        assert_eq!(entries.len(), 1);
        assert_eq!(entries[0].operation, "push");
        assert_eq!(entries[0].duration, "18.4s");
        assert!(entries[0].detail.contains("remote=origin"));
        assert_eq!(journal_rows(Some(&payload)), 1);
    }

    #[test]
    fn host_rows_mark_current_machine() {
        let payload = json!({"machines": [
            {"platform": "darwin", "machineId": "mac", "current": true, "file": "hosts/darwin/mac.nix"},
            {"platform": "linux", "machineId": "box", "current": false, "file": "hosts/linux/box.nix"}
        ]});
        let rows = host_rows(Some(&payload));
        assert_eq!(rows.len(), 2);
        assert!(rows[0].current);
        assert!(!rows[1].current);
    }

    #[test]
    fn mirror_rows_flatten_settings() {
        let payload = json!({"settings": {"mode": "china", "npm.registry": "https://x"}});
        let rows = mirror_rows(Some(&payload));
        assert_eq!(rows.len(), 2);
        assert!(rows
            .iter()
            .any(|row| row.key == "mode" && row.value == "china"));
    }

    #[test]
    fn dashboard_settings_expose_host_and_config_editability() {
        let hosts = json!({"machines": [
            {"platform": "darwin", "machineId": "mac", "current": true, "file": "hosts/darwin/mac.nix"},
            {"platform": "linux", "machineId": "box", "current": false, "file": "hosts/linux/box.nix"}
        ]});
        let config = json!({
            "device": {"machineId": "mac"},
            "fields": [
                {"path": "envy.mirrors.mode", "value": "china", "choices": ["upstream", "china"]},
                {"path": "envy.user.name", "value": "chi", "choices": []}
            ]
        });
        let rows = dashboard_settings(Some(&hosts), Some(&config));
        assert_eq!(rows[0].key, SettingKey::Host);
        assert_eq!(rows[0].value, "mac");
        assert_eq!(rows[0].choices, vec!["mac".to_string(), "box".to_string()]);
        let mirror = rows
            .iter()
            .find(|row| row.key == SettingKey::Config("envy.mirrors.mode".to_string()))
            .unwrap();
        assert!(!mirror.freeform());
        assert_eq!(mirror.value, "china");
        let name = rows
            .iter()
            .find(|row| row.key == SettingKey::Config("envy.user.name".to_string()))
            .unwrap();
        assert!(name.freeform());
    }
}
