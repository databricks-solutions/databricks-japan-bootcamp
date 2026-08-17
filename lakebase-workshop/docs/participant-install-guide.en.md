# Lakebase Workshop App Install Guide

This is the primary configuration for connecting the workshop app through a
Databricks Apps Database resource.

In this workshop, a ticket is a record used to manage a support request, work
item, vulnerability item, or similar operational task. This guide calls the
app service principal Client ID the App ID.

## What This Guide Includes And Excludes

- Creating the Databricks App
- Creating your own branch from the instructor's `production` branch (tables
  and data are copied with the branch)
- Creating the app role on your branch
- Adding your branch as a Database resource
- Deploying the app and connecting it to Lakebase
- Updating a ticket and confirming that only your branch changes

You do not copy a connection string or type `ENDPOINT_NAME` in the standard
flow.

## Install From Databricks UI

1. Open your Databricks workspace.
2. Download or clone this repository, then open the `lakebase-workshop` folder.
3. Go to **Workspace** and upload the contents of `lakebase-workshop` to a
   workspace folder such as:

   `/Workspace/Users/<your-email>/lakebase-workshop-app`

   The folder should directly contain `app.yaml`, `app.py`, `pyproject.toml`,
   and `static/`.

4. Open **Databricks Apps** from the app switcher in the top-right corner.
5. Create a new app. Do not deploy it yet.
6. Note the app service principal Client ID (App ID). You will select the same
   app when creating the role.

## Create Your Branch From Production

1. Open **Lakebase Postgres** from the app switcher.
2. Open the master project assigned by the instructor.
3. Create a new branch from `production`.
4. Use your name for the branch and set Auto-delete to `After 1 day`.
5. Wait for the branch and endpoint to become ready.

## Create The App Role On Your Branch

1. Open **Lakebase Postgres** from the app switcher.
2. Open the branch you created.
3. Select **Roles & Databases** → **Add role**.
4. Select your app service principal.
5. Enable the **superuser privilege option**, then create the role.

Create this role only on your own branch, never on `production`.

## Add The Database Resource

1. Return to your app and select **Resources** → **Add resource**.
2. Select **Database**.
3. Configure:

   | Field | Value |
   |---|---|
   | Resource key | `lakebase-demo` |
   | Project | The master project assigned by the instructor |
   | Branch | Your branch |
   | Database | `databricks_postgres` |
   | Permission | `Can connect and create` |

4. Save the resource.

The resource key must be `lakebase-demo` because `app.yaml` resolves
`ENDPOINT_NAME` from that key.

## Deploy The App

1. Click **Deploy** on the app details page.
2. Select the uploaded workspace folder.

   `/Workspace/Users/<your-email>/lakebase-workshop-app`

3. Click **Select**, then **Deploy**.
4. Open the app and confirm the green status shows:
   - `Lakebase connected`
   - database `databricks_postgres`
   - your branch
   - `Apps resource`
5. Confirm that the five Lakebase tickets are displayed.

## Confirm The Outcome

1. Select one ticket and note its ticket ID.
2. Change its status, set the owner to your name, and save.
3. Open **Lakebase Postgres** → your branch → **Tables** → `tickets`.
4. Confirm that status, owner, and updated_at changed for the ticket ID.
5. Open `production` → **Tables** → `tickets`.
6. Confirm that the same ticket remains unchanged.

Submit these three items through the form or chat specified by the instructor:

- Your branch name
- The updated ticket ID
- `production` unchanged: confirmed

## Manual Connection Fallback

If Database resources are unavailable, make a separate copy of the source
folder and replace `app.yaml` with `app.manual.yaml`. The manual configuration
starts in SQLite demo mode and supports the original two-variable connection
flow. See [the manual connection guide](participant-install-guide.manual.en.md)
for the complete procedure.

```yaml
env:
  - name: LAKEBASE_CONNECTION_STRING
    value: "<Connection details Copy snippet>"
  - name: ENDPOINT_NAME
    value: "projects/<master project>/branches/<your branch>/endpoints/primary"
```

`PGUSER` defaults to the Databricks Apps `DATABRICKS_CLIENT_ID`. Individual
standard `PG*` variables remain supported. Use
`notebooks/participant_connect_helper` for fallback diagnostics.

Troubleshooting:

| Symptom | Check | Recovery |
|---|---|---|
| The app remains in demo mode | Database resource and deployment state | Add the resource and redeploy |
| `password authentication failed` | App role on your branch | Create the role for the App ID |
| `permission denied for table tickets` | Superuser option | Update or recreate the role |
| `valueFrom: lakebase-demo` hint | Resource key | Set the key to `lakebase-demo` and redeploy |

## Next Step

Tell the instructor which route you want to take:

1. Run a proof of concept with your use case
2. Discuss placement across Lakebase, Unity Catalog/Delta, and DBSQL
3. Join a follow-up workshop or advanced session

## Update The App Code

When updating the source code, do not delete the Databricks App or Lakebase.
Replace only the source folder in Workspace, then redeploy the existing App.

1. Open **Workspace** in Databricks.
2. Delete the existing source folder.

   Example:

   `/Workspace/Users/<your-email>/lakebase-workshop-app`

3. Download or clone the latest repository version.
4. Upload the new `lakebase-workshop` contents to the same location and confirm
   that the workspace folder has the same name as before.

   Example:

   `/Workspace/Users/<your-email>/lakebase-workshop-app`

5. Confirm that the folder directly contains `app.yaml`, `app.py`,
   `pyproject.toml`, `static/`, and `sql/`.
6. Open the existing Databricks App.
7. Click **Deploy**, select the same source folder, and redeploy.

You may delete:

- The source folder in Workspace

Do not delete:

- The Databricks App
- The Lakebase project, database, or tables
- The App environment variables

Deleting the Databricks App can change the App service principal. If that
happens, you may need to redo the Lakebase role grant. For normal
updates, keep the App and redeploy it from the refreshed source folder.

## Included Files

- `app.py`: application server
- `app.yaml`: Database resource configuration
- `app.manual.yaml`: manual connection fallback configuration
- `pyproject.toml` and `uv.lock`: pinned Python runtime dependencies
- `static/`: browser UI
- `sql/`: reference schema and seed files for the workshop
- `notebooks/participant_connect_helper.py`: manual connection diagnostic helper

The public source does not include Lakebase creation, setup, cleanup, or
workspace-specific deployment scripts.
