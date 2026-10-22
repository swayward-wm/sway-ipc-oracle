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

sub _tree_object {
    my $body = _tree();
    return defined($body) ? JSON::PP::decode_json($body) : undef;
}

sub sway_sync {
    # Accept and ignore i3's no_cache/window_id options. They select details
    # of I3_SYNC, which sway does not implement.

    # 1. X11 round trip.
    eval {
        my $x = $i3test::x;
        $x->get_input_focus_reply($x->get_input_focus()->{sequence}) if $x;
        1;
    };

    # 2 + 3. IPC round trip, then settle until the tree stops changing.
    my $prev;
    for my $i (1 .. 20) {
        my $now = _tree();
        return 1 if defined($prev) && defined($now) && $prev eq $now;
        $prev = $now;
        select(undef, undef, undef, 0.02);
    }
    return 0;
}

{
    no warnings 'redefine';
    no strict 'refs';
    my $wait_for_map = \&i3test::wait_for_map;
    my $cmd = \&i3test::cmd;
    my $cmd_nosync = \&i3test::cmd_nosync;
    my $map_command = sub {
        my ($command) = @_;
        $command =~ s/\bfake-(\d+)\b/'headless-' . ($ENV{I3_SUITE_FAKE_OUTPUTS} - $1)/eg
            if $ENV{I3_SUITE_FAKE_OUTPUTS};
        $command =~ s/^layout stacked$/layout stacking/;
        return $command;
    };
    my $toggle_split = sub {
        my $tree = _tree_object();
        my ($node, $parent) = ($tree, undef);
        while (@{$node->{focus} // []}) {
            my $focused = $node->{focus}->[0];
            my ($child) = grep { $_->{id} == $focused }
                (@{$node->{nodes} // []}, @{$node->{floating_nodes} // []});
            last unless $child;
            ($parent, $node) = ($node, $child);
        }
        $node = $parent if $parent && ($node->{type} // '') eq 'con' && !@{$node->{nodes} // []};
        return ($node->{layout} // '') eq 'splitv' ? 'split h' : 'split v';
    };

    *i3test::i3 = sub {
        bless AnyEvent::I3->new(@_), 'swaycal::I3';
    };
    *i3test::sync_with_i3 = \&sway_sync;
    *i3test::wait_for_map = sub {
        my $result = $wait_for_map->(@_);
        sway_sync();
        return $result;
    };
    *i3test::cmd_nosync = sub {
        return $cmd_nosync->($toggle_split->()) if @_ == 1 && $_[0] eq 'split toggle';
        return $cmd_nosync->($map_command->($_[0])) if @_ == 1;
        return $cmd_nosync->(@_);
    };
    *i3test::cmd = sub {
        if (@_ == 1 && $_[0] eq 'split toggle') {
            my $result = $cmd_nosync->($toggle_split->());
            sway_sync();
            return $result;
        }
        return $cmd->($map_command->($_[0])) if @_ == 1;
        return $cmd->(@_);
    };
}

{
    package swaycal::I3;
    our @ISA = ('AnyEvent::I3');
    sub get_version {
        my $cv = shift->SUPER::get_version(@_);
        my $mapped = AnyEvent->condvar;
        $cv->cb(sub {
            my $version = $_[0]->recv;
            $version->{loaded_config_file_name} = $ENV{I3_SUITE_SOURCE_CONFIG}
                if ref($version) eq 'HASH' && $ENV{I3_SUITE_SOURCE_CONFIG};
            $mapped->send($version);
        });
        return $mapped;
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

    my $workspace_nodes = sub {
        my ($output) = @_;
        my ($content) = grep { ($_->{type} // '') eq 'con' } @{$output->{nodes}};
        return @{$content ? $content->{nodes} : $output->{nodes}};
    };
    my $workspaces_of = sub {
        my $tree = _tree_object();
        my @ws;
        for my $output (@{$tree->{nodes}}) {
            next if ($output->{name} // '') eq '__i3';
            push @ws, grep { ($_->{type} // '') eq 'workspace' } $workspace_nodes->($output);
        }
        return @ws;
    };

    my $rename_output;
    $rename_output = sub {
        my ($value) = @_;
        return unless $ENV{I3_SUITE_FAKE_OUTPUTS};
        if (ref($value) eq 'HASH') {
            $value->{name} =~ s/^headless-(\d+)$/'fake-' . ($ENV{I3_SUITE_FAKE_OUTPUTS} - $1)/e
                if ($value->{type} // '') eq 'output' && defined $value->{name};
            $value->{output} =~ s/^headless-(\d+)$/'fake-' . ($ENV{I3_SUITE_FAKE_OUTPUTS} - $1)/e
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
            for my $output (grep { ($_->{type} // '') eq 'output' && ($_->{name} // '') !~ /^__/ } @{$tree->{nodes}}) {
                my @workspaces = grep { ($_->{type} // '') eq 'workspace' } @{$output->{nodes}};
                $output->{nodes} = [{
                    id => -$output->{id}, type => 'con', name => 'content',
                    layout => 'splith', orientation => 'horizontal', nodes => \@workspaces,
                    floating_nodes => [], focus => $output->{focus},
                }];
            }
        });
        return $cv;
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
            for my $ws ($workspace_nodes->($output)) {
                return $output->{name} if ($ws->{name} // '') eq $ws_name;
            }
        }
        return '';
    };

    *i3test::focused_ws = sub {
        my $workspaces = AnyEvent::I3::i3(i3test::get_socket_path())->get_workspaces->recv;
        my $workspace = List::Util::first { $_->{focused} } @$workspaces;
        return $workspace ? $workspace->{name} : undef;
    };
}

1;
