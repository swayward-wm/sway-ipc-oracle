# Adding a compositor

The runners measure a compositor from the outside: they start it headless on a
private IPC socket, open real client windows, and talk to it over i3/sway IPC.
Adding a compositor means adding an adapter, not changing a test.

1. Add an adapter beside the existing ones (`i3/adapters/<name>/` for the i3
   suite, a class in `contrib/sway-ipc-run` for the sway IPC scenarios). It may
   start the compositor, translate a test's config into the compositor's own
   config language, and publish the IPC socket path. It must not change an
   assertion or a value observed over IPC.
2. List every translation rule in the adapter's README (`i3/adapters/<name>/README.md`,
   or `sway-ipc/adapters/<name>.md` for a sway IPC adapter), and flag affected rows
   as `adapted`. The same premise gets the same translation on every compositor
   that can express it.
3. Pin the compositor's source revision in `pins.toml`, and add its versioned
   snapshot name under `[snapshot]`.
4. Generate its snapshots with the runners and classify every non-pass in
   `i3/classifications/<snapshot>.toml`, citing source.
5. Before publishing a snapshot of someone else's project, send its maintainers
   a courtesy note.

Read [`CONTRIBUTING.md`](../CONTRIBUTING.md) for the rules that keep snapshots
fair across compositors.

To run the oracle in your own CI once the adapter exists, read
[Run the oracle in your compositor's CI](ci.md).

## Compositors not measured yet

[Wayfire](https://github.com/WayfireWM/wayfire) has an experimental i3/sway
IPC plugin,
[AR-CADE/wayfire-ipc](https://github.com/AR-CADE/wayfire-ipc). It has no
adapter yet.

[hy3](https://github.com/outfoxxed/hy3) gives Hyprland an i3/sway-like manual
tiling layout, but the oracle cannot run against it. The runners speak i3/sway
IPC: they connect to `$SWAYSOCK` or `$I3SOCK`, send `RUN_COMMAND` with sway
command syntax and read `GET_TREE` in the i3 tree schema. hy3 is a Hyprland
plugin. It is driven by Hyprland dispatchers, from keybindings, from Lua
(`hl.plugin.hy3` dispatchers passed to `hl.bind`) or over Hyprland's own IPC
(`hyprctl dispatch hy3:…`), and opens no i3/sway IPC socket. The same
holds for [hy3-lua](https://github.com/aarobc/hy3-lua), a separate Lua layout
registered as `lua:hy3` (Hyprland 0.50 or later). Supporting either would need
a layer that translates sway commands and the i3 tree onto Hyprland dispatchers
and JSON. That layer would then be the thing under test, not the layout.

i3-gaps was merged into i3 in 4.22, so the i3 snapshot covers it.
