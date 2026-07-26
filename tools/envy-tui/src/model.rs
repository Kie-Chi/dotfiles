use std::collections::HashMap;

use serde_json::Value;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Screen {
    Dashboard,
    Software,
    Search,
    Doctor,
    History,
}

impl Screen {
    pub const ALL: [Self; 5] = [
        Self::Dashboard,
        Self::Software,
        Self::Search,
        Self::Doctor,
        Self::History,
    ];

    pub fn title(self) -> &'static str {
        match self {
            Self::Dashboard => "Dashboard",
            Self::Software => "Software",
            Self::Search => "Search",
            Self::Doctor => "Doctor",
            Self::History => "History",
        }
    }

    pub fn index(self) -> usize {
        Self::ALL.iter().position(|item| *item == self).unwrap_or(0)
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
}
