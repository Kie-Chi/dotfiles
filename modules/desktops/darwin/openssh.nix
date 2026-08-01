{ config, ... }:

let
  mode = config.envy.darwin.services.openssh.mode;
in
{
  # null leaves Remote Login under manual control in macOS System Settings.
  services.openssh.enable =
    if mode == "manual" then null
    else mode == "keep";
}
