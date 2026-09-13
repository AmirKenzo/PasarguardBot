# Admin panel

A web admin panel for the bot, served as part of the existing WebApp.

There is no separate panel login, no panel-specific tables for admins or
sessions, and no server-rendered HTML: the panel is a set of JSON endpoints
plus a React area inside `frontend/`.

## How a request is authorised

The panel reuses the WebApp login exactly as it stands — Telegram `initData`,
or a session token obtained through the phone/OTP flow.

```
frontend/src/api/panel/client.ts
    POST /api/panel/...        Authorization: Bearer <session token>
                               X-Session-Token: <session token>
                               X-Telegram-Init-Data: <telegram init data>
        │
        ▼
app/routers/__init__.py        WebAppAuthHeaderMiddleware moves those headers
                               into a ContextVar (AUTH_HEADER_PREFIXES covers
                               both /api/webapp and /api/panel)
        │
        ▼
app/routers/panel/guard.py     run(payload, request, response_model, handler)
        │
        ▼
app/routers/panel/auth.py      authenticate_admin()
                                 1. authenticate_user()  — the WebApp's own check
                                 2. user id must be in ADMIN_ID
                               → PanelActor(user_id, ip)
```

`guard.run` is the only way a panel endpoint runs. It authenticates, and on
failure returns `response_model(ok=False, error=...)` rather than raising, so
an unauthorised caller gets the same envelope as any other error and never a
partial payload. Because of that, **every panel response model must have a
default for every field** — there is a check for this in the repository's
verification scripts.

Adding an endpoint therefore looks like this, and nothing else is needed to
make it admin-only:

```python
@router.post("/panel/things/delete", response_model=ActionResponse)
async def delete_thing(payload: PanelThingRequest, request: Request) -> ActionResponse:
    async def handle(actor: PanelActor) -> ActionResponse:
        ok = await mutations.delete_thing(actor, payload.thing_id)
        if not ok:
            return ActionResponse(ok=False, error="چیزی با این شناسه پیدا نشد.")
        return ActionResponse(message="حذف شد.")

    return await guard.run(payload, request, ActionResponse, handle)
```

## Layout

| Path | What lives there |
| --- | --- |
| `app/panel/queries.py` | Read queries shared by the endpoints |
| `app/panel/mutations.py` | Writes, each taking a `PanelActor` and writing an audit row |
| `app/panel/audit.py` | The audit trail (`record` never raises) |
| `app/panel/forms.py` | Small parsers (premium emoji id, button colour) |
| `app/models/panel/` | Request/response DTOs, one module per feature |
| `app/routers/panel/` | Endpoints, one module per feature |
| `frontend/src/api/panel/` | Typed client, one module per feature |
| `frontend/src/types/panel/` | TypeScript mirrors of the DTOs |
| `frontend/src/features/admin/` | The panel's pages and its shell |

Endpoints are POST-only and all live under `/api/panel`. Request bodies derive
from `PanelRequest`; responses derive from `PanelResponse` (`ok` + `error`),
with `ActionResponse` adding a human-readable `message` that the frontend shows
as a toast.

## Database

One table is added, `panel_audit_logs`, plus three columns on
`keyboard_buttons` (`sort_row`, `sort_order`, `hidden`) for the keyboard layout
editor. Everything else reads and writes the bot's existing tables, so the
panel and the bot can never disagree about the data.

## Reaching it

The panel is the `/panel` route of the WebApp, so it needs no URL or
certificate of its own. The admin keyboard shows a "web panel" button whenever
`WEBAPP_URL` is set; opening it lands on `WEBAPP_URL#/panel`.

A user who is not in `ADMIN_ID` sees a refusal instead of the panel, both from
the API and from the guard in front of the React routes.
