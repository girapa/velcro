# Velcro documentation

Velcro provides CRUD views for Django.

It gives you the usual list, create, detail, update, and delete views from a
single class, while still allowing real-world custom behaviour through actions,
queryset hooks, forms, permissions, templates, search, ordering, filtering, and
HTMX partials.

Velcro requires **Python 3.14+** and **Django 6.0+**, and ships with zero hard
dependencies beyond Django.

## Start here

- [Installation](installation.md)
- [Quickstart](quickstart.md)
- [Core concepts](concepts.md)
- [CRM example domain](crm-example.md)

All examples in these docs are built around a small CRM domain (leads,
accounts, contacts, deals, activities). The models are defined once in the
[CRM example](crm-example.md) and reused throughout.

## Customisation

- [Customisation overview](customisations/overview.md) — the map of every
  customisation point
- [Custom actions](customisations/custom-actions.md) — go beyond the five
  built-in CRUD operations
- [Templates](customisations/templates.md) — override markup, blocks, and
  partials
- [Access control](customisations/access-control.md) — login, model and
  object-level permissions

## Guides

Each guide covers one area: **what** you can customise, **how**, the
**default**, and the **outcome**.

- [Querysets and object lookup](guides/querysets.md)
- [Fields and value rendering](guides/fields-and-rendering.md)
- [Forms](guides/forms.md)
- [Search, ordering, filtering](guides/search-ordering-filtering.md)
- [Pagination](guides/pagination.md)
- [URLs and namespaces](guides/urls-and-namespaces.md)
- [Messages and redirects](guides/messages-and-redirects.md)
- [Context hooks](guides/context-hooks.md)
- [HTMX](guides/htmx.md)

## Reference

- [API tree](references/api-tree.md) — every public attribute and method
- [Defaults](references/defaults.md) — every default value and its outcome