package SocketActivation;
# Sway-side replacement for i3's testcases/lib/SocketActivation.pm.
#
# i3test.pm calls activate_i3() to start the window manager under test. It is
# the only launch hook in the upstream harness, so shadowing this one file
# starts sway instead of i3 while leaving lib/i3test.pm and every t/*.t file
# upstream.
#
# Differences from i3's version, all forced by sway not being i3:
#
#   * No systemd socket activation. Sway has no LISTEN_FDS path
#     (`grep -rn LISTEN_FDS sway/ common/` is empty at 88869399), so readiness
#     is a connect-and-GET_VERSION poll on $SWAYSOCK, not a pre-bound fd.
#
#   * Sway owns the X server. i3 attaches to the Xvfb that StartXServer.pm
#     created; sway is a Wayland compositor that spawns its own Xwayland and
#     becomes the window manager only there. So this module starts sway, reads
#     the display number back out of sway's log, sets $ENV{DISPLAY}, and
#     rebuilds i3test's X11 connection against it. i3's $args{display} is
#     ignored because it names a server sway will never manage.
#
#   * The socket path is published onto the new X root window as
#     I3_SOCKET_PATH by this module. Sway sets $SWAYSOCK and $I3SOCK in its own
#     environment (sway/ipc-server.c:114-115) and never writes the atom that
#     the unmodified i3test::Util::get_socket_path reads.
#
#   * i3-only flags (--shmlog-size, --disable-signalhandler, --force-xinerama,
#     -V -d all) are dropped. Sway takes -d for debug logging and -C to
#     validate.
#
#   * A two-line preamble is prepended to the config i3test wrote:
#       xwayland force        -- the headless backend starts Xwayland lazily,
#                                and a lazy Xwayland never prints the display
#                                number this module has to read back.
#       output * mode 1280x800 -- matches i3's test X server geometry
#                                (i3/testcases/lib/StartXServer.pm:106-108).
#                                Without it every rectangle assertion fails
#                                against the headless 1920x1080 default and
#                                the geometry signal is lost.
#     These are the ONLY config bytes this runner adds. The test's own config
#     text is copied through verbatim, including the `ipc-socket` line i3test
#     always writes, which sway rejects as an unknown command. That rejection
#     is left visible on purpose: it is part of what the measurement reports.

use strict;
use warnings;
use v5.10;
use IO::Socket::UNIX;
use POSIX ();
use Exporter 'import';

our @EXPORT = qw(activate_i3);

my $sway_bin  = $ENV{I3_SUITE_BINARY} or die 'I3_SUITE_BINARY is unset';
my $translator = $ENV{I3_SUITE_TRANSLATOR} or die 'I3_SUITE_TRANSLATOR is unset';
my $rundir    = $ENV{I3_SUITE_RUNDIR} or die 'I3_SUITE_RUNDIR is unset';

my $instance = 0;

sub _fake_outputs {
    my ($config) = @_;
    my ($spec) = $config =~ /^\s*fake[-_]outputs\s+(\S+)\s*$/m;
    return undef unless defined $spec;

    my @outputs;
    for my $entry (split /,/, $spec) {
        my $primary = $entry =~ s/P$//;
        $entry =~ /^(\d+)x(\d+)\+(\d+)\+(\d+)$/
            or die "invalid fake-outputs entry '$entry'";
        push @outputs, [ $1, $2, $3, $4, $primary ];
    }
    return \@outputs;
}

sub _read_display {
    my ($log) = @_;
    for (1 .. 300) {
        if (open(my $fh, '<', $log)) {
            local $/; my $text = <$fh>; close($fh);
            return $1 if $text =~ /listening on X11 socket: (:\d+)/;
        }
        select(undef, undef, undef, 0.05);
    }
    return undef;
}

sub _ipc_command {
    my ($sock, $command) = @_;
    my $cl = IO::Socket::UNIX->new(Peer => $sock) or return 0;
    print $cl 'i3-ipc' . pack('LL', length($command), 0) . $command;
    $cl->flush;
    my $hdr;
    my $ok = read($cl, $hdr, 14) == 14;
    close($cl);
    return $ok;
}

sub _publish_socket_path {
    my ($path) = @_;
    # i3test::Util::get_socket_path reads this atom off the root window.
    my $x = $i3test::x or return;
    # create => 1: sway never interns I3_SOCKET_PATH, so on its fresh Xwayland
    # the atom does not exist yet and a lookup-only intern returns None.
    my $atom = $x->atom(name => 'I3_SOCKET_PATH', create => 1);
    $x->change_property(
        0,                              # PropModeReplace
        $x->get_root_window(),
        $atom->id,
        $x->atom(name => 'UTF8_STRING', create => 1)->id,
        8,
        length($path),
        $path,
    );
    $x->flush;
}

sub activate_i3 {
    my %args = @_;

    if ($args{validate_config}) {
        my $pid = fork // die 'fork';
        if ($pid == 0) {
            open(STDOUT, '>>', "$rundir/sway-validate.log");
            open(STDERR, '>&', \*STDOUT);
            { no warnings 'exec'; exec($sway_bin, 'validate', '-c', $args{configfile}); }
            POSIX::_exit(1);
        }
        $args{cv}->send(1);
        return $pid;
    }

    my $n    = $instance++;
    my $sock = "$rundir/sway-$n.sock";
    my $log  = "$rundir/sway-log-$n";
    my $cfg  = "$rundir/sway-config-$n";
    unlink($sock, $log);

    my $source = "$rundir/sway-source-$n";
    my $source_text;
    {
        open(my $in, '<', $args{configfile}) or die "config: $!";
        local $/;
        $source_text = <$in>;
        close($in);
    }
    my $outputs = _fake_outputs($source_text);
    # Like the sway adapter: swayward announces startup headless outputs
    # last-first as wlroots does, so fake-k maps to the output announced k-th,
    # headless-(N-k). fake-0 keeps i3's identity: first output, workspace 1
    # and initial focus. The shim maps names back.
    $ENV{I3_SUITE_FAKE_OUTPUTS} = $outputs ? scalar(@$outputs) : 0;
    my $headless = sub { 'headless-' . (scalar(@$outputs) - $_[0]) };
    $source_text =~ s/^ipc-socket\s.*\n?//mg;
    $source_text =~ s/^\s*fake[-_]outputs\s+\S+\s*\n?//mg;
    $source_text =~ s/^(\s*workspace_layout\s+)stacked\s*$/${1}stacking/mg;
    $source_text =~ s/\bfake-(\d+)\b/$headless->($1)/eg if $outputs;
    # 316 uses this block only to identify the primary fake output. The
    # translated headless output already carries that identity.
    if ($ENV{TESTNAME} eq '316-drag-container.t') {
        $source_text =~ s/^\s*bar\s*\{\s*\n\s*output\s+primary\s*\n\s*\}\s*\n?//mg;
    }
    {
        open(my $out, '>', $source) or die "config copy: $!";
        print $out $source_text;
        close($out);
    }
    open(my $translated, '-|', $translator, $source) or die "translator: $!";
    open(my $out, '>', $cfg) or die "translated config: $!";
    while (my $line = <$translated>) {
        print $out $line;
    }
    if ($outputs) {
        # Like the sway adapter: focus the primary fake output, else fake-0.
        my ($focus) = grep { $outputs->[$_]->[4] } 0 .. $#$outputs;
        $focus //= 0;
        for my $i (0 .. $#$outputs) {
            my ($width, $height, $x, $y) = @{$outputs->[$i]};
            my $primary = $i == $focus;
            my $name = $headless->($i);
            print $out qq(\noutput "$name" {\n);
            print $out qq(    mode custom=true "${width}x${height}\@60"\n);
            print $out qq(    position x=$x y=$y\n);
            print $out "    focus-at-startup\n" if $primary;
            print $out "}\n";
        }
    }
    close($out);
    close($translated) or die "config translation failed: $?";
    $ENV{I3_SUITE_SOURCE_CONFIG} = $source;

    my $pid = fork // die 'fork';
    if ($pid == 0) {
        setpgrp;    # i3test's END block kills the whole group
        $ENV{SWAYSOCK} = $sock;
        delete $ENV{I3SOCK};
        delete $ENV{DESKTOP_STARTUP_ID};
        delete $ENV{SHELL};
        delete $ENV{DISPLAY};     # sway must create its own, not join ours
        $ENV{WLR_HEADLESS_OUTPUTS} = $outputs ? scalar(@$outputs) : 1;
        $ENV{RUST_LOG} = 'swayward=info';
        open(STDOUT, '>>', $log);
        open(STDERR, '>&', \*STDOUT);
        { no warnings 'exec'; exec($sway_bin, '-c', $cfg); }
        POSIX::_exit(1);
    }

    # run-one.sh reaps recorded process groups even if timeout terminates the
    # Perl harness before i3test's END block runs. The file is private to this
    # test, so cleanup never matches another calibration or the host session.
    if (open(my $pf, '>>', "$rundir/pids")) {
        say $pf $pid;
        close($pf);
    }

    my $ready = 0;
    for (1 .. 400) {
        if (-S $sock) {
            if (my $cl = IO::Socket::UNIX->new(Peer => $sock)) {
                print $cl 'i3-ipc' . pack('LL', 0, 7);   # GET_VERSION
                $cl->flush;
                my $hdr;
                $ready = 1 if read($cl, $hdr, 14);
                close($cl);
                last if $ready;
            }
        }
        select(undef, undef, undef, 0.05);
    }

    if ($ready) {
        if ($outputs) {
            for my $i (0 .. $#$outputs) {
                my ($width, $height, $x, $y) = @{$outputs->[$i]};
                my $name = $headless->($i);
                _ipc_command($sock, "output $name mode --custom ${width}x${height}\@60Hz position $x $y");
            }
        } else {
            _ipc_command($sock, 'output * mode --custom 1280x800@60Hz');
        }
        my $display = _read_display($log);
        if (defined $display) {
            $ENV{DISPLAY} = $display;
            # Rebind i3test's exported $x to sway's Xwayland. Exporter aliases
            # the same SV into the test package, so the .t file's $x follows.
            $i3test::x = i3test::X11->new;
            _publish_socket_path($sock);
        } else {
            $ready = 0;
        }
    }

    $ENV{SWAYSOCK} = $sock;
    $ENV{I3SOCK} = $sock;
    $args{cv}->send($ready);
    return $pid;
}

1;
