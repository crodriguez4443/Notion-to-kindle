# Notion → Kindle Weekly Sync

Automatically sends your Notion "read later" web clippings to your Kindle every Monday.

## How it works

1. **Queries** your Notion database for pages tagged `read later` that haven't been sent yet
2. **Converts** each page's content to an EPUB file
3. **Emails** each EPUB to your Kindle via Amazon's Send-to-Kindle service
4. **Marks** each page with a `Sent to Kindle` checkbox in Notion so it's never sent twice
5. **Runs automatically** every Monday at 8 AM UTC via GitHub Actions (free)

---

## One-time setup

### 1. Notion — add a property to your database

Open your database in Notion and add a new property:
- **Name:** `Sent to Kindle`
- **Type:** Checkbox

> The filter in `notion_fetcher.py` also expects a `Category` **Select** property with the value `read later`. Adjust the property name/type in `notion_fetcher.py` if yours differs.

### 2. Notion — create an integration

1. Go to [https://www.notion.so/my-integrations](https://www.notion.so/my-integrations)
2. Click **New integration**, give it a name (e.g. "Kindle Sync"), select your workspace
3. Copy the **Internal Integration Token** (`secret_...`)
4. Open your Notion database → click `...` (top right) → **Connections** → add your integration

### 3. Notion — get your Database ID

The database ID is in the URL when you open the database as a full page:

```
https://www.notion.so/yourworkspace/<DATABASE_ID>?v=...
```

Copy the 32-character hex string before the `?`.

### 4. Amazon — approve your Gmail as a sender

1. Go to [Manage Your Content and Devices](https://www.amazon.com/hz/mycd/myx)
2. Click **Preferences** → **Personal Document Settings**
3. Under **Approved Personal Document E-mail List**, click **Add a new approved e-mail address**
4. Enter your Gmail address

Your Kindle email is shown under **Send-to-Kindle E-Mail Settings** on the same page (usually `name@kindle.com`).

### 5. Google — create an App Password

1. Enable 2-Step Verification on your Google account if not already done
2. Go to [https://myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
3. Create a new App Password → select **Mail** + **Other (custom name)**
4. Copy the 16-character password shown (spaces are fine to include)

### 6. GitHub — add repository secrets

In your GitHub repository go to **Settings → Secrets and variables → Actions → New repository secret** and add:

| Secret name          | Value                                      |
|----------------------|--------------------------------------------|
| `NOTION_TOKEN`       | Your Notion integration token (`secret_…`) |
| `NOTION_DATABASE_ID` | Your 32-char database ID                   |
| `GMAIL_USER`         | Your Gmail address                         |
| `GMAIL_APP_PASSWORD` | Your 16-char Google App Password           |
| `KINDLE_EMAIL`       | Your Kindle email (`name@kindle.com`)      |

---

## Testing locally

```bash
# 1. Clone the repo and install dependencies
pip install -r requirements.txt

# 2. Create your .env file
cp .env.example .env
# Edit .env with your real values

# 3. Run the sync
cd src
python main.py
```

## Triggering manually on GitHub

Go to your repo → **Actions** → **Weekly Notion → Kindle Sync** → **Run workflow**.

---

## Customising the Notion filter

If your category property has a different name or type (e.g. `Tags` as a multi-select), edit the filter in `src/notion_fetcher.py`:

```python
# For a multi-select property called "Tags":
{
    "property": "Tags",
    "multi_select": {"contains": "read later"},
}
```

---

## Project structure

```
├── src/
│   ├── main.py              # Entrypoint — orchestrates the sync
│   ├── notion_fetcher.py    # Notion API: query, fetch blocks, mark sent
│   ├── epub_builder.py      # Notion blocks → HTML → EPUB
│   └── kindle_sender.py     # Gmail SMTP → Send-to-Kindle
├── .github/
│   └── workflows/
│       └── weekly_sync.yml  # GitHub Actions cron (every Monday 8am UTC)
├── requirements.txt
├── .env.example
└── .gitignore
```
