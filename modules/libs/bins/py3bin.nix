{ pkgs, ... }:

let
  niri-scratchpad = pkgs.writers.writePython3Bin "niri-scratchpad" 
    { 
      libraries = [ ]; 
      makeWrapperArgs = [
        "--prefix PATH : ${pkgs.lib.makeBinPath [ pkgs.niri ]}"
      ];
    } 
    ''
# !/usr/bin/env python3
import argparse
import json
import os
import subprocess
import sys
import shlex

# the found scratchpad window (id, workspace_id, is_focused, is_floating)
scratch_window = {}
# the focused workspace data
focused_workspace = {}
# the scratchpad workspace name
scratch_workspace = os.getenv("NS_WORKSPACE", "scratch")


def niri_cmd(cmd_args):
    subprocess.run(["niri", "msg", "action"] + cmd_args)


def move_window_to_scratchpad(window_id, animations):
    niri_cmd([
        "move-window-to-workspace",
        "--window-id", str(window_id),
        scratch_workspace,
        "--focus=false"
    ])
    if animations:
        niri_cmd(["move-window-to-tiling", "--id", str(window_id)])


def bring_scratchpad_window_to_focus(window_id, args):
    niri_cmd([
        "move-window-to-workspace",
        "--window-id", str(window_id),
        str(focused_workspace["idx"])
    ])
    if args.multi_monitor:
        niri_cmd([
            "move-window-to-monitor",
            "--id", str(window_id),
            focused_workspace["output"]
        ])
    if args.animations and not scratch_window["is_floating"]:
        niri_cmd(["move-window-to-floating", "--id", str(window_id)])
    niri_cmd(["focus-window", "--id", str(window_id)])


def find_scratch_window(args, windows):
    for window in windows:
        app_match = args.app_id and window["app_id"] == args.app_id
        title_match = args.title and window["title"] == args.title
        if app_match or title_match:
            scratch_window["id"] = window["id"]
            scratch_window["workspace_id"] = window["workspace_id"]
            scratch_window["is_focused"] = window["is_focused"]
            scratch_window["is_floating"] = window["is_floating"]
            break


def fetch_focused_workspace():
    props = subprocess.run(
        ["niri", "msg", "--json", "workspaces"],
        capture_output=True,
        text=True,
    )
    workspaces = json.loads(props.stdout)

    for workspace in workspaces:
        if workspace["is_focused"]:
            focused_workspace["idx"] = workspace["idx"]
            focused_workspace["output"] = workspace["output"]
            return workspace["id"]


def ns(parser):
    args = parser.parse_args()

    props = subprocess.run(
        ["niri", "msg", "--json", "windows"],
        capture_output=True,
        text=True,
    )
    windows = json.loads(props.stdout)

    find_scratch_window(args, windows)

    if not scratch_window:
        if args.spawn:
            niri_cmd(["spawn", "--"] + shlex.split(args.spawn))
            sys.exit(0)
        else:
            parser.print_help()
            sys.exit(1)

    window_id = scratch_window["id"]

    if not scratch_window["is_focused"]:
        workspace_id = fetch_focused_workspace()
        if scratch_window["workspace_id"] != workspace_id:
            bring_scratchpad_window_to_focus(window_id, args)
            return

    move_window_to_scratchpad(window_id, args.animations)


def main():
    desc = 'Niri Scratchpad support'
    parser = argparse.ArgumentParser(prog='nscratch', description=desc)
    group = parser.add_mutually_exclusive_group(required=True)

    group.add_argument('-id', '--app-id', help='Application identifier')
    group.add_argument('-t', '--title', help='Application title')
    parser.add_argument('-s', '--spawn', help='Process name to spawn')
    parser.add_argument('-a', '--animations', action='store_true')
    parser.add_argument('-m', '--multi-monitor', action='store_true')

    ns(parser)


if __name__ == "__main__":
    main()
    '';
in
{
  home.packages = [ niri-scratchpad ];
}