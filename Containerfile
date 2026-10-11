FROM registry.fedoraproject.org/fedora:44

COPY pins.toml /opt/oracle-pins.toml

RUN dnf install -y \
        bash git gcc gcc-c++ clang cargo meson ninja-build pkgconf-pkg-config \
        cairo-devel cairo-gobject-devel dbus-devel json-c-devel libdisplay-info-devel libev-devel libevdev-devel libinput-devel \
        libliftoff-devel libseat-devel libudev-devel libxkbcommon-devel libxkbcommon-x11-devel \
        mesa-libEGL-devel mesa-libgbm-devel pango-devel pcre2-devel \
        pipewire-devel startup-notification-devel systemd-devel wayland-devel \
        wayland-protocols-devel libxcb-devel xcb-proto xcb-util-devel xcb-util-cursor-devel xcb-util-errors-devel \
        xcb-util-keysyms-devel xcb-util-wm-devel xcb-util-xrm-devel yajl-devel \
        foot google-noto-sans-mono-vf-fonts perl-AnyEvent perl-AnyEvent-I3 perl-ExtUtils-Depends \
        perl-ExtUtils-PkgConfig perl-IPC-Run perl-Inline-C perl-JSON-PP \
        perl-Test-Deep perl-Test-Differences perl-Test-Exception perl-Test-Fatal \
        perl-Test-Simple perl-XML-Parser perl-XML-Simple perl-App-cpanminus perl-LWP-Protocol-https python3 scdoc \
        xdotool xkeyboard-config xorg-x11-server-Xephyr xorg-x11-server-Xvfb xorg-x11-server-Xwayland xorg-x11-server-Xwayland-devel \
        xorg-x11-xauth xorg-x11-xinit xterm xwayland-satellite \
    && dnf clean all

RUN cpanm --notest X11::XCB@0.25 || { cat /root/.cpanm/work/*/build.log; false; }

RUN I3_COMMIT=$(awk -F '"' '$1 ~ /^i3 = / { print $2; exit }' /opt/oracle-pins.toml) \
    && git clone https://github.com/i3/i3.git /opt/i3-src \
    && git -C /opt/i3-src checkout "$I3_COMMIT" \
    && meson setup /opt/i3-src/build /opt/i3-src \
    && meson compile -C /opt/i3-src/build

RUN SWAY_COMMIT=$(awk -F '"' '$1 ~ /^sway = / { print $2; exit }' /opt/oracle-pins.toml) \
    && WLROOTS_COMMIT=$(awk -F '"' '$1 ~ /^wlroots = / { print $2; exit }' /opt/oracle-pins.toml) \
    && git clone https://github.com/swaywm/sway.git /opt/sway-src \
    && git -C /opt/sway-src checkout "$SWAY_COMMIT" \
    && git clone https://gitlab.freedesktop.org/wlroots/wlroots.git /opt/sway-src/subprojects/wlroots \
    && git -C /opt/sway-src/subprojects/wlroots checkout "$WLROOTS_COMMIT" \
    && meson setup /opt/sway-src/build /opt/sway-src -Ddefault-wallpaper=false -Dman-pages=disabled \
    && meson compile -C /opt/sway-src/build

RUN SWAYFX_COMMIT=$(awk -F '"' '$1 ~ /^swayfx = / { print $2; exit }' /opt/oracle-pins.toml) \
    && SCENEFX_COMMIT=$(awk -F '"' '$1 ~ /^scenefx = / { print $2; exit }' /opt/oracle-pins.toml) \
    && WLROOTS_COMMIT=$(awk -F '"' '$1 ~ /^wlroots = / { print $2; exit }' /opt/oracle-pins.toml) \
    && git clone https://github.com/wlrfx/swayfx.git /opt/swayfx-src \
    && git -C /opt/swayfx-src checkout "$SWAYFX_COMMIT" \
    && git clone https://github.com/wlrfx/scenefx.git /opt/swayfx-src/subprojects/scenefx \
    && git -C /opt/swayfx-src/subprojects/scenefx checkout "$SCENEFX_COMMIT" \
    && git clone https://gitlab.freedesktop.org/wlroots/wlroots.git /opt/swayfx-src/subprojects/wlroots \
    && git -C /opt/swayfx-src/subprojects/wlroots checkout "$WLROOTS_COMMIT" \
    && meson setup /opt/swayfx-src/build /opt/swayfx-src -Ddefault-wallpaper=false -Dman-pages=disabled \
    && meson compile -C /opt/swayfx-src/build

RUN SWAYWARD_COMMIT=$(awk -F '"' '$1 ~ /^swayward = / { print $2; exit }' /opt/oracle-pins.toml) \
    && git clone https://github.com/swayward-wm/swayward.git /opt/swayward-src \
    && git -C /opt/swayward-src checkout "$SWAYWARD_COMMIT" \
    && CARGO_BUILD_JOBS=2 cargo build --manifest-path /opt/swayward-src/Cargo.toml --release \
    && rm -rf /opt/swayward-src/target/release/{build,deps,incremental,.fingerprint}

# scroll carries its own wlroots 0.21-dev in-tree (subprojects/wlroots) and
# needs lua and readline. meson leaves an untracked subprojects/.wraplock,
# which would mark the checkout dirty.
RUN SCROLL_COMMIT=$(awk -F '"' '$1 ~ /^scroll = / { print $2; exit }' /opt/oracle-pins.toml) \
    && dnf install -y lua-devel readline-devel \
    && dnf clean all \
    && git clone https://github.com/dawsers/scroll.git /opt/scroll-src \
    && git -C /opt/scroll-src checkout "$SCROLL_COMMIT" \
    && meson setup /opt/scroll-src/build /opt/scroll-src -Ddefault-wallpaper=false -Dman-pages=disabled \
    && meson compile -C /opt/scroll-src/build \
    && rm -f /opt/scroll-src/subprojects/.wraplock

# miracle-wm is a Mir compositor (CMake), built against Fedora's Mir packages.
# mir-test-tools carries the mir:stub-input platform that headless runs need.
# The build regenerates a tracked wayland wrapper in src/ (protocols/CMakeLists.txt),
# so the checkout is restored afterwards to keep the build clean.
RUN MIRACLE_COMMIT=$(awk -F '"' '$1 ~ /^miracle-wm = / { print $2; exit }' /opt/oracle-pins.toml) \
    && dnf install -y cmake mir-devel mir-internal-devel mir-test-tools yaml-cpp-devel glib2-devel \
        json-devel mesa-libGLES-devel jpcre2-devel glm-devel libdrm-devel libnotify-devel \
        boost-devel gtest-devel gmock-devel wasmedge-devel \
    && dnf clean all \
    && git clone https://github.com/miracle-wm-org/miracle-wm.git /opt/miracle-src \
    && git -C /opt/miracle-src checkout "$MIRACLE_COMMIT" \
    && cmake -G Ninja -S /opt/miracle-src -B /opt/miracle-src/build -DCMAKE_BUILD_TYPE=RelWithDebInfo \
        -DENABLE_TESTS=OFF -DBUILD_ERROR_REPORTER=OFF -DBUILD_DEBUG_OVERLAY=OFF \
    && ninja -j4 -C /opt/miracle-src/build \
    && git -C /opt/miracle-src checkout -- src

# swirl is a rebrand of scroll 1.12.17 with the same in-tree wlroots and
# dependencies. Its meson.build:228 installs swirl.png, which the pinned tree
# does not contain, so setup fails without it: an empty stand-in exists only
# during setup. It is removed with the .wraplock so the checkout stays clean.
RUN SWIRL_COMMIT=$(awk -F '"' '$1 ~ /^swirl = / { print $2; exit }' /opt/oracle-pins.toml) \
    && git clone https://github.com/visnudeva/swirl.git /opt/swirl-src \
    && git -C /opt/swirl-src checkout "$SWIRL_COMMIT" \
    && touch /opt/swirl-src/swirl.png \
    && meson setup /opt/swirl-src/build /opt/swirl-src -Ddefault-wallpaper=false -Dman-pages=disabled \
    && rm /opt/swirl-src/swirl.png \
    && meson compile -C /opt/swirl-src/build \
    && rm -f /opt/swirl-src/subprojects/.wraplock

ENV ORACLE_CONTAINER=1 \
    I3SRC=/opt/i3-src \
    I3BUILD=/opt/i3-src/build \
    I3_BINARY=/opt/i3-src/build/i3 \
    SWAY_BINARY=/opt/sway-src/build/sway/sway \
    SWAYWARD_BINARY=/opt/swayward-src/target/release/swayward \
    SWAYFX_BINARY=/opt/swayfx-src/build/sway/sway \
    SCROLL_BINARY=/opt/scroll-src/build/sway/scroll \
    MIRACLE_WM_BINARY=/opt/miracle-src/build/miracle-wm \
    SWIRL_BINARY=/opt/swirl-src/build/sway/swirl \
    XDG_RUNTIME_DIR=/run/oracle-runtime

RUN mkdir -m 700 /run/oracle-runtime \
    && git config --system --add safe.directory /oracle

WORKDIR /oracle
CMD ["./contrib/validate"]
