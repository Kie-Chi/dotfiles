"""Selection parsing and result filtering for doctor checks."""

from collections.abc import Iterable
from dataclasses import dataclass, field

from envy.doctor.model import (
    ALL_SECTIONS,
    SECTION_ALIASES,
    SECTION_DOCTOR,
    SECTION_PRIVACY,
    SECTION_SYSTEM,
    CheckResult,
    DoctorSection,
    error,
)
from envy.schemas.apps import ALL_APP_SPECS, APP_ALIASES

ONLY_HELP = (
    "Only selected sections and/or apps. Repeat or comma-separate values; "
    "use section:<name> or app:<name> to disambiguate."
)


@dataclass
class DoctorSelection:
    sections: set[DoctorSection] = field(default_factory=set)
    apps: list[str] = field(default_factory=list)
    unknown: list[str] = field(default_factory=list)
    ambiguous: list[str] = field(default_factory=list)

    @property
    def app_set(self) -> set[str]:
        return set(self.apps)

    @property
    def has_parse_errors(self) -> bool:
        return bool(self.unknown or self.ambiguous)


def parse_only(selected: Iterable[str] | None) -> DoctorSelection:
    selection = DoctorSelection()
    seen_apps: set[str] = set()

    for raw_token in _expand_selection(selected):
        prefix, value = _split_prefixed(raw_token)
        if prefix == "section":
            section = normalize_section(value)
            if section:
                selection.sections.add(section)
            else:
                selection.unknown.append(raw_token)
            continue
        if prefix == "app":
            app_key = normalize_app_key(value)
            if app_key:
                _append_app(selection, app_key, seen_apps)
            else:
                selection.unknown.append(raw_token)
            continue
        if prefix:
            selection.unknown.append(raw_token)
            continue

        section = normalize_section(raw_token)
        app_key = normalize_app_key(raw_token)
        if section and app_key:
            selection.ambiguous.append(raw_token)
        elif section:
            selection.sections.add(section)
        elif app_key:
            _append_app(selection, app_key, seen_apps)
        else:
            selection.unknown.append(raw_token)

    return selection


def normalize_section(value: str) -> DoctorSection | None:
    return SECTION_ALIASES.get(_normalize_token(value))


def normalize_app_key(value: str) -> str | None:
    key = _normalize_token(value)
    key = APP_ALIASES.get(key, key)
    if key in ALL_APP_SPECS:
        return key
    return None


def selection_errors(selection: DoctorSelection, *, allow_apps: bool) -> list[CheckResult]:
    errors: list[CheckResult] = []

    if selection.unknown:
        errors.append(error(
            SECTION_DOCTOR,
            "selection",
            "unknown selection token(s): " + ", ".join(selection.unknown),
            hint=_selection_hint(),
        ))
    if selection.ambiguous:
        errors.append(error(
            SECTION_DOCTOR,
            "selection",
            "ambiguous selection token(s): " + ", ".join(selection.ambiguous),
            hint="Use section:<name> or app:<name>. " + _selection_hint(),
        ))
    if selection.apps and not allow_apps:
        errors.append(error(
            SECTION_DOCTOR,
            "selection",
            "app filter(s) are not valid for this command: " + ", ".join(selection.apps),
            hint="Use section filters here. Available sections: " + ", ".join(ALL_SECTIONS),
        ))

    return errors


def filter_results(results: list[CheckResult], selection: DoctorSelection) -> list[CheckResult]:
    filtered: list[CheckResult] = []
    selected_apps = selection.app_set

    for result in results:
        if selection.sections and not _section_matches(result.section, selection.sections):
            continue
        if selected_apps and result.details.get("app") not in selected_apps:
            continue
        filtered.append(result)

    return filtered


def app_keys_for_selection(selection: DoctorSelection) -> list[str]:
    if selection.apps:
        return selection.apps
    return list(ALL_APP_SPECS)


def _section_matches(section: DoctorSection, selected: set[DoctorSection]) -> bool:
    if section in selected:
        return True
    return section == SECTION_SYSTEM and SECTION_PRIVACY in selected


def _append_app(selection: DoctorSelection, app_key: str, seen_apps: set[str]) -> None:
    if app_key in seen_apps:
        return
    selection.apps.append(app_key)
    seen_apps.add(app_key)


def _expand_selection(selected: Iterable[str] | None) -> list[str]:
    if not selected:
        return []

    values: list[str] = []
    for item in selected:
        values.extend(part.strip() for part in item.split(",") if part.strip())
    return values


def _split_prefixed(value: str) -> tuple[str, str]:
    if ":" not in value:
        return ("", value)
    prefix, rest = value.split(":", 1)
    return (_normalize_token(prefix), rest.strip())


def _normalize_token(value: str) -> str:
    return value.strip().lower().replace("_", "-")


def _selection_hint() -> str:
    return (
        "Available sections: "
        + ", ".join(ALL_SECTIONS)
        + ". Available app checks: "
        + ", ".join(sorted(ALL_APP_SPECS))
    )
