
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs
from pathlib import Path
from html import escape
from datetime import date
from decimal import Decimal, InvalidOperation
import json
import uuid

BASE_DIR = Path(__file__).parent
DATA_FILE = BASE_DIR / "transactions.json"


def load_data():
    if DATA_FILE.exists():
        try:
            return json.loads(DATA_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []
    return []


def save_data(transactions):
    DATA_FILE.write_text(
        json.dumps(transactions, indent=2),
        encoding="utf-8"
    )


class ExpenseTracker(BaseHTTPRequestHandler):

    def send_content(self, content, content_type="text/html; charset=utf-8",
                     status=200):
        data = content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/style.css":
            css = (BASE_DIR / "style.css").read_text(encoding="utf-8")
            self.send_content(css, "text/css; charset=utf-8")
            return

        if self.path != "/":
            self.send_content("Page not found", status=404)
            return

        transactions = load_data()

        income = sum(
            (Decimal(t["amount"]) for t in transactions
             if t["kind"] == "income"),
            Decimal("0")
        )

        expenses = sum(
            (Decimal(t["amount"]) for t in transactions
             if t["kind"] == "expense"),
            Decimal("0")
        )

        balance = income - expenses

        rows = ""

        for t in reversed(transactions):
            kind = escape(t["kind"])
            sign = "+" if kind == "income" else "-"

            rows += f"""
            <tr>
                <td>{escape(t["description"])}</td>
                <td>{escape(t["category"])}</td>
                <td>{escape(t["date"])}</td>
                <td class="{kind}">
                    {sign}₹{Decimal(t["amount"]):.2f}
                </td>
                <td>
                    <form action="/delete" method="POST">
                        <input type="hidden" name="id"
                               value="{escape(t['id'])}">
                        <button class="delete-btn" type="submit">
                            Delete
                        </button>
                    </form>
                </td>
            </tr>
            """

        if not rows:
            rows = """
            <tr>
                <td colspan="5" class="empty">
                    No transactions yet. Add your first one!
                </td>
            </tr>
            """

        template = (BASE_DIR / "index.html").read_text(encoding="utf-8")

        page = (
            template.replace("{{BALANCE}}", f"{balance:.2f}")
            .replace("{{INCOME}}", f"{income:.2f}")
            .replace("{{EXPENSES}}", f"{expenses:.2f}")
            .replace("{{TRANSACTIONS}}", rows)
        )

        self.send_content(page)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8")
        form = parse_qs(body)
        transactions = load_data()

        if self.path == "/add":
            description = form.get("description", [""])[0].strip()
            amount_text = form.get("amount", [""])[0].strip()
            kind = form.get("kind", ["expense"])[0]
            category = form.get("category", ["Other"])[0]
            transaction_date = form.get("date", [str(date.today())])[0]

            try:
                amount = Decimal(amount_text)
                if not amount.is_finite() or amount <= 0:
                    raise InvalidOperation
            except InvalidOperation:
                self.send_content(
                    '<h2>Enter an amount greater than zero.</h2>'
                    '<a href="/">Go back</a>',
                    status=400
                )
                return

            if not description:
                self.send_content(
                    '<h2>Please enter a description.</h2>'
                    '<a href="/">Go back</a>',
                    status=400
                )
                return

            if kind not in ("income", "expense"):
                kind = "expense"

            categories = {
                "Food", "Travel", "Shopping", "Bills",
                "Education", "Salary", "Other"
            }

            if category not in categories:
                category = "Other"

            transactions.append({
                "id": str(uuid.uuid4()),
                "description": description[:100],
                "amount": str(amount.quantize(Decimal("0.01"))),
                "kind": kind,
                "category": category,
                "date": transaction_date
            })

            save_data(transactions)

        elif self.path == "/delete":
            transaction_id = form.get("id", [""])[0]

            transactions = [
                t for t in transactions
                if t["id"] != transaction_id
            ]

            save_data(transactions)

        else:
            self.send_content("Page not found", status=404)
            return

        self.send_response(303)
        self.send_header("Location", "/")
        self.end_headers()


if __name__ == "__main__":
    server = HTTPServer(("127.0.0.1", 8000), ExpenseTracker)

    print("Personal Expense Tracker is running!")
    print("Open http://127.0.0.1:8000 in your browser.")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
        server.server_close()
