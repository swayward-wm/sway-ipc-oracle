#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <unistd.h>
#include <wayland-client.h>
#include "xdg-shell-client-protocol.h"

static struct wl_compositor *compositor;
static struct wl_shm *shm;
static struct xdg_wm_base *wm_base;

static void registry_global(void *data, struct wl_registry *registry, uint32_t name,
                            const char *interface, uint32_t version) {
    (void)data;
    (void)version;
    if (strcmp(interface, wl_compositor_interface.name) == 0)
        compositor = wl_registry_bind(registry, name, &wl_compositor_interface, 4);
    else if (strcmp(interface, wl_shm_interface.name) == 0)
        shm = wl_registry_bind(registry, name, &wl_shm_interface, 1);
    else if (strcmp(interface, xdg_wm_base_interface.name) == 0)
        wm_base = wl_registry_bind(registry, name, &xdg_wm_base_interface, 1);
}

static void registry_remove(void *data, struct wl_registry *registry, uint32_t name) {
    (void)data;
    (void)registry;
    (void)name;
}

static const struct wl_registry_listener registry_listener = {
    .global = registry_global,
    .global_remove = registry_remove,
};

static void wm_base_ping(void *data, struct xdg_wm_base *base, uint32_t serial) {
    (void)data;
    xdg_wm_base_pong(base, serial);
}

static const struct xdg_wm_base_listener wm_base_listener = {
    .ping = wm_base_ping,
};

struct toplevel {
    struct wl_surface *surface;
    int configured;
};

/* Ack every configure. After the first, commit at once so the compositor sees
 * the ack, as a real client does: sway's transactions otherwise wait for the
 * txn timeout and IPC reports the state from before the configure. */
static void surface_configure(void *data, struct xdg_surface *surface, uint32_t serial) {
    struct toplevel *toplevel = data;
    xdg_surface_ack_configure(surface, serial);
    if (toplevel->configured)
        wl_surface_commit(toplevel->surface);
    toplevel->configured = 1;
}

static const struct xdg_surface_listener surface_listener = {
    .configure = surface_configure,
};

static struct wl_buffer *make_buffer(void) {
    int fd = memfd_create("xdg-toplevel-fixture", MFD_CLOEXEC);
    if (fd < 0 || ftruncate(fd, 4) < 0) {
        perror("buffer file");
        exit(1);
    }
    uint32_t *pixel = mmap(NULL, 4, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
    if (pixel == MAP_FAILED) {
        perror("mmap");
        exit(1);
    }
    *pixel = 0xff808080;
    struct wl_shm_pool *pool = wl_shm_create_pool(shm, fd, 4);
    struct wl_buffer *buffer = wl_shm_pool_create_buffer(
        pool, 0, 1, 1, 4, WL_SHM_FORMAT_XRGB8888);
    wl_shm_pool_destroy(pool);
    munmap(pixel, 4);
    close(fd);
    return buffer;
}

static struct xdg_toplevel *map_toplevel(struct wl_display *display, const char *app_id,
                                         int min_width, int min_height,
                                         int max_width, int max_height,
                                         struct xdg_toplevel *parent) {
    struct wl_surface *surface = wl_compositor_create_surface(compositor);
    struct xdg_surface *xdg_surface = xdg_wm_base_get_xdg_surface(wm_base, surface);
    struct xdg_toplevel *toplevel = xdg_surface_get_toplevel(xdg_surface);
    struct toplevel *state = calloc(1, sizeof(*state));
    if (!state) {
        perror("calloc");
        exit(1);
    }
    state->surface = surface;
    xdg_surface_add_listener(xdg_surface, &surface_listener, state);
    xdg_toplevel_set_app_id(toplevel, app_id);
    xdg_toplevel_set_title(toplevel, app_id);
    xdg_toplevel_set_min_size(toplevel, min_width, min_height);
    xdg_toplevel_set_max_size(toplevel, max_width, max_height);
    if (parent)
        xdg_toplevel_set_parent(toplevel, parent);
    wl_surface_commit(surface);
    while (!state->configured && wl_display_dispatch(display) >= 0) {}
    if (!state->configured) {
        fputs("compositor disconnected before initial configure\n", stderr);
        exit(1);
    }
    wl_surface_attach(surface, make_buffer(), 0, 0);
    wl_surface_damage_buffer(surface, 0, 0, 1, 1);
    wl_surface_commit(surface);
    wl_display_flush(display);
    return toplevel;
}

int main(int argc, char **argv) {
    if (argc != 7) {
        fprintf(stderr, "usage: %s APP_ID MIN_WIDTH MIN_HEIGHT MAX_WIDTH MAX_HEIGHT PARENT\n", argv[0]);
        return 2;
    }
    struct wl_display *display = wl_display_connect(NULL);
    if (!display) {
        fputs("cannot connect to Wayland display\n", stderr);
        return 1;
    }
    struct wl_registry *registry = wl_display_get_registry(display);
    wl_registry_add_listener(registry, &registry_listener, NULL);
    wl_display_roundtrip(display);
    if (!compositor || !shm || !wm_base) {
        fputs("required Wayland globals are unavailable\n", stderr);
        return 1;
    }
    xdg_wm_base_add_listener(wm_base, &wm_base_listener, NULL);

    struct xdg_toplevel *parent = NULL;
    if (atoi(argv[6]))
        parent = map_toplevel(display, "fixture-hint-parent", 0, 0, 0, 0, NULL);
    map_toplevel(display, argv[1], atoi(argv[2]), atoi(argv[3]), atoi(argv[4]),
                 atoi(argv[5]), parent);
    while (wl_display_dispatch(display) >= 0) {}
    return 0;
}
