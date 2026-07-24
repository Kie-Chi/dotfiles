{ ... }:

{
  envy.linux.software.native.packages.include = [
    {
      id = "cifs-utils";
      name = "cifs-utils";
      ref = "native:cifs-utils";
    }
    {
      id = "openssh-server";
      name = "openssh-server";
      ref = "native:openssh-server";
      parameters.names.pacman = "openssh";
    }
    {
      id = "linux-kernel-headers";
      name = "Current kernel headers";
      parameters.resolver = "current-kernel-headers";
    }
  ];
}
