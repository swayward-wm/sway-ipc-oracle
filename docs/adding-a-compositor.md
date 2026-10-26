# Add a compositor

Add an adapter, not a test. The runners start a headless compositor on a
private IPC socket, open real client windows, and observe i3/sway IPC.
If an adapter already exists, [run a first check](start.md#measure-your-compositor) or [set up CI](ci.md).

## Add the adapter and pin

1. Add an adapter in `i3/adapters/<name>/` for the i3 suite, or a class in
   `contrib/sway-ipc-run` for the sway IPC corpora. It starts the compositor,
   translates configuration where needed, and publishes the socket path.
2. Document each translation in `i3/adapters/<name>/README.md` or
   `sway-ipc/adapters/<name>.md`, and flag affected rows as `adapted`.
   Translate the same premise for every compositor that can express it.
3. Add the source commit to `pins.toml` and its versioned name under `[snapshot]`.
4. [Generate snapshots](reproducing.md) and classify every i3-suite non-pass
   in `i3/classifications/<snapshot>.toml`, citing source. Sway IPC
   classifications live in `sway-ipc/classifications/<snapshot>.toml`.

An adapter must not change an assertion or an observed IPC value.
Read the [contribution rules](../CONTRIBUTING.md) before translating or
classifying a difference; [result terms](results.md#how-to-read-a-block) are explained separately.

## Check whether the interface fits

The runners connect to `$SWAYSOCK` or `$I3SOCK`, send `RUN_COMMAND` using sway
syntax, and read `GET_TREE` in the i3 tree schema. A tiling layout alone is not
enough; the compositor needs that IPC interface.

| Project | Status |
| --- | --- |
| [Wayfire](https://github.com/WayfireWM/wayfire) | Its experimental [wayfire-ipc plugin](https://github.com/AR-CADE/wayfire-ipc) speaks i3/sway IPC. No adapter yet. |
| [hy3](https://github.com/outfoxxed/hy3) | A Hyprland layout plugin, driven by Hyprland dispatchers via keybindings, Lua (`hl.plugin.hy3` passed to `hl.bind`), or Hyprland IPC (`hyprctl dispatch hy3:…`). No i3/sway IPC socket. |
| [hy3-lua](https://github.com/aarobc/hy3-lua) | A separate Lua layout, registered as `lua:hy3` on Hyprland 0.50+. It also uses Hyprland's interface, not i3/sway IPC. |
| i3-gaps | Merged into i3 in 4.22; covered by the i3 snapshot. |

Supporting either Hyprland layout would require a layer translating sway
commands and the i3 tree into Hyprland dispatchers and JSON. That layer would
be under test, not the layout itself.
