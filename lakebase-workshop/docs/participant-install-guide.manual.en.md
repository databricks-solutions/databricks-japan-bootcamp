# Lakebase Workshop App Install Guide (Manual Connection)

This configuration is the fallback for workspaces where a Databricks Apps Database
resource is unavailable. It supports the original two-variable flow and
individual standard `PG*` variables.

In this workshop, a ticket is a support request, work item, vulnerability
item, or similar operational record. This guide calls the service principal
Client ID the App ID.

## Initial Deployment

1. Make a separate copy of the `lakebase-workshop` source folder and replace
   `app.yaml` in that copy with `app.manual.yaml`.
2. Upload the copied folder containing the replaced `app.yaml` to Workspace.
3. Create a Databricks App.
4. Click **Deploy** and select the uploaded folder.
5. Open the app and confirm the yellow demo status and three `[DEMO]` tickets.
6. Note the app service principal Client ID (App ID).

## Branch And Role

1. Create your branch from `production` in the master project assigned by the
   instructor, and set Auto-delete to `After 1 day`.
2. On your branch, select **Roles & Databases** → **Add role**.
3. Select the app service principal.
4. Enable the superuser privilege option and create the role.

Create the role only on your own branch, never on `production`.

## Manual Connection

Set these values in the Apps Environment UI or `app.yaml`, then redeploy:

```yaml
env:
  - name: LAKEBASE_CONNECTION_STRING
    value: "<the Copy snippet from your branch Connection details>"
  - name: ENDPOINT_NAME
    value: "projects/<master project>/branches/<your branch>/endpoints/primary"
```

`PGUSER` defaults to the Databricks Apps `DATABRICKS_CLIENT_ID`. You can also
verify the values with `notebooks/participant_connect_helper.py`.

After redeployment, confirm the green connection status,
`databricks_postgres`, your branch, and the five Lakebase tickets.

## Confirm The Outcome

1. Update one ticket and note its ticket ID.
2. Confirm the update in `tickets` on your branch.
3. Confirm that the same ticket remains unchanged on `production`.
4. Submit your branch name, ticket ID, and `production` confirmation through
   the form or chat specified by the instructor.

## Compatibility

You can replace `LAKEBASE_CONNECTION_STRING` with individual `PGHOST`,
`PGDATABASE`, `PGPORT`, `PGSSLMODE`, and `PGUSER` variables.

Troubleshooting:

| Symptom | Check | Recovery |
|---|---|---|
| `password authentication failed` | App role | Create the App ID role on your branch |
| `permission denied for table tickets` | Superuser option | Update or recreate the role |
| The app remains in demo mode | `LAKEBASE_CONNECTION_STRING` | Set the value and redeploy |

## Next Step

Tell the instructor whether you want a proof of concept, an architecture
consultation, or a follow-up workshop.
