#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <wayland-client.h>
#include "wlr-foreign-toplevel-management-unstable-v1-client-protocol.h"

static struct zwlr_foreign_toplevel_manager_v1 *manager;
static struct wl_list toplevels;

struct toplevel {
    struct zwlr_foreign_toplevel_handle_v1 *handle;
    char *app_id;
    struct wl_list link;
};

static void registry_global(void *data, struct wl_registry *registry, uint32_t name,
                            const char *interface, uint32_t version) {
    (void)data;
    if (strcmp(interface, zwlr_foreign_toplevel_manager_v1_interface.name) == 0 && version >= 2)
        manager = wl_registry_bind(registry, name, &zwlr_foreign_toplevel_manager_v1_interface, 2);
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

static void handle_title(void *data, struct zwlr_foreign_toplevel_handle_v1 *handle,
                         const char *title) {
    (void)data;
    (void)handle;
    (void)title;
}

static void handle_app_id(void *data, struct zwlr_foreign_toplevel_handle_v1 *handle,
                          const char *app_id) {
    (void)handle;
    struct toplevel *toplevel = data;
    free(toplevel->app_id);
    toplevel->app_id = strdup(app_id);
}

static void handle_output(void *data, struct zwlr_foreign_toplevel_handle_v1 *handle,
                          struct wl_output *output) {
    (void)data;
    (void)handle;
    (void)output;
}

static void handle_state(void *data, struct zwlr_foreign_toplevel_handle_v1 *handle,
                         struct wl_array *state) {
    (void)data;
    (void)handle;
    (void)state;
}

static void handle_done(void *data, struct zwlr_foreign_toplevel_handle_v1 *handle) {
    (void)data;
    (void)handle;
}

static void handle_closed(void *data, struct zwlr_foreign_toplevel_handle_v1 *handle) {
    (void)handle;
    struct toplevel *toplevel = data;
    free(toplevel->app_id);
    toplevel->app_id = NULL;
}

static const struct zwlr_foreign_toplevel_handle_v1_listener handle_listener = {
    .title = handle_title,
    .app_id = handle_app_id,
    .output_enter = handle_output,
    .output_leave = handle_output,
    .state = handle_state,
    .done = handle_done,
    .closed = handle_closed,
};

static void manager_toplevel(void *data, struct zwlr_foreign_toplevel_manager_v1 *manager,
                             struct zwlr_foreign_toplevel_handle_v1 *handle) {
    (void)data;
    (void)manager;
    struct toplevel *toplevel = calloc(1, sizeof(*toplevel));
    if (!toplevel) {
        perror("calloc");
        exit(1);
    }
    toplevel->handle = handle;
    wl_list_insert(&toplevels, &toplevel->link);
    zwlr_foreign_toplevel_handle_v1_add_listener(handle, &handle_listener, toplevel);
}

static void manager_finished(void *data, struct zwlr_foreign_toplevel_manager_v1 *manager) {
    (void)data;
    (void)manager;
}

static const struct zwlr_foreign_toplevel_manager_v1_listener manager_listener = {
    .toplevel = manager_toplevel,
    .finished = manager_finished,
};

int main(int argc, char **argv) {
    if (argc != 3) {
        fprintf(stderr, "usage: %s APP_ID set_minimized|unset_minimized|set_maximized|unset_maximized\n",
                argv[0]);
        return 2;
    }
    void (*request)(struct zwlr_foreign_toplevel_handle_v1 *);
    if (strcmp(argv[2], "set_minimized") == 0)
        request = zwlr_foreign_toplevel_handle_v1_set_minimized;
    else if (strcmp(argv[2], "unset_minimized") == 0)
        request = zwlr_foreign_toplevel_handle_v1_unset_minimized;
    else if (strcmp(argv[2], "set_maximized") == 0)
        request = zwlr_foreign_toplevel_handle_v1_set_maximized;
    else if (strcmp(argv[2], "unset_maximized") == 0)
        request = zwlr_foreign_toplevel_handle_v1_unset_maximized;
    else {
        fprintf(stderr, "unknown request %s\n", argv[2]);
        return 2;
    }
    struct wl_display *display = wl_display_connect(NULL);
    if (!display) {
        fputs("cannot connect to Wayland display\n", stderr);
        return 1;
    }
    wl_list_init(&toplevels);
    struct wl_registry *registry = wl_display_get_registry(display);
    wl_registry_add_listener(registry, &registry_listener, NULL);
    wl_display_roundtrip(display);
    if (!manager) {
        fputs("zwlr_foreign_toplevel_manager_v1 is unavailable\n", stderr);
        return 1;
    }
    zwlr_foreign_toplevel_manager_v1_add_listener(manager, &manager_listener, NULL);
    // The first roundtrip delivers the handles, the second their app_id events.
    wl_display_roundtrip(display);
    wl_display_roundtrip(display);

    int matched = 0;
    struct toplevel *toplevel;
    wl_list_for_each(toplevel, &toplevels, link) {
        if (toplevel->app_id && strcmp(toplevel->app_id, argv[1]) == 0) {
            request(toplevel->handle);
            matched++;
        }
    }
    if (matched != 1) {
        fprintf(stderr, "expected one toplevel with app_id %s, found %d\n", argv[1], matched);
        return 1;
    }
    // The compositor has handled the request once this roundtrip returns.
    if (wl_display_roundtrip(display) < 0) {
        fputs("compositor disconnected after the request\n", stderr);
        return 1;
    }
    wl_display_disconnect(display);
    return 0;
}
