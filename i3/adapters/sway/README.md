# sway adapter

This adapter replaces only i3's compositor launcher and its `I3_SYNC` barrier.
It starts pinned sway with a headless wlroots backend, private IPC and X11
sockets, and runs real X11 clients on sway's own Xwayland. The optional direct
workspace navigation shim is enabled because sway omits i3's intermediate
output `content` node (`sway/sway/ipc-json.c:869-874`).

Like the swayward adapter, it converts i3's `fake-outputs` directive into
headless output count, mode, and position settings, then maps `fake-N` to
`HEADLESS-(count-N)` at config and command boundaries and back in IPC replies and
subscribed event payloads. The headless backend announces its outputs
last-first, so sway gives workspace 1 to `HEADLESS-count`; this mapping keeps
i3's premise that `fake-0` is the first output, holds workspace 1 and has the
initial focus. It also translates i3's `workspace_layout stacked`
and `layout stacked` spelling to sway's `stacking`.
Rows affected by these translations carry the corresponding `adapted` flags in
`i3/results/sway-1.12.toml`. The i3-derived recorder also preserves each source
fake output's mode, position, and initial focus; derived rows that replay this
setup carry `adapted = ["source-fake-output-layout"]`.

Besides replacing `I3_SYNC`, the shim adds one map rule at its barriers.
X `MapNotify` only shows that the X server mapped a window, not that the
window manager manages it. With pinned wlroots, Xwayland can commit a window's
first buffer before the XWM associates the `wl_surface` with the X window.
The window then never maps on the Wayland side, so it never enters sway's
tree and its `for_window` rules never run. Configure and repaint requests do
not recover it; unmap and map do. At the next `wait_for_map` or
`sync_with_i3` after a test maps a top-level, non-override-redirect window,
the shim checks the window. If X reports it viewable but it is neither in the
root `_NET_CLIENT_LIST` nor in `GET_TREE` within 0.5 s, the shim unmaps it,
maps it again and waits for the new `MapNotify`. Before a second re-map it
waits 1.5 s, so a slow host does not cause a spurious one. It re-maps at most
twice, and checks pending windows in the order the test mapped them. The rule
holds for any EWMH window manager. The swayward adapter does not apply it (see
its README).

### Known limitation: lost Xwayland maps

This is a measured sway/wlroots limitation, not a test property. The adapter
works around it and does not hide it:

- Cause (pinned wlroots c1d38536): `xwayland_surface_associate`
  (`xwayland/xwm.c:1178-1192`) attaches the commit listener when the XWM
  handles `WL_SURFACE_SERIAL` (`xwm_handle_surface_serial_message`,
  `xwm.c:1480-1506`). It never checks whether the `wl_surface` already has a
  buffer. Xwayland can commit the first buffer before that: the role commit
  (`xwayland/shell.c:46-56`) arrives on the Wayland connection and the
  serial on the XWM's X connection, and `wl_event_loop` does not order the
  two. `xwayland_surface_handle_commit` (`xwm.c:1119-1123`) maps only on a
  later buffer commit, which a static test window never sends. The other
  association paths (`xwm.c:2119-2128`) have the same gap.
- Rate: about 1 map in 25 (60-window reproduction loop). In a full
  i3-suite run that is about 25 lost maps. Before the rule, 15 to 27 files
  per run hit the shim's 2 s window-not-in-tree timeout, and seven serial
  runs disagreed by 41 to 87 assertions outside `i3/unstable.toml`. With the
  rule, three runs agreed exactly.
- Upstream: the missing check is still on wlroots master. We have not filed
  an upstream report yet.
- Counting: every re-map writes `# swaycal re-map window=0x<id> try=<n>` to
  stderr, which the runner stores in the test's `.tap` file. The `.tap`
  files are in the run's work directory (`<out>.work` for
  `contrib/validate reproduce ... --out <out>`). Count the re-maps of a run
  with
  `grep -h '^# swaycal re-map ' <work-dir>/*.tap | wc -l` and the affected
  files with `grep -l '^# swaycal re-map ' <work-dir>/*.tap | wc -l`.
  `try=2` lines mean the first re-map was lost as well.

### 280-wm-class-change-handler.t is excluded as flaky

Assertion 4 reads a WM_CLASS that is not NUL-terminated, and wlroots
`read_surface_class` at the pin reads past its end (fixed upstream in wlroots
`851cdd00`). The result depends on uninitialised memory: in serial runs the
file either stops with malformed JSON after assertion 3 (TAP plan missing) or
reaches assertion 4 and fails it with trailing garbage. Because its TAP plan
differs between runs, `i3/flaky.toml` excludes the whole file for sway.
