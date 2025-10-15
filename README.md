# Guard

> https://api.innohassle.ru/guard/v0

## Table of contents

Did you know that GitHub supports table of
contents [by default](https://github.blog/changelog/2021-04-13-table-of-contents-support-in-markdown-files/) 🤔

## About

### Project Goal

Guard is a backend service that adds users to Google Spreadsheets only after they authenticate via InNoHassle Accounts. It ensures that only verified Innopolis University community members can access shared spreadsheets.

### Project Description

Guard API is a FastAPI-based service that:
- **Gates access to Google Spreadsheets** - users must authenticate via InNoHassle Accounts to be added
- Provides automated spreadsheet setup with role-based access control (writer/reader)
- Generates secure join links for spreadsheet access
- Uses Google Service Accounts to manage spreadsheet permissions
- Offers admin interface for configuring spreadsheet integrations

**How it works:**
1. Admin sets up a spreadsheet through Guard and selects a role (writer/reader)
2. Admin shares a join link with users
3. Users authenticate via InNoHassle Accounts
4. Guard adds authenticated users to the spreadsheet with the configured role

### Technologies

- [Python 3.14](https://www.python.org/downloads/) & [uv](https://docs.astral.sh/uv/)
- [FastAPI](https://fastapi.tiangolo.com/)
- [Google Sheets API](https://developers.google.com/sheets/api) - Spreadsheet integration
- [Google Drive API](https://developers.google.com/drive) - File permissions management
- InNoHassle Accounts SDK - Authentication
- Formatting and linting: [Ruff](https://docs.astral.sh/ruff/), [pre-commit](https://pre-commit.com/)
- Deployment: [Docker](https://www.docker.com/), [Docker Compose](https://docs.docker.com/compose/),
  [GitHub Actions](https://github.com/features/actions)

## How to use?

**For Admins:**
1. Visit the setup interface at `/google`
2. Add the Guard service account to your Google Spreadsheet as an editor
3. Setup the spreadsheet in Guard and choose a role (writer/reader) for users
4. Share the generated join link with your users

**For Users:**
1. Receive a join link from the admin
2. Click the link and authenticate via InNoHassle Accounts
3. Enter your Gmail address
4. Guard automatically adds you to the spreadsheet with the configured permissions

This ensures only authenticated Innopolis University community members can access the spreadsheet.

## Development

### Set up for development

1. Install [uv](https://docs.astral.sh/uv/) and [Docker](https://docs.docker.com/engine/install/)
2. Install dependencies:
   ```bash
   uv sync
   ```
3. Copy settings.example.yaml to settings.yaml and configure:
   ```bash
   cp settings.example.yaml settings.yaml
   ```
4. Place your Google Service Account JSON file in the project root (default name: `inh-plugin.json`)
5. Start development server:
   ```bash
   uv run -m src.api --reload
   ```
   > Follow the provided instructions (if needed).
4. Open in the browser: http://localhost:8013
   > The api will be reloaded when you edit the code

> [!IMPORTANT]
> For endpoints requiring authorization click "Authorize" button in Swagger UI

> [!TIP]
> Edit `settings.yaml` according to your needs, you can view schema in
> [config_schema.py](src/config_schema.py) and in [settings.schema.yaml](settings.schema.yaml)

**Set up PyCharm integrations**

1. Run configurations ([docs](https://www.jetbrains.com/help/pycharm/run-debug-configuration.html#createExplicitly)).
   Right-click the `__main__.py` file in the project explorer, select `Run '__main__'` from the context menu.
2. Ruff ([plugin](https://plugins.jetbrains.com/plugin/20574-ruff)).
   It will lint and format your code. Make sure to enable `Use ruff format` option in plugin settings.
3. Pydantic ([plugin](https://plugins.jetbrains.com/plugin/12861-pydantic)). It will fix PyCharm issues with
   type-hinting.
4. Conventional commits ([plugin](https://plugins.jetbrains.com/plugin/13389-conventional-commit)). It will help you
   to write [conventional commits](https://www.conventionalcommits.org/en/v1.0.0/).

### Deployment
We use Docker with Docker Compose plugin to run the service on servers.

1. Copy the file with environment variables: `cp .example.env .env`
2. Change environment variables in the `.env` file
3. Copy the file with settings: `cp settings.example.yaml settings.yaml`
4. Change settings in the `settings.yaml` file according to your needs
   (check [settings.schema.yaml](settings.schema.yaml) for more info)
5. Place your Google Service Account JSON file in the project root (default name: `inh-plugin.json`)
6. Install Docker with Docker Compose
7. Run the containers: `docker compose up --build --wait`
8. Check the logs: `docker compose logs -f`

## FAQ

### Be up to date with the template!

Check https://github.com/one-zero-eight/fastapi-template for updates once in a while.

### How to update dependencies

1. Run `uv sync --upgrade` to update uv.lock file and install the latest versions of the dependencies.
2. Run `uv tree --outdated --depth=1` will show what package versions are installed and what are the latest versions.
3. Run `uv run pre-commit autoupdate`

Also, Dependabot will help you to keep your dependencies up-to-date, see [dependabot.yaml](.github/dependabot.yaml).
{% if cookiecutter.database == "mongo" %}
### How to dump the database

1. Dump:
   ```bash
   docker compose exec db sh -c 'mongodump "mongodb://$MONGO_INITDB_ROOT_USERNAME:$MONGO_INITDB_ROOT_PASSWORD@127.0.0.1:27017/db?authSource=admin" --db=db --out=dump/'
   ```
2. Restore:
   ```bash
   docker compose exec db sh -c 'mongorestore "mongodb://$MONGO_INITDB_ROOT_USERNAME:$MONGO_INITDB_ROOT_PASSWORD@127.0.0.1:27017/db?authSource=admin" --drop /dump/db'
   ```
{% endif %}

## Contributing

We are open to contributions of any kind.
You can help us with code, bugs, design, documentation, media, new ideas, etc.
If you are interested in contributing, please read
our [contribution guide](https://github.com/one-zero-eight/.github/blob/main/CONTRIBUTING.md).
