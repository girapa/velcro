# API tree

Every public attribute and method developers use to customise velcro. Names
exported from the top-level `velcro` package are marked; everything under
`CRUDView` is an attribute you set or a method you override. The field renderers
live in `velcro.renderers`.

For default values see [Defaults](defaults.md); for how each area behaves see
the [guides](../index.md#guides).

```text
velcro  (top-level exports)
├── CRUDView
│   ├── Core configuration
│   │   ├── model
│   │   ├── fields                      / {action}_fields
│   │   ├── queryset
│   │   ├── form_class                  / {action}_form_class
│   │   ├── template_name               / {action}_template_name
│   │   ├── success_url                 / {action}_success_url
│   │   ├── context_object_name
│   │   └── extra_actions
│   │
│   ├── URL configuration
│   │   ├── url_base                    (classproperty)
│   │   ├── url_name_prefix             (classproperty)
│   │   ├── url_namespace
│   │   ├── lookup_field
│   │   ├── lookup_url_kwarg
│   │   ├── path_converter
│   │   ├── get_urls()                  (classmethod)
│   │   ├── reverse()
│   │   └── maybe_reverse()
│   │
│   ├── Querysets and objects
│   │   ├── get_queryset()
│   │   └── get_object()
│   │
│   ├── Fields
│   │   └── get_fields()
│   │
│   ├── Forms
│   │   ├── get_form_class()
│   │   ├── get_form()
│   │   ├── form_valid()
│   │   └── form_invalid()
│   │
│   ├── Search / order / filter
│   │   ├── search_fields               / {action}_search_fields
│   │   ├── search_param
│   │   ├── ordering_fields             / {action}_ordering_fields
│   │   ├── ordering_param
│   │   ├── filterset_class             / {action}_filterset_class
│   │   ├── filterset_fields            / {action}_filterset_fields
│   │   ├── get_search_query()
│   │   ├── apply_search()
│   │   ├── get_current_ordering()
│   │   ├── apply_ordering()
│   │   ├── get_filterset_class()
│   │   └── get_filterset()
│   │
│   ├── Templates and context
│   │   ├── template_dir
│   │   ├── template_name_suffix
│   │   ├── base_template_name
│   │   ├── get_template_names()
│   │   ├── get_context_data()
│   │   ├── get_{action}_context_data() (per-action hook)
│   │   ├── get_context_object_name()
│   │   └── render_to_response()
│   │
│   ├── Pagination
│   │   ├── paginate_by                 / {action}_paginate_by
│   │   ├── page_kwarg
│   │   ├── allow_empty
│   │   ├── get_paginate_by()
│   │   ├── get_paginator()
│   │   └── paginate_queryset()
│   │
│   ├── Access control
│   │   ├── login_required
│   │   ├── permissions
│   │   ├── dispatch()
│   │   ├── get_required_permission()
│   │   └── has_permission()
│   │
│   ├── Messages and redirects
│   │   ├── success_message             / {action}_success_message
│   │   ├── redirect_param
│   │   ├── DEFAULT_MESSAGE_VERBS
│   │   ├── get_success_message()
│   │   ├── send_success_message()
│   │   └── get_success_url()
│   │
│   ├── HTMX
│   │   ├── htmx_partials
│   │   ├── htmx_events
│   │   ├── is_htmx                     (property)
│   │   ├── get_htmx_partial()
│   │   ├── get_htmx_event_name()
│   │   └── htmx_success_response()
│   │
│   ├── Actions
│   │   ├── get_actions()               (classmethod)
│   │   └── as_view()                   (classmethod)
│   │
│   └── Action handlers (bound per request via as_view)
│       ├── list()                      (get: list)
│       ├── detail()                    (get: detail)
│       ├── show_form()                 (get: create, update)
│       ├── process_form()              (post: create, update)
│       ├── confirm_delete()            (get: delete)
│       └── process_deletion()          (post: delete)
│
├── Action  (export)
│   ├── name
│   ├── handlers
│   ├── url_pattern
│   ├── detail
│   ├── template_suffix
│   ├── permission
│   └── using()
│
├── action()  (export — the @action decorator)
│
├── Built-in actions  (exports)
│   ├── LIST
│   ├── CREATE
│   ├── DETAIL
│   ├── UPDATE
│   ├── DELETE
│   └── DEFAULT_ACTIONS
│
├── LOOKUP  (export — URL placeholder constant "{lookup}")
├── __version__  (export)
│
└── velcro.renderers
    ├── EMPTY_VALUE                      ("—")
    ├── Cell
    ├── Row
    ├── field_label()
    ├── format_value()
    ├── related_detail_url()
    ├── resolve_cell()
    ├── build_headers()
    └── build_rows()
```