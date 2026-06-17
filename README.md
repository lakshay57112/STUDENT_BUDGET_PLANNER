# Student Budget Planner

A web-based budget tracking application for students. Built with Python Flask,
SQLite, Bootstrap 5, and Chart.js — exactly as specified in the project proposal.

Students can register, set monthly budget limits per category, record daily
income and expenses, and view real-time dashboards and spending reports.

---

## How to Run (3 steps)

You need **Python 3** installed. Check by running `python --version`.

### Step 1 — Open a terminal in this folder

```
cd path\to\student_budget_planner
```

### Step 2 — Install Flask

```
pip install -r requirements.txt
```

### Step 3 — Start the app

```
python app.py
```

Then open your browser to:

```
http://127.0.0.1:5000
```

Register an account, log in, and start tracking. Press `CTRL+C` in the
terminal to stop the server.

> The database file `budget_planner.db` is created automatically the first
> time you run the app. Your data is saved between runs.

---

## Features (mapped to the proposal's Functional Requirements)

| ID    | Feature             | Where it lives                          |
|-------|---------------------|-----------------------------------------|
| FR-01 | User Registration   | `/register`                             |
| FR-02 | User Login          | `/login`                                |
| FR-03 | Budget Creation     | `/budget` (set a limit per category)    |
| FR-04 | Expense Recording   | `/expenses` → Add button                |
| FR-05 | Expense Modification| `/expenses` → pencil icon               |
| FR-06 | Expense Deletion    | `/expenses` → trash icon                |
| FR-07 | Dashboard View      | `/dashboard` (cards + weekly chart)     |
| FR-08 | Report Generation   | `/reports` (donut chart + breakdown)    |
| FR-09 | User Logout         | top-right menu → Log out                |

Passwords are stored as secure hashes, never in plain text (NFR-02). Each
user only sees their own data.

---

## Project Structure

```
student_budget_planner/
├── app.py                  # All backend logic: routes, database, auth
├── requirements.txt        # Python dependencies (Flask)
├── budget_planner.db       # SQLite database (auto-created on first run)
├── README.md               # This file
├── templates/              # HTML pages (Jinja2 + Bootstrap)
│   ├── base.html           # Shared layout: navbar, flash messages
│   ├── _month_nav.html     # Reusable month switcher
│   ├── register.html       # Sign-up page
│   ├── login.html          # Login page
│   ├── dashboard.html      # Home: balance, weekly chart, recent activity
│   ├── expenses.html       # Transaction list + add/edit/delete modals
│   ├── budget.html         # Budget limits with progress bars
│   └── reports.html        # Category donut chart + breakdown
└── static/
    └── css/
        └── style.css       # Custom minimalist theme
```

## How the Pieces Fit Together

- **`app.py`** is the heart. It defines URL routes (e.g. `/dashboard`), talks
  to the SQLite database, and decides which HTML template to show. Each route
  has comments explaining what it does.
- **Templates** are HTML files with placeholders. Flask fills in the data
  (your transactions, budgets, totals) and sends finished pages to the browser.
  `base.html` holds the shared shell; every other page "extends" it.
- **`style.css`** controls the look. Colors carry meaning: purple = brand,
  teal = income, coral = expense, amber = nearing your limit.
- **Chart.js** draws the charts. The browser asks `/api/chart-data` for the
  numbers (as JSON), then renders the weekly bar chart and category donut.

## Database Tables

- **users** — account details with a hashed password.
- **budgets** — a spending limit for one category in one month.
- **expenses** — each income or expense entry (title, amount, category, date).

---

## How to Extend It

- **Add a category**: edit the `EXPENSE_CATEGORIES` or `INCOME_CATEGORIES`
  lists near the top of `app.py`.
- **Change the colors**: edit the `:root` variables at the top of
  `static/css/style.css`.
- **Add recurring expenses**: add a `recurring` column to the `expenses`
  table and a checkbox in the add form.
- **Export to CSV**: add a route that queries expenses and returns a CSV file.
- **Deploy online**: host on PythonAnywhere, Render, or Railway (all support
  Flask + SQLite for free).
