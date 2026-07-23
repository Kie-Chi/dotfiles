{ pkgs, config, lib, sys, ... }:

let
  rimeIceRepo = pkgs.fetchFromGitHub {
    owner = "iDvel";
    repo = "rime-ice";
    rev = "6319944ea9ea3dc17aa62d3aef5e019e7890d6b5";
    sha256 = "sha256-/9clctDtFlngn0zcGb/OL055/i+PGzVK7qjJv3xh4+g=";
  };
in
{
  config = lib.mkIf (!(builtins.elem "squirrel-app" config.envy.homebrew.casks.exclude)) {

  home.activation.installRimeIce = sys.task.activation {
    name = "installRimeIce";
    script = ''
      RIME_DIR="$HOME/Library/Rime"
      mkdir -p "$RIME_DIR"
      ${pkgs.rsync}/bin/rsync -av --chmod=u+w "${rimeIceRepo}/" "$RIME_DIR/"

      if ${sys.cmds.pgrep} -x "Squirrel" > /dev/null; then
        echo "Reloading Squirrel..."
        rm -rf "$RIME_DIR/build"
        /Library/Input\ Methods/Squirrel.app/Contents/MacOS/Squirrel --reload
      fi
    '';
  };

  home.file."squirrel-custom" = {
    target = "Library/Rime/squirrel.custom.yaml";
    text = ''
      patch:
        style/color_scheme: rose_pine
        style/horizontal: true
        style/inline_preedit: true
        style/corner_radius: 5
    '';
  };
  
  home.file."default-custom" = {
    target = "Library/Rime/default.custom.yaml";
    text = ''
      patch:
        schema_list:
          - schema: rime_ice
        ascii_composer/good_old_caps_lock: true
        ascii_composer/switch_key:
          Caps_Lock: commit_code
          Shift_L: noop
          Shift_R: noop
          Control_L: noop
          Control_R: noop
        
        ascii_composer/engine/processors:
          - 'ascii_segmentor'
          - 'key_binder'
          - 'speller'
          - 'selector'
          - 'navigator'
          - 'express_editor'
          # - 'ascii_composer'  # 将此行注释掉或删除
        app_options/: {}

        key_binder/bindings:
          # 翻页
          - { when: has_menu, accept: Tab, send: Page_Down }            # "tab" 键翻页, 和下一条 "tab" 键分词只能二选一
          - { when: composing, accept: Shift+Tab, send: Shift+Left }    # "Shift+Tab" 键向左选拼音分词
          - { when: paging, accept: minus, send: Page_Up }              # "-" 上一页
          - { when: has_menu, accept: equal, send: Page_Down }          # "=" 下一页
          - { when: paging, accept: comma, send: Page_Up }              # "," 上一页
          - { when: has_menu, accept: period, send: Page_Down }         # "." 下一页
          - { when: paging, accept: bracketleft, send: Page_Up }        # "[" 上一页
          - { when: has_menu, accept: bracketright, send: Page_Down }   # "]" 下一页

          # 快捷键
          - { when: has_menu, accept: semicolon, send: 2 }              # ":" (分号)选择第 2 个候选词
          - { when: has_menu, accept: apostrophe, send: 3 }             # "'" (引号)选择第 3 个候选词
          - { when: composing, accept: Shift+Tab, send: Shift+Left }    # "Shift+Tab" 键向左选拼音分词
          - { when: composing, accept: Control+a, send: Home }          # "Control+a" 光标移至首
          - { when: composing, accept: Control+e, send: End }           # "Control+e" 光标移至尾
          - { when: always, accept: Control+Shift+1, select: .next }             # 切换输入方案
          - { when: always, accept: Control+space, toggle: ascii_mode }        # 中/英文切换
          - { when: always, accept: Control+Shift+2, toggle: ascii_mode }        # 中/英文切换
          - { when: always, accept: Control+Shift+3, toggle: full_shape }        # 全角/半角切换
          - { when: always, accept: Control+Shift+4, toggle: simplification }    # 繁简体切换
          - { when: always, accept: Control+Shift+5, toggle: extended_charset }  # 通用/增广切换（显示生僻字）
          - { when: composing, accept: Control+b, send: Left }           # "Control+b" 移动光标
          - { when: composing, accept: Control+f, send: Right }          # "Control+f" 向右选择候选词
          - { when: composing, accept: Control+h, send: BackSpace }      # "Control+h" 删除输入码
    '';
  };
  };
}
