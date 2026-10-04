# Fixture: a side-by-side snapshot table, one row per compositor

readme-snapshots must reject this table: it puts three compositors side by side.

## Snapshots

| Snapshot | i3 suite (pass/skip/fail) | sway IPC | Commit |
| --- | --- | --- | --- |
| `i3-4.25` | 3,754/1/0 | 242/246/540 | `9be3249a` |
| `sway-1.12` | 1,461/20/2,117 | 740/0/40 | `88869399` |
| `swayward-ec03e0af` | 1,453/11/2,269 | 749/31/0 | `ec03e0af` |

## End
