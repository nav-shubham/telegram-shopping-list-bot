# 🛒 Telegram Shopping List Bot

A production-ready, lightweight, and fast Telegram bot that allows users to create and manage multiple shopping lists with a fully menu-driven inline keyboard interface. 

---

## ✨ Features

- 👤 **Automated User Management:** Zero login/signup. Uses unique Telegram User IDs to securely segregate user data.
- 📁 **Unlimited Lists & Categorization:** Predefined categories:
  - 🛒 Groceries
  - 🥬 Vegetables
  - 💊 Medical
  - 🏠 Household
  - 🧴 Personal Care
  - 📦 Other
- ⚡ **Multi-Item Paste Parser:** Paste single or multi-line items. The bot's isolated parser automatically extracts name, quantity, and unit.
  - *Example input:*
    ```text
    Tomato 2kg
    Milk 2
    Bread
    ```
  - *Decoded:* `Tomato` (2.0 kg), `Milk` (2.0), `Bread` (1.0).
- 🛍️ **Dedicated Shopping Mode:** Check items off in real-time by clicking buttons. Completed items automatically slide to the bottom.
- 📜 **Archiving & History:** Complete a shopping session to generate a permanent snapshot of the list. The original list is reset for reuse.
- 📱 **Clean Navigation:** Entirely menu-driven using inline keyboards to eliminate keyboard typing.

---

## 🏗️ Project Structure

```text
telegram-shopping-list-bot/
├── .env.example
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── src/
│   ├── __init__.py
│   ├── config.py         # Configuration loading and validation
│   ├── main.py           # Application runner and handler registers
│   ├── database/
│   │   ├── __init__.py
│   │   ├── models.py     # SQLAlchemy ORM declarations
│   │   └── session.py    # Session helper and schema seeding
│   ├── parser/
│   │   ├── __init__.py
│   │   └── parser.py     # Regex item text parser
│   ├── services/
│   │   ├── __init__.py
│   │   └── db_service.py # CRUD & Core business logic
│   └── handlers/
│       ├── __init__.py
│       ├── common.py     # Commands: /start, /help, main menus
│       ├── lists.py      # List CRUD (create, rename, delete)
│       ├── items.py      # Item CRUD (add, edit qty/unit/name)
│       ├── shopping.py   # Shopping checkoffs & completion
│       └── history.py    # Completed session logs
└── tests/                # Test suite
    ├── __init__.py
    ├── test_db.py
    └── test_parser.py
```

---

## 💾 Database Schema

The bot uses a normalized relational database design, mapped declaratively with SQLAlchemy:

```
+------------+        +---------------+        +------------+
|   users    |        |  list_types   |        |   lists    |
+------------+        +---------------+        +------------+
| telegram_id| <----+ | id (PK)       | <----+ | id (PK)    |
| created_at |      | | name (Unique) |        | user_id(FK)|
+------------+      | | emoji         |        | type_id(FK)|
      |             | +---------------+        | name       |
      |             +------------------------+ | created_at |
      |                                        | updated_at |
      v                                        +------------+
+---------------------+                              |
| shopping_histories  | <-------+                    v
+---------------------+         |              +------------+
| id (PK)             |         |              |   items    |
| user_id (FK)        |         |              +------------+
| list_name           |         |              | id (PK)    |
| list_type           |         |              | list_id(FK)|
| list_type_emoji     |         |              | name       |
| completion_date     |         |              | quantity   |
| total_items         |         |              | unit       |
| created_at          |         |              |is_completed|
+---------------------+         |              | created_at |
      |                         |              | updated_at |
      v                         |              +------------+
+---------------------+         |
|shopping_history_items|        |
+---------------------+         |
| id (PK)             |         |
| history_id (FK) ----+---------+
| name                |
| quantity            |
| unit                |
| created_at          |
+---------------------+
```

---

## ⚙️ Configuration

The project is configured using environment variables. Create a `.env` file in the root folder (or copy `.env.example`):

```env
# Telegram Bot Token (obtained from @BotFather)
BOT_TOKEN=your_telegram_bot_token_here

# Database URL (SQLite default, easily upgradable to PostgreSQL)
DATABASE_URL=sqlite:///shopping_list.db

# Logging level (DEBUG, INFO, WARNING, ERROR)
LOG_LEVEL=INFO
```

---

## 🚀 Installation & Local Development

### 1. Setup with `uv` (Recommended)

Make sure you have [uv](https://github.com/astral-sh/uv) installed:

```bash
# Create virtual environment
uv venv

# Install dependencies
uv pip install -r requirements.txt

# Run tests
uv run python -m pytest

# Run the bot locally
uv run python src/main.py
```

### 2. Standard `venv` Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows use: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run tests
python -m pytest

# Run the bot locally
python src/main.py
```

---

## 🐳 Docker Deployment

To run the bot in a production-ready, isolated container:

### Prerequisites
Make sure [Docker](https://www.docker.com/) and [Docker Compose](https://docs.docker.com/compose/) are installed.

### Run with Docker Compose
1. Ensure your `.env` contains a valid `BOT_TOKEN`.
2. Run the command:
   ```bash
   docker-compose up -d
   ```
3. This creates a `./data/` folder in the root path which maps to the container to safely persist the SQLite database.

---

## ☁️ Free Cloud Hosting Deployment (e.g., Render, Koyeb, Railway)

The bot is fully compliant with modern cloud providers. Because it runs on **long-polling** by default, you do not need to configure webhooks or public ports.

### Option A: Koyeb / Render (Using Dockerfile)
1. Push this repository to GitHub.
2. Link your GitHub account to [Koyeb](https://www.koyeb.com/) or [Render](https://render.com/).
3. Create a new **Worker** or **Private Service** (non-web service, as there is no HTTP listener).
4. Select **Docker** as the builder (it will automatically build using the included `Dockerfile`).
5. Add the environment variable `BOT_TOKEN` in the service configuration.
6. Deploy.

### Option B: Railway / Render (Using Python Runtime)
1. Push this repository to GitHub.
2. Link your GitHub account and select your project.
3. Configure start command as `python src/main.py`.
4. Define your environment variables (`BOT_TOKEN`).
5. Deploy.

---

## 💡 Bot Commands & Usage Examples

### Suggested Commands:
- `/start` - Launch the main menu card.
- `/lists` - View and manage your categories and lists.
- `/new` - Immediately prompt for a category and name to create a new list.
- `/use <ListName>` - Quickly jump into a specific list.
- `/shop` - Open shopping mode for the active list.
- `/history` - View past shopping history details.
- `/help` - View usage guide and command reference.

### Usage Example: Auto-Adding Items
1. Send `/start` and click **🛒 My Lists**.
2. Click **➕ Create New List**, choose **🛒 Groceries**, and send `Weekly Shopping`.
3. The bot will open your new list detail view.
4. Copy and paste:
   ```text
   Apple 6pcs
   Rice 5kg
   Milk 2
   Bread
   ```
5. Send the message. The bot automatically decodes the items and appends them to your list.
6. Click **🛍️ Start Shopping** to check off items interactively as you put them in your cart!
