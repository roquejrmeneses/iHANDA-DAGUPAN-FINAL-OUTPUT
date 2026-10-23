"""
iHANDA Dagupan - ADMIN application (separate program from the user app).

    python ihanda_admin.py

Only accounts with role = 'admin' can sign in. Create the first one with
    python setup_admin.py
"""

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
import os

import database
from ihanda_common import *
from database import (
    find_report, filter_reports, get_all_reports, update_report,
    reopen_report, dispatch_report, get_evacuation_areas,
    add_evacuation_area, update_evacuation_area, delete_evacuation_area
)


# =========================================================
# ADMIN APP (own window, own entry point)
# =========================================================

class AdminApp(tk.Tk):

    def __init__(self):
        super().__init__()

        self.title("iHANDA Dagupan - Administrator")
        self.option_add("*TCombobox*Listbox.font", ("Arial", 12))
        self.geometry("1200x740")
        self.minsize(1100, 620)
        self.configure(bg=BACKGROUND)

        style = ttk.Style()
        style.configure("Treeview", rowheight=30, font=("Arial", 10))
        style.configure("Treeview.Heading", font=("Arial", 10, "bold"))

        self.current_frame = None
        self.current_admin = None
        self.frames = {}

        container = tk.Frame(self, bg=BACKGROUND)
        container.pack(fill="both", expand=True)

        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        self.container = container

        login = AdminLoginScreen(container, self)
        self.frames["AdminLoginScreen"] = login
        login.grid(row=0, column=0, sticky="nsew")

        self.bind_all("<MouseWheel>", self.global_scroll)

        self.show_frame("AdminLoginScreen")

    def open_dashboard(self, user):
        """Called by the login screen after a verified admin sign-in."""
        database.start_admin_session(user)
        self.current_admin = user

        old = self.frames.pop("AdminScreen", None)
        if old is not None:
            old.destroy()

        screen = AdminScreen(self.container, self)
        self.frames["AdminScreen"] = screen
        screen.grid(row=0, column=0, sticky="nsew")

        self.show_frame("AdminScreen")

    def logout_admin(self):
        database.end_admin_session()
        self.current_admin = None

        for child in self.winfo_children():
            if isinstance(child, tk.Toplevel):
                child.destroy()

        screen = self.frames.pop("AdminScreen", None)

        self.frames["AdminLoginScreen"].pending = (
            "You have been logged out successfully.", "success"
        )
        self.show_frame("AdminLoginScreen")

        if screen is not None:
            screen.destroy()

    def show_frame(self, page_name):
        # The dashboard is protected: no valid admin session -> login screen.
        if page_name == "AdminScreen" and not database.admin_session_valid():
            page_name = "AdminLoginScreen"

        frame = self.frames[page_name]
        self.current_frame = frame
        frame.tkraise()

        if hasattr(frame, "reset_scroll"):
            frame.reset_scroll()

        if hasattr(frame, "on_show"):
            frame.on_show()

        if page_name == "AdminScreen":
            frame.refresh()

    def global_scroll(self, event):
        # Ignore scrolling inside pop-up windows / dropdown lists
        try:
            if event.widget.winfo_toplevel() is not self:
                return
        except Exception:
            pass

        if self.current_frame and hasattr(
            self.current_frame, "mouse_scroll"
        ):
            self.current_frame.mouse_scroll(event)


# =========================================================
# ADMIN LOGIN  (same blue/red layout as the user login)
# =========================================================

class AdminLoginScreen(tk.Frame):

    def __init__(self, parent, controller):
        super().__init__(parent, bg=WHITE)

        self.controller = controller
        self.pending = None

        form = build_auth_shell(
            self,
            "iHANDA ADMIN OPERATIONS CENTER",
            "Authorized administrators only. Review emergency reports, "
            "assign response teams, and manage evacuation areas for "
            "Dagupan City.",
            [
                "Review and verify emergency reports",
                "Assign organizations and track progress",
                "Manage evacuation areas"
            ],
            badge="ADMINISTRATOR ACCESS"
        )

        tk.Label(
            form, text="Administrator login", font=("Arial", 22, "bold"),
            bg=WHITE, fg=BLUE, anchor="w"
        ).pack(fill="x")

        tk.Label(
            form,
            text="⚠ Restricted area. Sign in with an administrator account.",
            font=("Arial", 11, "bold"), bg=WHITE, fg=RED, anchor="w"
        ).pack(fill="x", pady=(2, 12))

        self.message = MessageBar(form)

        box, self.identifier = auth_field(form, "Admin Username or Email")
        box.pack(fill="x", pady=(0, 12))

        box, self.password = auth_field(form, "Password", show="•")
        box.pack(fill="x")

        password_toggle(form, [self.password]).pack(anchor="w", pady=(6, 14))

        primary_button(form, "LOGIN", self.login, bg=RED).pack(fill="x")

        tk.Label(
            form, text="Need access? Contact the system administrator.",
            font=("Arial", 10), bg=WHITE, fg=GRAY
        ).pack(pady=(16, 0))

        self.identifier.bind("<Return>", lambda e: self.login())
        self.password.bind("<Return>", lambda e: self.login())

    def on_show(self):
        self.password.delete(0, "end")
        self.message.clear()

        if self.pending:
            notice, kind = self.pending
            self.pending = None
            self.message.show(notice, kind)

        self.identifier.focus_set()

    def login(self):
        user, error = database.authenticate(
            self.identifier.get(), self.password.get(), "admin"
        )

        if user is None:
            self.password.delete(0, "end")
            self.message.show(error)
            return

        self.identifier.delete(0, "end")
        self.password.delete(0, "end")
        self.message.clear()

        self.controller.open_dashboard(user)


# =========================================================
# ADMIN SCREEN
# Own layout and own navigation. Design follows the original
# admin dashboard (stat cards, report cards, search + filters,
# detail window). Every data change goes through database.py,
# which re-checks the admin session each time.
# =========================================================

class AdminScreen(ScrollPage):

    SECTIONS = [
        ("dashboard", "Dashboard", "▦"),
        ("active", "Active Reports", "⚠"),
        ("archive", "Response Archive", "✔"),
        ("evacuation", "Evacuation Area Management", "⌂")
    ]

    TITLES = {
        "dashboard": (
            "Administrator Dashboard",
            "Review reports, assign response teams, and track emergency "
            "response progress."
        ),
        "active": (
            "Active Reports",
            "Reports awaiting verification, response, or completion. Open a "
            "report to review details, assign an organization, update the "
            "status, add notes, or run the dispatch simulation."
        ),
        "archive": (
            "Response Archive",
            "Completed emergency responses. Records are kept and can be "
            "reopened if needed."
        ),
        "evacuation": (
            "Evacuation Area Management",
            "Add, edit, or delete the evacuation areas shown to users on the "
            "public Evacuation page."
        )
    }

    def __init__(self, parent, controller):
        super().__init__(parent, bg=BACKGROUND)

        self.controller = controller
        self.admin_section = "dashboard"
        self.saved_filters = {}
        self.nav_buttons = {}

        self.build_sidebar()

        main = tk.Frame(self, bg=BACKGROUND)
        main.pack(side="left", fill="both", expand=True)

        self.build_header(main)
        create_footer(main)
        self.setup_scroll(main)

    # -----------------------------------------------------
    # Sidebar, header, session protection
    # -----------------------------------------------------

    def build_sidebar(self):
        side = tk.Frame(self, bg=DARK_BLUE, width=250)
        side.pack(side="left", fill="y")
        side.pack_propagate(False)

        brand = tk.Frame(side, bg=DARK_BLUE, padx=18, pady=18)
        brand.pack(fill="x")

        tk.Label(
            brand, text="iHANDA", font=("Arial", 24, "bold"),
            bg=DARK_BLUE, fg=WHITE
        ).pack(anchor="w")

        tk.Label(
            brand, text="Admin Operations Center", font=("Arial", 10),
            bg=DARK_BLUE, fg=LIGHT_BLUE
        ).pack(anchor="w")

        tk.Frame(side, height=1, bg=BLUE).pack(fill="x", padx=14, pady=(0, 10))

        for key, label, icon in self.SECTIONS:
            button = tk.Button(
                side,
                text=f"  {icon}   {label}",
                command=lambda k=key: self.show_section(k),
                font=("Arial", 11, "bold"),
                anchor="w",
                justify="left",
                wraplength=190,
                relief="flat",
                bd=0,
                padx=12,
                pady=12,
                cursor="hand2"
            )
            button.pack(fill="x", padx=10, pady=3)
            self.nav_buttons[key] = button

        bottom = tk.Frame(side, bg=DARK_BLUE, padx=14, pady=14)
        bottom.pack(side="bottom", fill="x")

        admin_name = (self.controller.current_admin or {}).get("username", "")

        tk.Label(
            bottom, text="●  Signed in as " + admin_name,
            font=("Arial", 9), bg=DARK_BLUE, fg=LIGHT_BLUE,
            wraplength=200, justify="left"
        ).pack(anchor="w", pady=(0, 8))

        make_button(bottom, "LOGOUT", self.logout, bg=RED).pack(fill="x")

    def build_header(self, main):
        head = tk.Frame(
            main, bg=WHITE, highlightbackground=BORDER, highlightthickness=1
        )
        head.pack(fill="x")

        self.header_title = tk.Label(
            head, text="", font=("Arial", 18, "bold"), bg=WHITE, fg=BLUE
        )
        self.header_title.pack(side="left", padx=24, pady=14)

        tk.Label(
            head,
            text="SIMULATION MODE  •  no real agency is contacted",
            font=("Arial", 9, "bold"), bg=LIGHT_BLUE, fg=BLUE,
            padx=10, pady=4
        ).pack(side="right", padx=20)

    def update_nav(self):
        active = len(filter_reports("active"))

        for key, label, icon in self.SECTIONS:
            button = self.nav_buttons[key]
            selected = key == self.admin_section
            text = f"  {icon}   {label}"

            if key == "active" and active:
                text += f"  ({active})"

            button.config(
                text=text,
                bg=WHITE if selected else DARK_BLUE,
                fg=DARK_BLUE if selected else WHITE,
                activebackground=WHITE if selected else BLUE,
                activeforeground=DARK_BLUE if selected else WHITE
            )

    def guard(self):
        """True if a valid admin session exists; otherwise go to login."""
        if database.admin_session_valid():
            return True

        clear_frame(self.content)
        self.controller.show_frame("AdminLoginScreen")
        return False

    def run_protected(self, func, *args):
        """Run a service function; handle an expired admin session."""
        try:
            return func(*args)
        except PermissionError as error:
            messagebox.showerror("Access Denied", str(error))
            self.guard()
            return None, ""

    def show_section(self, section):
        if not self.guard():
            return

        self.admin_section = section
        self.build()

    def refresh(self):
        if not self.guard():
            return

        self.build()

    def after_change(self):
        """Redraw the current section after data changed (keeps scroll)."""
        if database.admin_session_valid():
            self.build(keep_scroll=True)

    def logout(self):
        if not messagebox.askyesno(
            "Log Out", "Are you sure you want to log out?"
        ):
            return

        self.controller.logout_admin()     # destroys this screen

    # -----------------------------------------------------
    # Page builder
    # -----------------------------------------------------

    def build(self, keep_scroll=False):
        position = self.canvas.yview()[0] if keep_scroll else 0

        clear_frame(self.content)
        self.update_nav()

        title, subtitle = self.TITLES[self.admin_section]
        self.header_title.config(text=title)

        sub = tk.Label(
            self.content, text=subtitle, font=("Arial", 11),
            bg=BACKGROUND, fg=GRAY, justify="left", anchor="w"
        )
        sub.pack(fill="x", pady=(0, 12))
        wrap_to_width(sub, 1000)

        if self.admin_section == "dashboard":
            self.create_dashboard()
        elif self.admin_section == "evacuation":
            self.create_evacuation_section()
        else:
            self.create_reports_section(self.admin_section)

        self.after_idle(self.update_scroll_region)

        if keep_scroll and position:
            self.after(60, lambda: self.canvas.yview_moveto(position))

    # -----------------------------------------------------
    # DASHBOARD
    # -----------------------------------------------------

    def create_dashboard(self):
        all_reports = get_all_reports()

        counts = {s: 0 for s in REPORT_STATUSES}
        for r in all_reports:
            counts[r["status"]] += 1

        active = filter_reports("active")

        stats = tk.Frame(self.content, bg=BACKGROUND)
        stats.pack(fill="x", pady=(0, 10))

        cards = [
            ("Total Reports", len(all_reports), BLUE, "▦"),
            ("Active Reports", len(active), BLUE, "⚠"),
            ("Pending Reports", counts["Pending"], RED, "!"),
            ("In Progress", counts["In Progress"], ORANGE, "↻"),
            ("Resolved Reports", counts["Resolved"], GREEN, "✔")
        ]

        for i, (title, value, color, icon) in enumerate(cards):
            stats.grid_columnconfigure(i, weight=1, uniform="stat")

            card = make_card(stats, padx=14, pady=12)
            card.grid(
                row=0, column=i, sticky="nsew",
                padx=(0 if i == 0 else 5, 0 if i == len(cards) - 1 else 5)
            )

            icon_tile(card, icon, color, size=36).pack(anchor="w")

            tk.Label(
                card, text=str(value), font=("Arial", 26, "bold"),
                bg=WHITE, fg=color
            ).pack(anchor="w", pady=(4, 0))

            tk.Label(
                card, text=title, font=("Arial", 10, "bold"),
                bg=WHITE, fg=GRAY
            ).pack(anchor="w")

        actions = tk.Frame(self.content, bg=BACKGROUND)
        actions.pack(fill="x", pady=(0, 10))

        make_button(
            actions, "OPEN ACTIVE REPORTS",
            lambda: self.show_section("active"), bg=RED
        ).pack(side="left")

        make_button(
            actions, "RESPONSE ARCHIVE",
            lambda: self.show_section("archive"), bg=BLUE
        ).pack(side="left", padx=8)

        # two columns: reports needing attention | recent activity
        columns = tk.Frame(self.content, bg=BACKGROUND)
        columns.pack(fill="x")
        columns.grid_columnconfigure(0, weight=3, uniform="dash")
        columns.grid_columnconfigure(1, weight=2, uniform="dash")

        left = make_card(columns, padx=16, pady=14)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 6))

        tk.Label(
            left, text="Reports Needing Attention", font=FONT_SECTION,
            bg=WHITE, fg=BLUE
        ).pack(anchor="w", pady=(0, 8))

        if not active:
            tk.Label(
                left, text="No active reports right now.",
                font=("Arial", 11), bg=WHITE, fg=GRAY
            ).pack(anchor="w")

        for report in active[:5]:
            row = tk.Frame(left, bg=LIGHT_BLUE, padx=12, pady=10)
            row.pack(fill="x", pady=4)

            make_button(
                row, "VIEW / UPDATE",
                lambda r=report["report_id"]: self.edit_report(r), bg=BLUE
            ).pack(side="right", padx=(8, 0))

            info = tk.Frame(row, bg=LIGHT_BLUE)
            info.pack(side="left", fill="x", expand=True)

            head = tk.Frame(info, bg=LIGHT_BLUE)
            head.pack(fill="x")

            tk.Label(
                head,
                text=f"{report['report_id']}  |  {report['emergency']}",
                font=("Arial", 11, "bold"), bg=LIGHT_BLUE, fg=RED
            ).pack(side="left")

            status_badge(head, report["status"]).pack(side="left", padx=8)

            detail = tk.Label(
                info,
                text=(
                    f"{report['barangay']} - {report['location']}\n"
                    f"Assigned: {report['assigned_organization']}"
                ),
                font=("Arial", 10), bg=LIGHT_BLUE, fg=TEXT,
                justify="left", anchor="w"
            )
            detail.pack(fill="x", pady=(3, 0))
            wrap_to_width(detail, 600)

        right = make_card(columns, padx=16, pady=14)
        right.grid(row=0, column=1, sticky="nsew", padx=(6, 0))

        tk.Label(
            right, text="Recent Emergency Activity", font=FONT_SECTION,
            bg=WHITE, fg=BLUE
        ).pack(anchor="w", pady=(0, 8))

        events = []
        for r in all_reports:
            for entry in r["history"]:
                events.append((entry, r["report_id"]))

        events.sort(reverse=True)

        if not events:
            tk.Label(
                right, text="No activity yet.", font=("Arial", 11),
                bg=WHITE, fg=GRAY
            ).pack(anchor="w")

        for entry, rid in events[:8]:
            item = tk.Label(
                right, text=f"{rid}\n{entry}", font=("Arial", 9),
                bg=WHITE, fg=TEXT, justify="left", anchor="w"
            )
            item.pack(fill="x", pady=4)
            wrap_to_width(item, 400)

        note = tk.Label(
            self.content,
            text=(
                "Emergency response and dispatch in this system are a "
                "simulation. No real emergency organization is contacted."
            ),
            font=("Arial", 10, "italic"), bg=BACKGROUND, fg=GRAY,
            justify="left", anchor="w"
        )
        note.pack(fill="x", pady=(10, 0))
        wrap_to_width(note, 1000)

    # -----------------------------------------------------
    # ACTIVE REPORTS / RESPONSE ARCHIVE
    # -----------------------------------------------------

    def create_reports_section(self, mode):
        saved = self.saved_filters.setdefault(mode, {})

        box = tk.Frame(
            self.content, bg=WHITE, padx=16, pady=16,
            highlightbackground=BORDER, highlightthickness=1
        )
        box.pack(fill="both", expand=True, pady=6)

        search_var = tk.StringVar(value=saved.get("search", ""))
        status_var = tk.StringVar(value=saved.get("status", "All Statuses"))
        type_var = tk.StringVar(value=saved.get("type", "All Types"))
        org_var = tk.StringVar(value=saved.get("org", "All Organizations"))
        date_var = tk.StringVar(value=saved.get("date", ""))

        # ----- search + filters -----
        bar = tk.Frame(box, bg=WHITE)
        bar.pack(fill="x", pady=(0, 6))

        def cell(col, text, weight):
            bar.grid_columnconfigure(col, weight=weight)
            cell_box = tk.Frame(bar, bg=WHITE)
            cell_box.grid(row=0, column=col, sticky="ew", padx=4)
            tk.Label(
                cell_box, text=text, font=("Arial", 10, "bold"),
                bg=WHITE, fg=TEXT
            ).pack(anchor="w")
            return cell_box

        tk.Entry(
            cell(0, "Search reports", 3), textvariable=search_var,
            font=("Arial", 11)
        ).pack(fill="x", ipady=3)

        col = 1

        if mode != "archive":
            statuses = ACTIVE_STATUSES
            ttk.Combobox(
                cell(col, "Status", 1), textvariable=status_var,
                values=["All Statuses"] + statuses, state="readonly",
                width=13
            ).pack(fill="x", ipady=2)
            col += 1

        ttk.Combobox(
            cell(col, "Type", 1), textvariable=type_var,
            values=["All Types"] + EMERGENCY_TYPES, state="readonly",
            width=11
        ).pack(fill="x", ipady=2)
        col += 1

        ttk.Combobox(
            cell(col, "Organization", 2), textvariable=org_var,
            values=["All Organizations"] + RESPONSE_ORGANIZATIONS,
            state="readonly", width=22
        ).pack(fill="x", ipady=2)
        col += 1

        tk.Entry(
            cell(col, "Date (YYYY-MM-DD)", 1), textvariable=date_var,
            font=("Arial", 11), width=12
        ).pack(fill="x", ipady=3)
        col += 1

        def clear_filters():
            search_var.set("")
            status_var.set("All Statuses")
            type_var.set("All Types")
            org_var.set("All Organizations")
            date_var.set("")

        tk.Button(
            bar, text="CLEAR", command=clear_filters,
            font=("Arial", 10, "bold"), bg=GRAY, fg=WHITE,
            activebackground="#444444", activeforeground=WHITE,
            relief="flat", bd=0, padx=12, pady=5, cursor="hand2"
        ).grid(row=0, column=col, sticky="s", padx=(8, 0))

        date_msg = tk.Label(
            box, text="", font=("Arial", 9), bg=WHITE, fg=RED, anchor="w"
        )
        date_msg.pack(fill="x")

        count_label = tk.Label(
            box, text="", font=("Arial", 10, "bold"), bg=WHITE, fg=GRAY,
            anchor="w"
        )
        count_label.pack(fill="x", pady=(0, 4))

        list_frame = tk.Frame(box, bg=WHITE)
        list_frame.pack(fill="both", expand=True)

        def render(*_):
            clear_frame(list_frame)

            if not database.admin_session_valid():
                self.guard()
                return

            date = date_var.get().strip()
            valid_date = ""
            date_msg.config(text="")

            if date:
                try:
                    datetime.strptime(date, "%Y-%m-%d")
                    valid_date = date
                except ValueError:
                    date_msg.config(
                        text="Date filter ignored - use YYYY-MM-DD."
                    )

            status = status_var.get()
            rtype = type_var.get()
            org = org_var.get()

            saved.update(
                search=search_var.get(), status=status, type=rtype,
                org=org, date=date_var.get()
            )

            reports = filter_reports(
                mode,
                text=search_var.get(),
                rtype="" if rtype.startswith("All") else rtype,
                status="" if status.startswith("All") else status,
                org="" if org.startswith("All") else org,
                date=valid_date
            )

            count_label.config(
                text=f"Showing {len(reports)} of "
                     f"{len(filter_reports(mode))} report(s)"
            )

            if not reports:
                tk.Label(
                    list_frame,
                    text=(
                        "No matching reports." if get_all_reports() else
                        "No emergency reports submitted yet."
                    ),
                    font=("Arial", 11), bg=WHITE, fg=GRAY, pady=20
                ).pack(fill="x")
                return

            for report in reports:
                self.make_report_card(list_frame, report)

            self.after_idle(self.update_scroll_region)

        for var in (search_var, status_var, type_var, org_var, date_var):
            var.trace_add("write", render)

        render()

    def make_report_card(self, parent, report):
        rid = report["report_id"]
        resolved = report["status"] == "Resolved"

        card = tk.Frame(parent, bg=LIGHT_BLUE, padx=13, pady=12)
        card.pack(fill="x", pady=5)

        head = tk.Frame(card, bg=LIGHT_BLUE)
        head.pack(fill="x")

        tk.Label(
            head, text=f"{rid}  |  {report['emergency']}",
            font=("Arial", 12, "bold"), bg=LIGHT_BLUE, fg=RED
        ).pack(side="left")

        status_badge(head, report["status"]).pack(side="left", padx=10)

        def line(text, font=("Arial", 10), fg=TEXT, pady=(2, 0)):
            label = tk.Label(
                card, text=text, font=font, bg=LIGHT_BLUE, fg=fg,
                justify="left", anchor="w"
            )
            label.pack(fill="x", pady=pady)
            wrap_to_width(label, 1000)

        line(
            f"{report['barangay']} - {report['location']}  |  "
            f"Submitted: {report['date_time']}  |  "
            f"Assigned: {report['assigned_organization']}",
            pady=(4, 2)
        )

        description = report["description"]
        if len(description) > 300:
            description = description[:300] + "..."
        line(description)

        if resolved and report["completed_at"]:
            line("Completed: " + report["completed_at"],
                 font=("Arial", 10, "bold"), fg=GREEN)

        if report["response_notes"]:
            notes = " ".join(report["response_notes"].split())
            if len(notes) > 200:
                notes = notes[:200] + "..."
            line("Response notes: " + notes,
                 font=("Arial", 10, "italic"), fg=GRAY)

        if report["sent_to_officials"]:
            line(
                f"SIMULATED DISPATCH: Sent to {report['sent_to_officials']}"
                f" | {report['sent_to_officials_at']}",
                font=("Arial", 10, "bold"), fg=GREEN, pady=(5, 0)
            )

        actions = tk.Frame(card, bg=LIGHT_BLUE)
        actions.pack(fill="x", pady=(8, 0))

        make_button(
            actions, "VIEW / UPDATE",
            lambda r=rid: self.edit_report(r), bg=BLUE
        ).pack(side="left")

        if resolved:
            make_button(
                actions, "REOPEN", lambda r=rid: self.reopen(r), bg=RED
            ).pack(side="left", padx=6)
            return

        if report["sent_to_officials"]:
            sent = make_button(actions, "SENT ✓", lambda: None, bg=GREEN)
            sent.config(state="disabled", disabledforeground=WHITE)
            sent.pack(side="left", padx=6)
        else:
            make_button(
                actions, "SEND EMERGENCY RESPONSE",
                lambda r=rid: self.send_report_to_officials(r), bg=GREEN
            ).pack(side="left", padx=6)

        make_button(
            actions, "MARK RESOLVED",
            lambda r=rid: self.mark_resolved(r), bg=RED
        ).pack(side="left", padx=6)

    # -----------------------------------------------------
    # Quick actions on a report card
    # -----------------------------------------------------

    def mark_resolved(self, rid):
        if not self.guard():
            return

        report = find_report(rid)

        if report is None:
            messagebox.showerror("Not Found", "Report not found.")
            return

        if not messagebox.askyesno(
            "Resolve Report",
            f"Mark report {rid} as Resolved?\n\n"
            "It will move to the Response Archive."
        ):
            return

        ok, message = self.run_protected(
            update_report, rid, "Resolved",
            report["assigned_organization"], report["response_notes"]
        )

        if ok is None:
            return

        if not ok:
            if message.startswith("Please assign"):
                message += "\n\nUse VIEW / UPDATE to choose an organization."
            messagebox.showwarning("Cannot Resolve", message)
            return

        messagebox.showinfo("Report Resolved", message)
        self.after_change()

    def reopen(self, rid):
        if not self.guard():
            return

        if not messagebox.askyesno(
            "Reopen Report",
            f"Return report {rid} to Active Reports?\n\n"
            "All previous information and history will be kept."
        ):
            return

        ok, message = self.run_protected(reopen_report, rid)

        if ok is None:
            return

        (messagebox.showinfo if ok else messagebox.showwarning)(
            "Reopen Report", message
        )
        self.after_change()

    # -----------------------------------------------------
    # SIMULATED EMERGENCY RESPONSE (dispatch)
    # -----------------------------------------------------

    def send_report_to_officials(self, rid):
        """Let the admin choose recipients for a SIMULATED dispatch."""
        if not self.guard():
            return

        report = find_report(rid)

        if report is None:
            messagebox.showerror("Not Found", "Report not found.")
            return

        if report["sent_to_officials"]:
            messagebox.showinfo(
                "Already Sent",
                "This report has already been marked as sent in the "
                "simulation."
            )
            return

        suggested = DISPATCH_SUGGESTIONS.get(
            report["emergency"].strip().lower(),
            DISPATCH_SUGGESTIONS["other"]
        )

        win = tk.Toplevel(self)
        win.title("Choose Emergency Response Recipients")
        win.geometry("520x520")
        win.minsize(460, 440)
        win.configure(bg=BACKGROUND)
        win.transient(self.winfo_toplevel())
        win.grab_set()

        card = tk.Frame(
            win, bg=WHITE, padx=20, pady=18,
            highlightbackground=BORDER, highlightthickness=1
        )
        card.pack(fill="both", expand=True, padx=16, pady=16)

        tk.Label(
            card, text="SEND EMERGENCY RESPONSE (SIMULATION)",
            font=("Arial", 15, "bold"), bg=WHITE, fg=RED
        ).pack(anchor="w")

        tk.Label(
            card,
            text=f"Report: {rid}  |  Scenario: {report['emergency']}",
            font=("Arial", 10, "bold"), bg=WHITE, fg=TEXT,
            wraplength=440, justify="left"
        ).pack(anchor="w", pady=(6, 3))

        tk.Label(
            card,
            text="Select the officials/agencies to notify in this simulation:",
            font=("Arial", 10), bg=WHITE, fg=GRAY,
            wraplength=440, justify="left"
        ).pack(anchor="w", pady=(0, 10))

        recipient_vars = {}

        for recipient in DISPATCH_RECIPIENTS:
            var = tk.BooleanVar(value=recipient in suggested)
            recipient_vars[recipient] = var

            tk.Checkbutton(
                card, text=recipient, variable=var,
                font=("Arial", 10), bg=WHITE, fg=TEXT,
                activebackground=WHITE, selectcolor=LIGHT_BLUE,
                anchor="w", justify="left", wraplength=430
            ).pack(fill="x", anchor="w", pady=2)

        tk.Label(
            card,
            text=(
                "Suggested recipients are pre-selected for the scenario. "
                "You can change the selection. This is a demonstration "
                "only - no real officials or agencies are contacted."
            ),
            font=("Arial", 9), bg=WHITE, fg=GRAY,
            wraplength=440, justify="left"
        ).pack(anchor="w", pady=(8, 10))

        buttons = tk.Frame(card, bg=WHITE)
        buttons.pack(fill="x", side="bottom")

        def confirm_send():
            selected = [
                name for name, var in recipient_vars.items() if var.get()
            ]

            ok, message = self.run_protected(dispatch_report, rid, selected)

            if ok is None:
                win.destroy()
                return

            if not ok:
                messagebox.showwarning(
                    "Cannot Send", message, parent=win
                )
                return

            win.destroy()
            self.after_change()

            messagebox.showinfo(
                "Simulated Send Complete",
                f"Report {rid} is now marked as SENT.\n\n"
                f"Scenario: {report['emergency']}\n"
                f"Recipient(s): {message}\n\n"
                "This is a demonstration only. No real officials were "
                "contacted."
            )

        make_button(buttons, "CANCEL", win.destroy, bg=GRAY).pack(
            side="right", padx=(6, 0)
        )
        make_button(
            buttons, "CONFIRM SIMULATED SEND", confirm_send, bg=GREEN
        ).pack(side="right")

    # -----------------------------------------------------
    # REPORT DETAILS + MANAGEMENT WINDOW
    # -----------------------------------------------------

    def edit_report(self, rid):
        if not self.guard():
            return

        report = find_report(rid)

        if report is None:
            messagebox.showerror("Not Found", "Report not found.")
            return

        win = tk.Toplevel(self)
        win.title("Report Details and Management")
        height = min(820, win.winfo_screenheight() - 90)
        win.geometry(f"720x{height}")
        win.minsize(620, 520)
        win.configure(bg=BACKGROUND)
        win.transient(self.winfo_toplevel())
        win.grab_set()

        # Buttons are packed first so they always stay visible
        buttons = tk.Frame(win, bg=BACKGROUND)
        buttons.pack(side="bottom", fill="x", padx=14, pady=(0, 14))

        card = tk.Frame(win, bg=WHITE, padx=20, pady=14)
        card.pack(fill="both", expand=True, padx=14, pady=(14, 8))

        title_row = tk.Frame(card, bg=WHITE)
        title_row.pack(fill="x")

        tk.Label(
            title_row, text=f"Report {rid}", font=("Arial", 17, "bold"),
            bg=WHITE, fg=BLUE
        ).pack(side="left")

        status_badge(title_row, report["status"]).pack(side="left", padx=12)

        details = (
            f"Emergency: {report['emergency']}\n"
            f"Reporter: {report['name']} | Contact: {report['contact']}\n"
            f"Location: {report['barangay']}, {report['location']}\n"
            f"Submitted: {report['date_time']}\n"
            f"Completed: {report['completed_at'] or '-'}\n\n"
            f"Description: {report['description']}\n"
            "Photo: " + (
                os.path.basename(report["photo"])
                if report["photo"] else "None"
            )
        )
        detail_label = tk.Label(
            card, text=details, font=("Arial", 10), bg=WHITE, fg=TEXT,
            justify="left", anchor="w"
        )
        detail_label.pack(fill="x", pady=8)
        wrap_to_width(detail_label, 900)

        if report["sent_to_officials"]:
            tk.Label(
                card,
                text=(
                    f"SIMULATED DISPATCH: Sent to {report['sent_to_officials']}"
                    f" | {report['sent_to_officials_at']}"
                ),
                font=("Arial", 10, "bold"), bg=WHITE, fg=GREEN,
                justify="left", wraplength=620
            ).pack(anchor="w", pady=(0, 6))

        # ----- attached photo preview -----
        photo_path = report["photo"]

        if photo_path and os.path.isfile(photo_path):
            photo_box = tk.Frame(
                card, bg=LIGHT_BLUE, padx=10, pady=8,
                highlightbackground=BORDER, highlightthickness=1
            )
            photo_box.pack(fill="x", pady=(0, 8))

            tk.Label(
                photo_box, text="ATTACHED EMERGENCY PHOTO",
                font=("Arial", 10, "bold"), bg=LIGHT_BLUE, fg=BLUE
            ).pack(anchor="w")

            preview = load_photo_preview(photo_path)

            if preview is not None:
                preview_label = tk.Label(photo_box, image=preview, bg=LIGHT_BLUE)
                preview_label.image = preview      # keep a reference
                preview_label.pack(anchor="w", pady=(6, 4))
            else:
                tk.Label(
                    photo_box,
                    text=(
                        os.path.basename(photo_path) +
                        "\nPreview not available. Use OPEN PHOTO to view "
                        "the image."
                    ),
                    font=("Arial", 10), bg=LIGHT_BLUE, fg=TEXT,
                    justify="left"
                ).pack(anchor="w", pady=(6, 4))

            def open_attached_photo():
                try:
                    if hasattr(os, "startfile"):
                        os.startfile(photo_path)
                    else:
                        import webbrowser
                        from pathlib import Path
                        webbrowser.open(Path(photo_path).resolve().as_uri())
                except Exception as exc:
                    messagebox.showerror(
                        "Cannot Open Photo", str(exc), parent=win
                    )

            make_button(
                photo_box, "OPEN PHOTO", open_attached_photo, bg=BLUE
            ).pack(anchor="w", pady=(4, 0))
        else:
            tk.Label(
                card,
                text=(
                    "Attached photo: None" if not photo_path else
                    "Attached photo: file not found (" +
                    os.path.basename(photo_path) + ")"
                ),
                font=("Arial", 10), bg=WHITE, fg=GRAY
            ).pack(anchor="w", pady=(0, 8))

        # ----- status / organization / notes -----
        tk.Label(
            card, text="Status", font=("Arial", 10, "bold"),
            bg=WHITE, fg=TEXT
        ).pack(anchor="w")

        status_var = tk.StringVar(value=report["status"])
        ttk.Combobox(
            card, textvariable=status_var, values=REPORT_STATUSES,
            state="readonly", font=("Arial", 11)
        ).pack(fill="x", pady=(3, 8))

        tk.Label(
            card, text="Assign to Organization / Response Team",
            font=("Arial", 10, "bold"), bg=WHITE, fg=TEXT
        ).pack(anchor="w")

        org_var = tk.StringVar(value=report["assigned_organization"])
        org_box = ttk.Combobox(
            card, textvariable=org_var, values=RESPONSE_ORGANIZATIONS,
            state="readonly", font=("Arial", 10)
        )
        org_box.pack(fill="x", pady=(3, 2))

        contact_label = tk.Label(
            card, text="", font=("Arial", 9), bg=WHITE, fg=GRAY,
            anchor="w", justify="left"
        )
        contact_label.pack(fill="x")
        wrap_to_width(contact_label, 700)

        def update_contact(*_):
            contact_label.config(
                text="Contact: " + org_contact(org_var.get()) +
                     "   (assigning does not mean the report was delivered)"
            )

        org_box.bind("<<ComboboxSelected>>", update_contact)
        update_contact()

        tk.Label(
            card, text="Response Notes", font=("Arial", 10, "bold"),
            bg=WHITE, fg=TEXT
        ).pack(anchor="w", pady=(6, 0))

        notes = tk.Text(card, height=4, font=("Arial", 10), wrap="word")
        notes.pack(fill="both", expand=True, pady=(3, 8))
        notes.insert("1.0", report["response_notes"])

        tk.Label(
            card, text="Response History", font=("Arial", 10, "bold"),
            bg=WHITE, fg=TEXT
        ).pack(anchor="w")

        history = tk.Text(
            card, height=4, font=("Arial", 9), wrap="word",
            bg=BACKGROUND, relief="flat"
        )
        history.pack(fill="x", pady=(3, 0))
        history.insert("1.0", "\n".join(report["history"]))
        history.config(state="disabled")
        history.see("end")

        def save_changes():
            ok, message = self.run_protected(
                update_report, rid, status_var.get(), org_var.get(),
                notes.get("1.0", "end")
            )

            if ok is None:
                win.destroy()
                return

            if not ok:
                messagebox.showwarning("Cannot Save", message, parent=win)
                return

            win.destroy()
            self.after_change()
            messagebox.showinfo("Report Updated", message)

        make_button(buttons, "SAVE CHANGES", save_changes, bg=RED).pack(
            side="left"
        )
        make_button(buttons, "CLOSE", win.destroy, bg=GRAY).pack(side="right")

    # -----------------------------------------------------
    # EVACUATION AREA MANAGEMENT
    # Saved in the database; the user app reads the same table.
    # -----------------------------------------------------

    def create_evacuation_section(self):
        areas = get_evacuation_areas()

        box = tk.Frame(
            self.content, bg=WHITE, padx=22, pady=20,
            highlightbackground=BORDER, highlightthickness=1
        )
        box.pack(fill="x", pady=10)

        tk.Label(
            box, text="Evacuation Area Management",
            font=("Arial", 17, "bold"), bg=WHITE, fg=BLUE
        ).pack(anchor="w")

        tk.Label(
            box,
            text=(
                "Administrators can add, edit, or delete evacuation "
                "locations displayed to users."
            ),
            font=("Arial", 10), bg=WHITE, fg=GRAY
        ).pack(anchor="w", pady=(3, 15))

        make_button(
            box, "ADD EVACUATION AREA", self.add_evacuation, bg=RED
        ).pack(anchor="w", pady=(0, 15))

        if not areas:
            tk.Label(
                box, text="No evacuation areas listed.",
                font=("Arial", 11), bg=WHITE, fg=GRAY
            ).pack(anchor="w")

        for item in areas:
            row = tk.Frame(box, bg=LIGHT_BLUE, padx=18, pady=15)
            row.pack(fill="x", pady=5)

            actions = tk.Frame(row, bg=LIGHT_BLUE)
            actions.pack(side="right")

            detail = tk.Frame(row, bg=LIGHT_BLUE)
            detail.pack(side="left", fill="x", expand=True)

            tk.Label(
                detail, text=item["name"], font=("Arial", 13, "bold"),
                bg=LIGHT_BLUE, fg=RED, anchor="w"
            ).pack(fill="x")

            info = tk.Label(
                detail,
                text=(
                    f"Barangay: {item['barangay']} | "
                    f"Location: {item['location']} | "
                    f"Capacity: {format_capacity(item['capacity'])}\n"
                    f"Notes: {item.get('notes', '')}"
                ),
                font=("Arial", 11), bg=LIGHT_BLUE, fg=TEXT,
                justify="left", anchor="w"
            )
            info.pack(fill="x", pady=(3, 0))
            wrap_to_width(info, 800)

            make_button(
                actions, "EDIT",
                lambda a=item: self.edit_evacuation(a), bg=BLUE
            ).pack(side="left", padx=2)

            make_button(
                actions, "DELETE",
                lambda a=item["id"]: self.delete_evacuation(a), bg=RED
            ).pack(side="left", padx=2)

        note = tk.Label(
            self.content,
            text=(
                "Data note: reports and evacuation changes are saved in the "
                "iHANDA database and are kept when the program closes."
            ),
            font=("Arial", 10, "italic"), bg=BACKGROUND, fg=GRAY,
            justify="left", anchor="w"
        )
        note.pack(fill="x", pady=(4, 0))
        wrap_to_width(note, 1000)

    def add_evacuation(self):
        if self.guard():
            self.evacuation_form()

    def edit_evacuation(self, area):
        if self.guard():
            self.evacuation_form(data=area)

    def evacuation_form(self, data=None):
        win = tk.Toplevel(self)
        win.title("Edit Evacuation Area" if data else "Add Evacuation Area")
        win.geometry("500x540")
        win.resizable(False, False)
        win.configure(bg=BACKGROUND)
        win.transient(self.winfo_toplevel())
        win.grab_set()

        card = tk.Frame(win, bg=WHITE, padx=25, pady=25)
        card.pack(fill="both", expand=True, padx=20, pady=20)

        tk.Label(
            card,
            text="Edit Evacuation Area" if data else "Add Evacuation Area",
            font=("Arial", 18, "bold"), bg=WHITE, fg=BLUE
        ).pack(anchor="w", pady=(0, 15))

        entries = {}

        fields = [
            ("Location Name", "name"),
            ("Barangay", "barangay"),
            ("Address / Landmark", "location"),
            ("Capacity (number of persons)", "capacity"),
            ("Notes", "notes")
        ]

        for label, key in fields:
            tk.Label(
                card, text=label, font=("Arial", 9, "bold"),
                bg=WHITE, fg=TEXT
            ).pack(anchor="w")

            if key == "capacity":
                # numbers only (maximum 6 digits)
                entry = tk.Entry(
                    card, font=("Arial", 10), validate="key",
                    validatecommand=(
                        win.register(
                            lambda v: v == "" or (v.isdigit() and len(v) <= 6)
                        ),
                        "%P"
                    )
                )
            else:
                entry = tk.Entry(card, font=("Arial", 10))

            entry.pack(fill="x", pady=(3, 10), ipady=2)

            if data:
                value = data.get(key, "")
                if key != "capacity" or str(value).isdigit():
                    entry.insert(0, value)

            entries[key] = entry

        def save():
            if not database.admin_session_valid():
                win.destroy()
                self.guard()
                return

            values = {key: entries[key].get().strip() for _, key in fields}

            if not values["name"] or not values["barangay"]:
                messagebox.showwarning(
                    "Missing Information",
                    "Location Name and Barangay are required.",
                    parent=win
                )
                return

            if not values["capacity"].isdigit() or int(values["capacity"]) < 1:
                messagebox.showwarning(
                    "Invalid Capacity",
                    "Capacity must be a number greater than 0 "
                    "(for example: 300).",
                    parent=win
                )
                return

            if data is None:
                ok, message = self.run_protected(add_evacuation_area, values)
            else:
                ok, message = self.run_protected(
                    update_evacuation_area, data["id"], values
                )

            if ok is None:
                win.destroy()
                return

            if not ok:
                messagebox.showwarning("Cannot Save", message, parent=win)
                return

            win.destroy()
            self.after_change()

        make_button(card, "SAVE", save, bg=RED).pack(anchor="e", pady=(5, 0))

    def delete_evacuation(self, area_id):
        if not self.guard():
            return

        if messagebox.askyesno(
            "Delete Evacuation Area",
            "Are you sure you want to delete this evacuation area?"
        ):
            ok, message = self.run_protected(delete_evacuation_area, area_id)

            if ok is False:
                messagebox.showwarning("Cannot Delete", message)

            if ok is not None:
                self.after_change()


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":

    database.init_db()

    app = AdminApp()

    app.attributes("-fullscreen", True)

    # Press ESC to leave fullscreen, F11 to go back
    app.bind(
        "<Escape>",
        lambda e: app.attributes("-fullscreen", False)
    )
    app.bind(
        "<F11>",
        lambda e: app.attributes(
            "-fullscreen",
            not app.attributes("-fullscreen")
        )
    )

    app.mainloop()
