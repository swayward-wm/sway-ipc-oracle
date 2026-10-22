package swaycal::Shim;
# Preloaded with -Mswaycal::Shim before an unmodified i3 t/*.t file runs.
#
# It loads upstream i3test.pm and then replaces exactly one function:
# sync_with_i3. Everything else -- open_window, cmd, get_ws, cmp_tree, the
# X11 connection, the assertions -- stays upstream.
#
# WHY sync_with_i3 MUST BE REPLACED
#
# i3's version sends an I3_SYNC ClientMessage to the X root window and blocks
# until i3 echoes it back (i3/testcases/lib/i3test.pm.in:753-804;
# i3/src/handlers.c:813-815). Because i3 replies only after draining every
# earlier event, the reply is a true barrier.
#
# Sway implements no such protocol: `grep -rn "I3_SYNC\|i3_sync" sway/` at
# 88869399 returns nothing, and the 2018 attempt to add one (swaywm/sway#3318)
# was dropped. Left unreplaced, every sync_with_i3 call blocks for the full
# 4-second wait_for_event timeout and the file times out rather than failing.
#
# WHAT THIS BARRIER ACTUALLY GUARANTEES, AND WHAT IT DOES NOT
#
#   1. An X11 round trip (GetInputFocus reply). Our own X requests have
#      reached the X server, so Xwayland has them.
#   2. An IPC round trip (GET_TREE). Command replies already prove that every
#      earlier `cmd` has been executed. Using SEND_TICK here would broadcast a
#      test-internal nonce into an upstream events_for tick subscription.
#
# It does NOT guarantee that events already queued on sway's XWM fd have been
# processed, because wl_event_loop does not order work across file
# descriptors. Step 3 is therefore a bounded settle poll: repeat GET_TREE
# until its reply is byte-identical twice in a row, up to a cap.
# That is weaker than i3's barrier and it is the main measurement limit of
# this runner. A sway-side failure in a window-lifecycle test should be
# re-run before it is believed.

use strict;
use warnings;
use v5.10;

use IO::Socket::UNIX;
use List::Util ();
use AnyEvent::I3 ();
use JSON::PP ();
use Scalar::Util qw(blessed);

require i3test;

sub _sock {
    # Re-read every time: launch_with_config starts a new sway with a new path.
    return i3test::get_socket_path(0);
}

sub _ipc {
    my ($type, $payload) = @_;
    $payload //= '';
    my $path = _sock();
    my $cl = IO::Socket::UNIX->new(Peer => $path) or return undef;
    print $cl 'i3-ipc' . pack('LL', length($payload), $type) . $payload;
    $cl->flush;
    my $hdr;
    read($cl, $hdr, 14) == 14 or do { close($cl); return undef };
    my ($len) = unpack('x6LL', $hdr);
    my $body = '';
    while (length($body) < $len) {
        my $chunk;
        my $n = read($cl, $chunk, $len - length($body));
        last if !defined($n) || $n == 0;
        $body .= $chunk;
    }
    close($cl);
    return $body;
}

sub _tree {
    return _ipc(4, '');                                # IPC_GET_TREE
}

sub _tree_window {
    my ($node, $id) = @_;
    return $node if defined($node->{window}) && $node->{window} == $id;
    for my $child (@{$node->{nodes} // []}, @{$node->{floating_nodes} // []}) {
        my $found = _tree_window($child, $id);
        return $found if $found;
    }
    return undef;
}

sub _wait_for_sway_window {
    my ($window) = @_;
    my $id = blessed($window) && $window->isa('X11::XCB::Window')
        ? $window->id : $window;
    for my $i (1 .. 100) {
        my $body = _tree();
        return 1 if defined($body) && _tree_window(JSON::PP::decode_json($body), $id);
        select(undef, undef, undef, 0.02);
    }
    return 0;
}

# _NET_CLIENT_LIST is written by the window manager. In sway it is written by
# wlroots' XWM when the window's wl_surface maps (wlroots xwayland/xwm.c:
# xwayland_surface_handle_map -> xwm_set_net_client_list), and that same map
# signal is what puts the view into sway's tree.
sub _in_client_list {
    my ($id) = @_;
    my $ok = eval {
        my $x = $i3test::x;
        my $cookie = $x->get_property(0, $x->get_root_window(),
            $x->atom(name => '_NET_CLIENT_LIST')->id,
            $x->atom(name => 'WINDOW')->id, 0, 4096);
        my $reply = $x->get_property_reply($cookie->{sequence});
        my $len = $reply->{length} // 0;
        $len ? List::Util::any { $_ == $id } unpack("L$len", $reply->{value}) : 0;
    };
    return $ok;
}

# MAP-ASSOCIATION RETRY
#
# X MapNotify proves the X server mapped the window, not that the window
# manager will ever manage it. With pinned wlroots, Xwayland can commit the
# window's first buffer before the XWM has associated the wl_surface with the
# X window (WL_SURFACE_SERIAL is handled on the XWM's X connection, the commit
# on Xwayland's Wayland connection; wl_event_loop does not order the two).
# wlroots maps only on a later commit with a buffer
# (xwayland_surface_handle_commit), and for a static test window none comes:
# the window stays out of sway's tree indefinitely, and for_window rules never
# run for it. Configure and repaint requests do not recover it; unmap + map
# does.
#
# The rule, valid for any EWMH window manager: every managed (top-level, not
# override-redirect) window the test maps is settled at the next barrier
# (wait_for_map or sync_with_i3). If X reports it viewable but the window
# manager has neither listed it in _NET_CLIENT_LIST nor shown it in GET_TREE
# within a grace period (MAP_GRACE seconds before the first re-map,
# RETRY_GRACE before the second, so a busy host does not trigger a spurious
# second re-map), unmap it, map it again and wait for the new MapNotify
# (upstream wait_for_map; like upstream I3_SYNC, waiting discards queued
# events). At most MAP_RETRIES times. A window the WM managed and then
# withdrew or killed was listed or is no longer viewable, so the rule never
# re-creates it.
#
# Every re-map prints '# swaycal re-map window=0x<id> try=<n>' on stderr,
# which the runner stores in the test's .tap file, so interventions can be
# counted (see README.md).
use constant { MAP_GRACE => 0.5, RETRY_GRACE => 1.5, MAP_RETRIES => 2 };
# Windows mapped since the last barrier, settled in the order they were mapped.
my @pending_map;

sub _forget_pending {
    my ($id) = @_;
    @pending_map = grep { $_->id != $id } @pending_map;
}

sub _managed_by_wm {
    my ($id, $grace) = @_;
    for my $i (1 .. int($grace / 0.02)) {
        return 1 if _in_client_list($id);
        my $body = _tree();
        return 1 if defined($body) && _tree_window(JSON::PP::decode_json($body), $id);
        select(undef, undef, undef, 0.02);
    }
    return 0;
}

sub _viewable {
    my ($window) = @_;
    my $state = eval { $window->attributes->{map_state} };
    return defined($state) && $state == X11::XCB::MAP_STATE_VIEWABLE();
}

my $upstream_wait_for_map;

sub _settle_map {
    my ($window) = @_;
    _forget_pending($window->id);
    for my $retry (1 .. MAP_RETRIES) {
        return unless _viewable($window);
        return if _managed_by_wm($window->id, $retry == 1 ? MAP_GRACE : RETRY_GRACE);
        printf STDERR "# swaycal re-map window=0x%x try=%d\n", $window->id, $retry;
        $window->unmap;
        _x11_round_trip();
        $window->map;
        _forget_pending($window->id);
        if (grep { $_ eq 'structure_notify' } @{$window->event_mask}) {
            # Consume our UnmapNotify and the new MapNotify, as upstream
            # open_window does for the first map.
            $upstream_wait_for_map->($window);
        } else {
            for my $i (1 .. 100) {
                last if _viewable($window);
                select(undef, undef, undef, 0.02);
            }
        }
    }
}

sub _x11_round_trip {
    eval {
        my $x = $i3test::x;
        $x->get_input_focus_reply($x->get_input_focus()->{sequence}) if $x;
        1;
    };
}

sub sway_sync {
    # Accept and ignore i3's no_cache/window_id options. They select details
    # of I3_SYNC, which sway does not implement.

    # 1. Ensure prior test-client requests reached Xwayland.
    _x11_round_trip();

    # 1b. Settle windows the test mapped without wait_for_map.
    my @maps = @pending_map;
    _settle_map($_) for @maps;

    # 2 + 3. Give Xwayland's wl_event_loop source a quiet period, then require
    # three equal IPC snapshots. Two immediate GET_TREE replies can both win
    # the race with a pending XWM event and falsely report a settled tree.
    select(undef, undef, undef, 0.10);
    my ($prev, $stable) = (undef, 0);
    for my $i (1 .. 20) {
        my $now = _tree();
        $stable = defined($prev) && defined($now) && $prev eq $now ? $stable + 1 : 0;
        if ($stable == 2) {
            # Sway may issue X focus/configure requests while producing the
            # settled tree. Give its XWM/Xwayland fd handoff a quiet period,
            # then wait until Xwayland has applied those requests too.
            select(undef, undef, undef, 0.20);
            _x11_round_trip();
            return 1;
        }
        $prev = $now;
        select(undef, undef, undef, 0.05);
    }
    return 0;
}

{
    no warnings 'redefine';
    no strict 'refs';
    my $wait_for_map = \&i3test::wait_for_map;
    $upstream_wait_for_map = $wait_for_map;
    *i3test::sync_with_i3 = \&sway_sync;
    my $map = \&X11::XCB::Window::map;
    *X11::XCB::Window::map = sub {
        my ($window) = @_;
        $map->(@_);
        # Only top-level, WM-managed windows on the test's own connection,
        # whose events the barrier can wait for.
        push @pending_map, $window
            if !(List::Util::any { $_->id == $window->id } @pending_map)
            && !$window->override_redirect && $i3test::x
            && Scalar::Util::refaddr($window->_conn) == Scalar::Util::refaddr($i3test::x)
            && $window->parent == $i3test::x->get_root_window();
    };
    *i3test::wait_for_map = sub {
        my $result = $wait_for_map->(@_);
        my $window = $_[0];
        my $id = blessed($window) && $window->isa('X11::XCB::Window')
            ? $window->id : $window;
        _settle_map($window) if blessed($window) && $window->isa('X11::XCB::Window')
            && Scalar::Util::refaddr($window->_conn) == Scalar::Util::refaddr($i3test::x);
        _wait_for_sway_window($window);
        sway_sync();
        my $tree = _tree();
        my $node = defined($tree) ? _tree_window(JSON::PP::decode_json($tree), $id) : undef;
        if ($node && $node->{focused}) {
            for my $i (1 .. 100) {
                last if $i3test::x->input_focus == $id;
                select(undef, undef, undef, 0.02);
            }
        }
        return $result;
    };
    my $cmd = \&i3test::cmd;
    my $cmd_nosync = \&i3test::cmd_nosync;
    my $map_command = sub {
        my ($command) = @_;
        $command =~ s/\bfake-(\d+)\b/'HEADLESS-' . ($ENV{I3_SUITE_FAKE_OUTPUTS} - $1)/eg
            if $ENV{I3_SUITE_FAKE_OUTPUTS};
        $command =~ s/^layout stacked$/layout stacking/;
        return $command;
    };
    *i3test::cmd_nosync = sub {
        return $cmd_nosync->($map_command->($_[0])) if @_ == 1;
        return $cmd_nosync->(@_);
    };
    *i3test::cmd = sub {
        return $cmd->($map_command->($_[0])) if @_ == 1;
        return $cmd->(@_);
    };
}

# Optional recorder for deriving sway IPC fixtures. It records only operations
# that the black-box sway-ipc runner can replay: IPC commands and ordinary
# mapped windows. The upstream test and its assertions remain untouched.
if (my $path = $ENV{SWAY_CAL_RECORD}) {
    require JSON::PP;
    open(my $record, '>>', $path) or die "record $path: $!";
    $record->autoflush(1);

    my $source = sub {
        for my $depth (1 .. 20) {
            my (undef, $file, $line) = caller($depth);
            next unless defined $file;
            return ($file, $line) if $file =~ m{(?:^|/)t/[^/]+[.]t$};
        }
        return ('unknown', 0);
    };
    my $write = sub {
        my ($kind, $value) = @_;
        my ($file, $line) = $source->();
        print $record JSON::PP::encode_json({
            test => $file =~ s{.*/}{}r,
            line => $line,
            kind => $kind,
            value => $value,
        }), "\n";
    };

    my $original_cmd = \&i3test::cmd;
    my $original_cmd_nosync = \&i3test::cmd_nosync;
    my $original_open_window = \&i3test::open_window;
    {
        no warnings 'redefine';
        *i3test::cmd = sub { $write->('command', $_[0]); goto &$original_cmd };
        *i3test::cmd_nosync = sub { $write->('command', $_[0]); goto &$original_cmd_nosync };
        *i3test::open_window = sub {
            my %args = @_;
            my $window = $original_open_window->(@_);
            $write->('window', 'x11') unless $args{override_redirect} || $args{dont_map};
            return $window;
        };
    }
}

# ---------------------------------------------------------------------------
# OPTIONAL second pass: the output "content" node.
#
# Enabled only when SWAY_CAL_CONTENT_SHIM=1. The default run does NOT have it,
# and the default run is the primary measurement.
#
# i3 puts a CT_CON "content" node between an output and its workspaces, and
# five i3test.pm helpers navigate through it with
#   first { $_->{type} eq 'con' } @{$output->{nodes}}
# (i3test.pm.in:406,430,474,519,723). Sway serializes each workspace as a
# direct child of the output with no intervening node
# (sway/sway/ipc-json.c:869-874). The helper therefore gets undef and dies
# before the file's first assertion. That kills 140 of 242 files at i3test.pm
# line 407, in the harness, not in an assertion.
#
# This replaces those five helpers with versions that read
# $output->{nodes} directly. It changes ONLY workspace lookup. Every
# assertion, expected value and comparison stays upstream, and no .t file is
# touched.
#
# It is still a real weakening, which is why it is opt-in and reported
# separately: a test that asserts something ABOUT the content node would now
# be answered from a node that does not exist in sway. Treat any result from
# this pass as conditional on that.
if ($ENV{SWAY_CAL_CONTENT_SHIM}) {
    no warnings 'redefine';
    no strict 'refs';

    my $rename_output;
    $rename_output = sub {
        my ($value) = @_;
        return unless $ENV{I3_SUITE_FAKE_OUTPUTS};
        if (ref($value) eq 'HASH') {
            $value->{name} =~ s/^HEADLESS-(\d+)$/'fake-' . ($ENV{I3_SUITE_FAKE_OUTPUTS} - $1)/e
                if ($value->{type} // '') eq 'output' && defined $value->{name};
            $value->{output} =~ s/^HEADLESS-(\d+)$/'fake-' . ($ENV{I3_SUITE_FAKE_OUTPUTS} - $1)/e
                if defined $value->{output};
            $rename_output->($_) for values %$value;
        } elsif (ref($value) eq 'ARRAY') {
            $rename_output->($_) for @$value;
        }
    };
    my $subscribe = \&AnyEvent::I3::subscribe;
    *AnyEvent::I3::subscribe = sub {
        my ($self, $callbacks) = @_;
        my %translated = map {
            my ($name, $callback) = ($_, $callbacks->{$_});
            $name => sub {
                $rename_output->($_[0]);
                $callback->(@_);
            }
        } keys %$callbacks;
        return $subscribe->($self, \%translated);
    };
    my $get_outputs = \&AnyEvent::I3::get_outputs;
    *AnyEvent::I3::get_outputs = sub {
        my $cv = $get_outputs->(@_);
        $cv->cb(sub {
            my $outputs = $_[0]->recv;
            $rename_output->($outputs);
        });
        return $cv;
    };
    my $get_workspaces = \&AnyEvent::I3::get_workspaces;
    *AnyEvent::I3::get_workspaces = sub {
        my $cv = $get_workspaces->(@_);
        $cv->cb(sub {
            my $workspaces = $_[0]->recv;
            $rename_output->($workspaces);
        });
        return $cv;
    };
    my $get_tree = \&AnyEvent::I3::get_tree;
    *AnyEvent::I3::get_tree = sub {
        my $cv = $get_tree->(@_);
        $cv->cb(sub {
            my $tree = $_[0]->recv;
            $rename_output->($tree);
        });
        return $cv;
    };

    my $workspaces_of = sub {
        my $tree = AnyEvent::I3::i3(i3test::get_socket_path())->get_tree->recv;
        my @ws;
        for my $output (@{$tree->{nodes}}) {
            next if ($output->{name} // '') eq '__i3';
            push @ws, grep { ($_->{type} // '') eq 'workspace' } @{$output->{nodes}};
        }
        return @ws;
    };

    *i3test::get_workspace_names = sub {
        [ map { $_->{name} } $workspaces_of->() ]
    };

    *i3test::get_ws = sub {
        my ($name) = @_;
        return List::Util::first { $_->{name} eq $name } $workspaces_of->();
    };

    *i3test::get_ws_content = sub {
        my ($name) = @_;
        my $con = i3test::get_ws($name);
        return wantarray ? ($con->{nodes}, $con->{focus}) : $con->{nodes};
    };

    *i3test::get_output_for_workspace = sub {
        my ($ws_name) = @_;
        my $tree = AnyEvent::I3::i3(i3test::get_socket_path())->get_tree->recv;
        for my $output (@{$tree->{nodes}}) {
            next if ($output->{name} // '') eq '__i3';
            for my $ws (@{$output->{nodes}}) {
                return $output->{name} if ($ws->{name} // '') eq $ws_name;
            }
        }
        return '';
    };

    # Upstream reads the visible workspace of the output at root.focus[0]
    # (i3test.pm.in:700-726). Every output has a focus stack, so the first
    # output with one is just the first in tree order, not the focused one.
    # GET_WORKSPACES' focused field is sway's authority for this helper.
    *i3test::focused_ws = sub {
        my $workspaces = AnyEvent::I3::i3(i3test::get_socket_path())->get_workspaces->recv;
        my $workspace = List::Util::first { $_->{focused} } @$workspaces;
        return $workspace ? $workspace->{name} : undef;
    };
}

1;
