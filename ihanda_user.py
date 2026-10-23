"""
iHANDA Dagupan - USER application.

    python ihanda_user.py

Registration, login and the public features (disaster information, ready kit,
hotlines, first aid, evacuation areas, emergency reporting).
The administrator system is a separate program (ihanda_admin.py) and is not
part of, or reachable from, this application.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
import re

import database
from ihanda_common import *


# =========================================================
# MAIN APP
# =========================================================

class App(tk.Tk):

    AUTH_PAGES = ("LoginScreen", "RegisterScreen")

    def __init__(self):
        super().__init__()

        self.title("iHANDA Dagupan")
        self.option_add("*TCombobox*Listbox.font", ("Arial", 12))
        self.geometry("1200x740")
        self.minsize(1100, 620)
        self.configure(bg=BACKGROUND)

        style = ttk.Style()
        style.configure("Treeview", rowheight=30, font=("Arial", 10))
        style.configure("Treeview.Heading", font=("Arial", 10, "bold"))

        self.current_frame = None
        self.current_user = None          # set after a successful login
        self.frames = {}

        container = tk.Frame(self, bg=BACKGROUND)
        container.pack(fill="both", expand=True)

        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        self.container = container

        for Page in (LoginScreen, RegisterScreen):
            frame = Page(container, self)
            self.frames[Page.__name__] = frame
            frame.grid(row=0, column=0, sticky="nsew")

        self.bind_all("<MouseWheel>", self.global_scroll)

        self.show_frame("LoginScreen")

    # ---------- login / logout ----------

    def build_main_pages(self):
        """The real pages only exist while someone is logged in."""
        pages = (
            HomeScreen,
            DisasterScreen,
            ReadyKitScreen,
            HotlinesScreen,
            FirstAidScreen,
            EvacuationScreen,
            EmergencyReportScreen
        )

        for Page in pages:
            frame = Page(self.container, self)
            self.frames[Page.__name__] = frame
            frame.grid(row=0, column=0, sticky="nsew")

    def destroy_main_pages(self):
        for name in list(self.frames):
            if name not in self.AUTH_PAGES:
                self.frames.pop(name).destroy()

    def login_user(self, user):
        self.current_user = user
        self.build_main_pages()
        self.show_frame("HomeScreen")

    def show_login(self, notice=None, kind="success", identifier=""):
        login = self.frames["LoginScreen"]
        login.pending = (notice, kind, identifier)
        self.show_frame("LoginScreen")

    def logout(self):
        if not messagebox.askyesno(
            "Log Out", "Are you sure you want to log out?"
        ):
            return

        self.current_user = None
        self.show_login("You have been logged out successfully.")
        self.destroy_main_pages()

    def show_frame(self, page_name):
        # No login -> only the Login / Register pages can be opened.
        if page_name not in self.AUTH_PAGES and self.current_user is None:
            page_name = "LoginScreen"

        frame = self.frames[page_name]
        self.current_frame = frame
        frame.tkraise()

        if hasattr(frame, "reset_scroll"):
            frame.reset_scroll()

        if hasattr(frame, "on_show"):
            frame.on_show()

        if page_name == "EvacuationScreen":
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
# LOGIN
# =========================================================

class LoginScreen(tk.Frame):

    def __init__(self, parent, controller):
        super().__init__(parent, bg=WHITE)

        self.controller = controller
        self.pending = None

        form = build_auth_shell(
            self,
            WELCOME_TITLE,
            WELCOME_TEXT,
            [
                "Disaster guides and safety tips",
                "Evacuation areas and emergency hotlines",
                "Fast emergency reporting"
            ]
        )

        tk.Label(
            form, text="Log in to your account", font=("Arial", 22, "bold"),
            bg=WHITE, fg=BLUE, anchor="w"
        ).pack(fill="x")

        tk.Label(
            form,
            text="Enter your username or iHANDA email and your password.",
            font=("Arial", 11), bg=WHITE, fg=GRAY, anchor="w"
        ).pack(fill="x", pady=(2, 12))

        self.message = MessageBar(form)

        box, self.identifier = auth_field(form, "Username or Email")
        box.pack(fill="x", pady=(0, 12))

        box, self.password = auth_field(form, "Password", show="•")
        box.pack(fill="x")

        password_toggle(form, [self.password]).pack(anchor="w", pady=(6, 14))

        primary_button(form, "LOGIN", self.login, bg=RED).pack(fill="x")

        footer = tk.Frame(form, bg=WHITE)
        footer.pack(pady=(16, 0))

        tk.Label(
            footer, text="Don't have an account?", font=("Arial", 10),
            bg=WHITE, fg=GRAY
        ).pack(side="left")

        link_button(
            footer, "CREATE ACCOUNT",
            lambda: controller.show_frame("RegisterScreen")
        ).pack(side="left", padx=4)

        self.identifier.bind("<Return>", lambda e: self.login())
        self.password.bind("<Return>", lambda e: self.login())

    def on_show(self):
        self.password.delete(0, "end")
        self.message.clear()

        if self.pending:
            notice, kind, identifier = self.pending
            self.pending = None

            if identifier:
                self.identifier.delete(0, "end")
                self.identifier.insert(0, identifier)

            if notice:
                self.message.show(notice, kind)

        (self.password if self.identifier.get() else self.identifier
         ).focus_set()

    def login(self):
        identifier = self.identifier.get().strip()
        password = self.password.get()

        user, error = database.authenticate(identifier, password, "user")

        if user is None:
            self.password.delete(0, "end")
            self.message.show(error)
            (self.identifier if not identifier else self.password
             ).focus_set()
            return

        self.identifier.delete(0, "end")
        self.password.delete(0, "end")
        self.message.clear()

        self.controller.login_user(user)


# =========================================================
# REGISTER
# =========================================================

class RegisterScreen(tk.Frame):

    def __init__(self, parent, controller):
        super().__init__(parent, bg=WHITE)

        self.controller = controller

        form = build_auth_shell(
            self,
            WELCOME_TITLE,
            WELCOME_TEXT,
            [
                "Free resident account",
                "Use your iHANDA email (ending in .ih@dagupan.com)",
                "Your password is stored securely"
            ]
        )

        tk.Label(
            form, text="Create your account", font=("Arial", 22, "bold"),
            bg=WHITE, fg=BLUE, anchor="w"
        ).pack(fill="x")

        tk.Label(
            form, text="Fill in the details below. All fields are required.",
            font=("Arial", 11), bg=WHITE, fg=GRAY, anchor="w"
        ).pack(fill="x", pady=(2, 10))

        self.message = MessageBar(form)

        box, self.username = auth_field(
            form, "Username",
            hint="3-30 characters: letters, numbers, dot, dash, underscore."
        )
        box.pack(fill="x", pady=(0, 8))

        box, self.email = auth_field(
            form, "Email",
            hint="Must end with .ih@dagupan.com  (example: juan.ih@dagupan.com)"
        )
        box.pack(fill="x", pady=(0, 8))

        passwords = tk.Frame(form, bg=WHITE)
        passwords.pack(fill="x")
        passwords.grid_columnconfigure(0, weight=1, uniform="pw")
        passwords.grid_columnconfigure(1, weight=1, uniform="pw")

        box, self.password = auth_field(passwords, "Password", show="•")
        box.grid(row=0, column=0, sticky="ew", padx=(0, 6))

        box, self.confirm = auth_field(passwords, "Confirm Password", show="•")
        box.grid(row=0, column=1, sticky="ew", padx=(6, 0))

        tk.Label(
            form, text="At least 8 characters, with letters and numbers.",
            font=("Arial", 9), bg=WHITE, fg=GRAY, anchor="w"
        ).pack(fill="x", pady=(3, 0))

        password_toggle(
            form, [self.password, self.confirm]
        ).pack(anchor="w", pady=(4, 12))

        primary_button(
            form, "CREATE ACCOUNT", self.register, bg=RED
        ).pack(fill="x")

        footer = tk.Frame(form, bg=WHITE)
        footer.pack(pady=(14, 0))

        tk.Label(
            footer, text="Already have an account?", font=("Arial", 10),
            bg=WHITE, fg=GRAY
        ).pack(side="left")

        link_button(
            footer, "LOG IN", lambda: controller.show_login()
        ).pack(side="left", padx=4)

        for entry in (self.username, self.email, self.password, self.confirm):
            entry.bind("<Return>", lambda e: self.register())

    def on_show(self):
        self.message.clear()
        self.password.delete(0, "end")
        self.confirm.delete(0, "end")
        self.username.focus_set()

    def register(self):
        username = self.username.get().strip()

        ok, message = database.register_user(
            username,
            self.email.get(),
            self.password.get(),
            self.confirm.get()
        )

        if not ok:
            self.message.show(message)
            return

        for entry in (self.username, self.email, self.password, self.confirm):
            entry.delete(0, "end")

        self.controller.show_login(
            "Account created successfully. You can now log in.",
            "success", username
        )


# =========================================================
# PUBLIC HEADER / NAVIGATION  (user app only)
# =========================================================

NAV_BUTTONS = [
    ("HOME", "HomeScreen"),
    ("DISASTER\nRECOGNITION", "DisasterScreen"),
    ("READY KIT", "ReadyKitScreen"),
    ("HOTLINES", "HotlinesScreen"),
    ("FIRST AID", "FirstAidScreen"),
    ("EVACUATION", "EvacuationScreen"),
    ("EMERGENCY\nREPORT", "EmergencyReportScreen")
]


def create_navigation(parent, controller, active_page):

    header = tk.Frame(parent, height=96, bg=BLUE)
    header.pack(fill="x")
    header.pack_propagate(False)

    # Blue section
    left = tk.Frame(header, bg=BLUE)
    left.pack(side="left", fill="y", padx=(22, 12))

    tk.Label(
        left,
        text="iHANDA Dagupan",
        font=("Arial", 21, "bold"),
        bg=BLUE,
        fg=WHITE
    ).pack(anchor="w", pady=(24, 0))

    tk.Label(
        left,
        text="Disaster Preparedness System",
        font=("Arial", 10),
        bg=BLUE,
        fg=WHITE
    ).pack(anchor="w")

    # Red section
    right = tk.Frame(header, bg=RED)
    right.pack(side="right", fill="both", expand=True)

    divider = tk.Canvas(
        right,
        width=28,
        bg=RED,
        highlightthickness=0
    )
    divider.pack(side="left", fill="y")

    divider.create_polygon(
        0, 0,
        28, 0,
        0, 96,
        fill=BLUE,
        outline=BLUE
    )

    nav = tk.Frame(right, bg=RED)
    nav.pack(side="left", fill="both", expand=True, padx=(4, 10))

    def nav_button(text, page, active):
        return tk.Button(
            nav,
            text=text,
            command=page,
            font=("Arial", 11, "bold"),
            bg=WHITE if active else RED,
            fg=RED if active else WHITE,
            activebackground=WHITE,
            activeforeground=RED,
            relief="flat",
            bd=0,
            padx=10,
            pady=8,
            cursor="hand2"
        )

    # Buttons share the available width, so labels are never cut off.
    for text, page in NAV_BUTTONS:
        nav_button(
            text,
            lambda p=page: controller.show_frame(p),
            page == active_page
        ).pack(side="left", fill="both", expand=True, padx=3, pady=16)

    tk.Frame(
        nav,
        width=2,
        bg=WHITE
    ).pack(side="left", fill="y", pady=22, padx=8)

    name = controller.current_user["username"] if controller.current_user else ""
    short = name if len(name) <= 12 else name[:11] + "…"

    logout_button = nav_button("LOGOUT\n" + short, controller.logout, False)
    logout_button.config(
        bg=DARK_BLUE, fg=WHITE,
        activebackground=BLUE, activeforeground=WHITE
    )
    logout_button.pack(
        side="left", fill="both", expand=True, padx=3, pady=16
    )


# =========================================================
# HOME
# =========================================================

class HomeScreen(ScrollPage):

    FEATURES = [
        (
            "Disaster Recognition",
            "Learn about floods, earthquakes, fires, and tsunamis, "
            "including warning signs and safety measures."
        ),
        (
            "Ready Kit",
            "See what to prepare before an emergency and which supplies "
            "belong in an emergency kit."
        ),
        (
            "Evacuation Areas",
            "Identify safe areas and evacuation locations that may be "
            "used during emergencies."
        ),
        (
            "Emergency Hotlines",
            "Access important emergency contact information for "
            "assistance during disasters."
        ),
        (
            "First Aid",
            "Review basic first aid steps to follow while waiting for "
            "professional help."
        ),
        (
            "Emergency Reporting",
            "Provide information about urgent situations so that proper "
            "authorities or responders can be informed."
        )
    ]

    QUICK_ACCESS = [
        ("Emergency Reporting", "EmergencyReportScreen", "!", RED),
        ("Evacuation Areas", "EvacuationScreen", "⌂", BLUE),
        ("Emergency Hotlines", "HotlinesScreen", "☎", RED),
        ("Ready Kit", "ReadyKitScreen", "✚", BLUE),
        ("First Aid", "FirstAidScreen", "✚", GREEN),
        ("Disaster Recognition", "DisasterScreen", "≈", BLUE)
    ]

    TIPS = [
        ("Know your route",
         "Know your family's evacuation area and route before a disaster."),
        ("Prepare your kit",
         "Keep drinking water, food, a flashlight, and first aid supplies ready."),
        ("Follow official warnings",
         "Monitor weather conditions and follow instructions from authorities.")
    ]

    def __init__(self, parent, controller):
        super().__init__(parent, bg=BACKGROUND)

        self.controller = controller

        create_navigation(self, controller, "HomeScreen")
        create_footer(self)
        self.setup_scroll()

        self.build_hero()
        self.build_quick_access()
        self.build_reminders()

    # ---------- hero ----------
    def build_hero(self):
        hero = tk.Frame(self.content, bg=BLUE, padx=30, pady=24)
        hero.pack(fill="x", pady=(4, 14))

        hotline = tk.Frame(hero, bg=RED, padx=24, pady=16)
        hotline.pack(side="right", anchor="n", padx=(20, 0))

        tk.Label(
            hotline, text="IN AN EMERGENCY CALL", font=("Arial", 10, "bold"),
            bg=RED, fg=WHITE
        ).pack()
        tk.Label(
            hotline, text="911", font=("Arial", 36, "bold"),
            bg=RED, fg=WHITE
        ).pack()
        tk.Label(
            hotline, text="National Emergency Hotline",
            font=("Arial", 10), bg=RED, fg=WHITE
        ).pack()

        left = tk.Frame(hero, bg=BLUE)
        left.pack(side="left", fill="x", expand=True)

        tk.Label(
            left, text="DAGUPAN CITY DISASTER PREPAREDNESS",
            font=("Arial", 10, "bold"), bg=BLUE, fg=LIGHT_BLUE
        ).pack(anchor="w")

        tk.Label(
            left, text="Welcome to iHANDA Dagupan",
            font=("Arial", 30, "bold"), bg=BLUE, fg=WHITE
        ).pack(anchor="w", pady=(4, 6))

        intro = tk.Label(
            left,
            text=(
                "iHANDA Dagupan is a community-based disaster preparedness "
                "information system designed to help residents of Dagupan "
                "City become more informed and prepared for disasters. "
                "It helps residents stay informed, prepared, and safe "
                "before, during, and after disasters."
            ),
            font=("Arial", 14), bg=BLUE, fg=WHITE,
            justify="left", anchor="w"
        )
        intro.pack(fill="x")
        wrap_to_width(intro, 800)

        buttons = tk.Frame(left, bg=BLUE)
        buttons.pack(anchor="w", pady=(16, 0))

        make_button(
            buttons, "REPORT AN EMERGENCY",
            lambda: self.controller.show_frame("EmergencyReportScreen"),
            bg=RED
        ).pack(side="left")

        make_button(
            buttons, "VIEW EVACUATION AREAS",
            lambda: self.controller.show_frame("EvacuationScreen"),
            bg=WHITE, fg=BLUE
        ).pack(side="left", padx=10)

    # ---------- quick access ----------
    def build_quick_access(self):
        section_heading(self.content, "Quick Access").pack(
            fill="x", pady=(4, 8)
        )

        grid = tk.Frame(self.content, bg=BACKGROUND)
        grid.pack(fill="x")

        for c in range(3):
            grid.grid_columnconfigure(c, weight=1, uniform="quick")

        descriptions = dict(self.FEATURES)

        for i, (title, page, symbol, color) in enumerate(self.QUICK_ACCESS):
            card = make_card(grid, padx=16, pady=14)
            card.grid(
                row=i // 3, column=i % 3, sticky="nsew",
                padx=(0 if i % 3 == 0 else 6, 0 if i % 3 == 2 else 6),
                pady=6
            )

            top = tk.Frame(card, bg=WHITE)
            top.pack(fill="x")

            icon_tile(top, symbol, color).pack(side="left")

            tk.Label(
                top, text=title, font=FONT_CARD_TITLE,
                bg=WHITE, fg=BLUE, anchor="w"
            ).pack(side="left", padx=12)

            text = tk.Label(
                card, text=descriptions.get(title, ""),
                font=("Arial", 12), bg=WHITE, fg=TEXT,
                justify="left", anchor="w"
            )
            text.pack(fill="x", pady=(10, 0))
            wrap_to_width(text, 500)

            make_clickable(card, lambda p=page: self.controller.show_frame(p))

    # ---------- reminders ----------
    def build_reminders(self):
        notice = tk.Frame(self.content, bg=LIGHT_BLUE, padx=26, pady=18)
        notice.pack(fill="x", pady=(10, 6))

        tk.Label(
            notice, text="Be Prepared. Stay Safe.",
            font=("Arial", 22, "bold"), bg=LIGHT_BLUE, fg=RED
        ).pack(anchor="w")

        message = tk.Label(
            notice,
            text=(
                "Disasters can happen unexpectedly. Being prepared, "
                "following official warnings, knowing evacuation routes, "
                "and having an emergency kit can help reduce risks and "
                "protect individuals, families, and communities."
            ),
            font=("Arial", 13), bg=LIGHT_BLUE, fg=TEXT,
            justify="left", anchor="w"
        )
        message.pack(fill="x", pady=(6, 10))
        wrap_to_width(message, 1000)

        tips = tk.Frame(notice, bg=LIGHT_BLUE)
        tips.pack(fill="x")

        for c in range(3):
            tips.grid_columnconfigure(c, weight=1, uniform="tips")

        for c, (title, text) in enumerate(self.TIPS):
            tip = tk.Frame(tips, bg=WHITE, padx=14, pady=10)
            tip.grid(
                row=0, column=c, sticky="nsew",
                padx=(0 if c == 0 else 5, 0 if c == 2 else 5)
            )

            tk.Label(
                tip, text="✔  " + title, font=("Arial", 12, "bold"),
                bg=WHITE, fg=GREEN, anchor="w"
            ).pack(fill="x")

            label = tk.Label(
                tip, text=text, font=("Arial", 11), bg=WHITE, fg=TEXT,
                justify="left", anchor="w"
            )
            label.pack(fill="x", pady=(3, 0))
            wrap_to_width(label, 400)


# =========================================================
# DISASTER RECOGNITION
# =========================================================

class DisasterScreen(ScrollPage):

    def __init__(self, parent, controller):
        super().__init__(parent, bg=BACKGROUND)

        create_navigation(self, controller, "DisasterScreen")
        create_footer(self)
        self.setup_scroll()

        page_title(
            self.content,
            "Disaster Recognition",
            "Click a disaster to show or hide its information."
        )

        self.cards = {}

        for name in DISASTERS:
            self.create_disaster_card(name)

    def create_disaster_card(self, name):
        outer = tk.Frame(
            self.content,
            bg=WHITE,
            highlightbackground=BORDER,
            highlightthickness=1
        )
        outer.pack(fill="x", pady=5)

        button = tk.Button(
            outer,
            text=disaster_label(name),
            anchor="w",
            font=("Arial", 12, "bold"),
            bg=WHITE,
            fg=BLUE,
            activebackground=LIGHT_BLUE,
            activeforeground=BLUE,
            relief="flat",
            bd=0,
            padx=12,
            pady=13,
            cursor="hand2",
            command=lambda n=name: self.toggle_disaster(n)
        )
        button.pack(fill="x")

        info = tk.Frame(
            outer,
            bg=WHITE,
            padx=18,
            pady=12
        )

        self.cards[name] = {
            "info": info,
            "button": button,
            "open": False
        }

    def toggle_disaster(self, name):
        data = DISASTERS[name]
        card = self.cards[name]

        if card["open"]:
            card["info"].pack_forget()
            card["open"] = False
            card["button"].config(text=disaster_label(name))
            return

        clear_frame(card["info"])

        desc = tk.Label(
            card["info"],
            text=data["description"],
            font=("Arial", 13),
            bg=WHITE,
            fg=TEXT,
            justify="left",
            anchor="w"
        )
        desc.pack(fill="x", pady=(0, 8))
        wrap_to_width(desc, 1000)

        # Before / During / After side by side to use the full width
        columns = tk.Frame(card["info"], bg=WHITE)
        columns.pack(fill="x")

        for c in range(3):
            columns.grid_columnconfigure(c, weight=1, uniform="phase")

        for c, (title, key) in enumerate([
            ("BEFORE", "before"),
            ("DURING", "during"),
            ("AFTER", "after")
        ]):
            col = tk.Frame(columns, bg=WHITE)
            col.grid(row=0, column=c, sticky="new", padx=8)

            tk.Label(
                col,
                text=title,
                font=("Arial", 14, "bold"),
                bg=PHASE_COLORS[title],
                fg=WHITE,
                anchor="w",
                padx=10,
                pady=4
            ).pack(fill="x", pady=(0, 6))

            for item in data[key]:
                label = tk.Label(
                    col,
                    text="• " + item,
                    font=("Arial", 13),
                    bg=WHITE,
                    fg=TEXT,
                    justify="left",
                    anchor="w"
                )
                label.pack(fill="x", pady=2)
                wrap_to_width(label, 500)

        tk.Label(
            card["info"],
            text="Source: " + data["source"],
            font=("Arial", 10, "italic"),
            bg=WHITE,
            fg=GRAY
        ).pack(anchor="w", pady=(10, 0))

        card["info"].pack(fill="x")
        card["open"] = True
        card["button"].config(text=disaster_label(name, True))


# =========================================================
# READY KIT  (card / grid layout)
# =========================================================

class ReadyKitScreen(ScrollPage):

    def __init__(self, parent, controller):
        super().__init__(parent, bg=BACKGROUND)

        create_navigation(self, controller, "ReadyKitScreen")
        create_footer(self)
        self.setup_scroll()

        page_title(
            self.content,
            "Emergency Ready Kit",
            "Check the items that should be prepared for each emergency."
        )

        grid = tk.Frame(self.content, bg=BACKGROUND)
        grid.pack(fill="x")

        grid.grid_columnconfigure(0, weight=1, uniform="kit")
        grid.grid_columnconfigure(1, weight=1, uniform="kit")

        categories = list(KIT_ITEMS.items())

        # General kit: full width on top, items in 3 columns
        general_title, general_items = categories[0]
        self.make_kit_card(
            grid, general_title, general_items, columns=3
        ).grid(row=0, column=0, columnspan=2, sticky="nsew", pady=6)

        # Disaster-specific kits: 2 cards per row
        for i, (title, items) in enumerate(categories[1:]):
            self.make_kit_card(
                grid, title, items, columns=2
            ).grid(
                row=1 + i // 2,
                column=i % 2,
                sticky="nsew",
                padx=(0, 6) if i % 2 == 0 else (6, 0),
                pady=6
            )

    def make_kit_card(self, parent, title, items, columns):
        card = tk.Frame(
            parent,
            bg=WHITE,
            padx=16,
            pady=14,
            highlightbackground=BORDER,
            highlightthickness=1
        )

        header = tk.Frame(card, bg=WHITE)
        header.pack(fill="x", pady=(0, 6))

        tk.Label(
            header,
            text=title,
            font=("Arial", 15, "bold"),
            bg=WHITE,
            fg=BLUE if title == "General Emergency Kit" else RED
        ).pack(side="left")

        counter = tk.Label(
            header,
            text=f"0 / {len(items)} packed  •  0%",
            font=("Arial", 10, "bold"),
            bg=WHITE,
            fg=GRAY
        )
        counter.pack(side="right")

        # progress bar (drawn on a Canvas)
        bar = tk.Canvas(
            card, height=8, bg=BORDER, highlightthickness=0
        )
        bar.pack(fill="x", pady=(0, 10))

        chips = tk.Frame(card, bg=WHITE)
        chips.pack(fill="x")

        for c in range(columns):
            chips.grid_columnconfigure(c, weight=1, uniform="chip")

        variables = []

        def draw_bar(event=None):
            bar.delete("all")
            done = sum(1 for v in variables if v.get())
            width = bar.winfo_width()
            filled = int(width * done / len(items)) if items else 0
            bar.create_rectangle(
                0, 0, filled, 8, width=0,
                fill=GREEN if done == len(items) else BLUE
            )

        def update():
            done = sum(1 for v in variables if v.get())
            percent = round(100 * done / len(items)) if items else 0
            counter.config(
                text=f"{done} / {len(items)} packed  •  {percent}%",
                fg=GREEN if done == len(items) else GRAY
            )
            draw_bar()

        bar.bind("<Configure>", draw_bar)

        for i, item in enumerate(items):
            var = tk.BooleanVar()
            variables.append(var)

            chip = tk.Frame(
                chips,
                bg=WHITE,
                highlightbackground="#AAB7C8",
                highlightthickness=1,
                bd=0
            )
            chip.grid(
                row=i // columns,
                column=i % columns,
                sticky="nsew",
                padx=4,
                pady=4
            )

            tk.Checkbutton(
                chip,
                text=item,
                variable=var,
                command=update,
                font=("Arial", 11),
                bg=WHITE,
                fg=TEXT,
                activebackground=WHITE,
                selectcolor=LIGHT_BLUE,
                anchor="w",
                justify="left",
                indicatoron=True,
                padx=10,
                pady=10,
                cursor="hand2"
            ).pack(fill="x")

        return card


# =========================================================
# HOTLINES
# =========================================================

class HotlinesScreen(ScrollPage):

    def __init__(self, parent, controller):
        super().__init__(parent, bg=BACKGROUND)

        create_navigation(self, controller, "HotlinesScreen")
        create_footer(self)
        self.setup_scroll()

        page_title(
            self.content,
            "Emergency Hotlines",
            "DAGUPAN CITY",
            color=RED
        )

        grid = make_grid(self.content, 2)

        for i, (office, number) in enumerate(HOTLINES):
            place_card(self.make_hotline(grid, office, number), i)

    def make_hotline(self, parent, office, number):
        card = tk.Frame(
            parent,
            bg=WHITE,
            padx=16,
            pady=14,
            highlightbackground=BORDER,
            highlightthickness=1
        )

        icon_tile(card, "☎", RED if office.startswith("NATIONAL") else BLUE
                  ).pack(side="left", anchor="n", padx=(0, 14))

        # Button first so it keeps its space when the window is narrow
        make_button(
            card,
            "CALL",
            lambda n=number: self.call_number(n),
            bg=RED
        ).pack(side="right", padx=(8, 0))

        left = tk.Frame(card, bg=WHITE)
        left.pack(side="left", fill="x", expand=True)

        name = tk.Label(
            left,
            text=office,
            font=("Arial", 11, "bold"),
            bg=WHITE,
            fg=BLUE,
            anchor="w",
            justify="left"
        )
        name.pack(fill="x")
        wrap_to_width(name, 500)

        tk.Label(
            left,
            text=number,
            font=("Arial", 16, "bold"),
            bg=WHITE,
            fg=RED,
            anchor="w"
        ).pack(anchor="w", pady=(3, 0))

        return card

    def call_number(self, number):
        clean = number.split("/")[0].strip()

        try:
            import webbrowser
            webbrowser.open("tel:" + clean)
        except Exception:
            messagebox.showinfo(
                "Emergency Hotline",
                "Please call:\n\n" + number
            )


# =========================================================
# FIRST AID
# =========================================================

class FirstAidScreen(ScrollPage):

    def __init__(self, parent, controller):
        super().__init__(parent, bg=BACKGROUND)

        create_navigation(self, controller, "FirstAidScreen")
        create_footer(self)
        self.setup_scroll()

        page_title(
            self.content,
            "First Aid Procedure",
            "Basic emergency response guidance. Contact emergency "
            "responders for serious injuries."
        )

        banner = tk.Frame(self.content, bg="#FDECEA", padx=18, pady=10,
                          highlightbackground=LIGHT_RED, highlightthickness=1)
        banner.pack(fill="x", pady=(0, 10))

        warning = tk.Label(
            banner,
            text=(
                "⚠  SAFETY FIRST: check that the area is safe before helping, "
                "and call 911 or the Emergency Hotlines for serious injuries."
            ),
            font=("Arial", 11, "bold"), bg="#FDECEA", fg=RED,
            justify="left", anchor="w"
        )
        warning.pack(fill="x")
        wrap_to_width(warning, 1000)

        grid = make_grid(self.content, 2)

        for i, (title, text) in enumerate(FIRST_AID):
            box = tk.Frame(
                grid,
                bg=WHITE,
                padx=16,
                pady=14,
                highlightbackground=BORDER,
                highlightthickness=1
            )
            place_card(box, i)

            tk.Label(
                box,
                text=str(i + 1),
                font=("Arial", 13, "bold"),
                bg=RED,
                fg=WHITE,
                width=3,
                pady=5
            ).pack(side="left", anchor="n", padx=(0, 14))

            detail = tk.Frame(box, bg=WHITE)
            detail.pack(side="left", fill="x", expand=True)

            tk.Label(
                detail,
                text=title,
                font=("Arial", 12, "bold"),
                bg=WHITE,
                fg=BLUE,
                anchor="w"
            ).pack(fill="x")

            body = tk.Label(
                detail,
                text=text,
                font=("Arial", 10),
                bg=WHITE,
                fg=TEXT,
                justify="left",
                anchor="w"
            )
            body.pack(fill="x", pady=(4, 0))
            wrap_to_width(body, 600)

        source = tk.Frame(
            self.content,
            bg=LIGHT_BLUE,
            padx=18,
            pady=12
        )
        source.pack(fill="x", pady=12)

        note = tk.Label(
            source,
            text=(
                "SOURCE: World Health Organization (WHO) & International "
                "Committee of the Red Cross (ICRC). Basic Emergency Care: "
                "Approach to the Acutely Ill and Injured."
            ),
            font=("Arial", 9, "italic"),
            bg=LIGHT_BLUE,
            fg=GRAY,
            justify="left",
            anchor="w"
        )
        note.pack(fill="x")
        wrap_to_width(note, 1000)


# =========================================================
# EVACUATION AREA - USER VIEW  (reads from the database)
# =========================================================

class EvacuationScreen(ScrollPage):

    def __init__(self, parent, controller):
        super().__init__(parent, bg=BACKGROUND)

        self.controller = controller

        create_navigation(self, controller, "EvacuationScreen")
        create_footer(self)
        self.setup_scroll()

        page_title(
            self.content,
            "Evacuation Areas",
            "View available evacuation locations. Always follow the "
            "latest instructions from local authorities."
        )

        self.list_frame = tk.Frame(
            self.content,
            bg=BACKGROUND
        )
        self.list_frame.pack(fill="x")

        self.refresh()

    def refresh(self):
        if not hasattr(self, "list_frame"):
            return

        clear_frame(self.list_frame)

        areas = database.get_evacuation_areas()

        if not areas:
            tk.Label(
                self.list_frame,
                text="No evacuation areas currently listed.",
                font=("Arial", 12),
                bg=WHITE,
                fg=GRAY,
                padx=20,
                pady=20
            ).pack(fill="x")
            return

        grid = make_grid(self.list_frame, 2)

        for i, item in enumerate(areas):
            box = make_card(grid, padx=0, pady=0)
            place_card(box, i)

            header = tk.Frame(box, bg=BLUE, padx=16, pady=10)
            header.pack(fill="x")

            tk.Label(
                header,
                text="CAPACITY: " + format_capacity(item.get("capacity", "")).upper(),
                font=("Arial", 9, "bold"),
                bg=WHITE,
                fg=BLUE,
                padx=8,
                pady=2
            ).pack(side="right", anchor="n", padx=(8, 0))

            name = tk.Label(
                header,
                text=item["name"],
                font=("Arial", 14, "bold"),
                bg=BLUE,
                fg=WHITE,
                anchor="w",
                justify="left"
            )
            name.pack(side="left", fill="x", expand=True)
            wrap_to_width(name, 500)

            body = tk.Frame(box, bg=WHITE, padx=16, pady=12)
            body.pack(fill="both", expand=True)

            for label, value in (
                ("Barangay", item.get("barangay", "")),
                ("Address", item.get("location", "")),
                ("Capacity", format_capacity(item.get("capacity", ""))),
                ("Notes", item.get("notes", ""))
            ):
                row = tk.Frame(body, bg=WHITE)
                row.pack(fill="x", pady=3)

                tk.Label(
                    row,
                    text=label,
                    font=("Arial", 11, "bold"),
                    bg=WHITE,
                    fg=GRAY,
                    width=9,
                    anchor="nw"
                ).pack(side="left", anchor="n")

                text = tk.Label(
                    row,
                    text=value or "-",
                    font=("Arial", 13),
                    bg=WHITE,
                    fg=TEXT,
                    justify="left",
                    anchor="w"
                )
                text.pack(side="left", fill="x", expand=True)
                wrap_to_width(text, 600)


# =========================================================
# EMERGENCY REPORT
# =========================================================

class EmergencyReportScreen(ScrollPage):

    def __init__(self, parent, controller):
        super().__init__(parent, bg=BACKGROUND)

        self.controller = controller
        self.photo_path = ""
        self._sending = False

        create_navigation(self, controller, "EmergencyReportScreen")
        create_footer(self)
        self.setup_scroll()

        tk.Label(
            self.content,
            text="Emergency Report",
            font=("Arial", 25, "bold"),
            bg=BACKGROUND,
            fg=RED
        ).pack(anchor="w")

        note = tk.Frame(self.content, bg=BACKGROUND)
        note.pack(anchor="w", pady=(3, 8))

        tk.Label(
            note,
            text="Provide accurate information about the emergency. "
                 "Fields marked with ",
            font=("Arial", 13),
            bg=BACKGROUND,
            fg=GRAY
        ).pack(side="left")

        tk.Label(
            note,
            text="*",
            font=("Arial", 14, "bold"),
            bg=BACKGROUND,
            fg=RED
        ).pack(side="left")

        tk.Label(
            note,
            text=" are required.",
            font=("Arial", 13),
            bg=BACKGROUND,
            fg=GRAY
        ).pack(side="left")

        # Honest notice about what "Send Report" does
        notice = tk.Frame(self.content, bg=LIGHT_BLUE, padx=14, pady=8)
        notice.pack(fill="x", pady=(0, 10))

        notice_text = tk.Label(
            notice,
            text=(
                "Your report is saved in this system for administrators to "
                "review. It is not automatically sent to any organization. "
                "For urgent emergencies, call 911 or the Emergency "
                "Hotlines right away."
            ),
            font=("Arial", 11),
            bg=LIGHT_BLUE,
            fg=TEXT,
            justify="left",
            anchor="w"
        )
        notice_text.pack(fill="x")
        wrap_to_width(notice_text, 1000)

        form = tk.Frame(
            self.content,
            bg=WHITE,
            padx=22,
            pady=16,
            highlightbackground=BORDER,
            highlightthickness=1
        )
        form.pack(fill="x")

        form.grid_columnconfigure(0, weight=1, uniform="f")
        form.grid_columnconfigure(1, weight=1, uniform="f")

        # Validators (restrict what can be typed)
        self.v_name = (self.register(self.valid_name), "%P")
        self.v_contact = (self.register(self.valid_contact), "%P")
        self.v_location = (self.register(self.valid_location), "%P")
        self.v_barangay = (self.register(self.valid_barangay), "%P")

        self.form_heading(form, 0, "1.  Reporter Information")
        self.form_heading(form, 2, "2.  Incident Details")
        self.form_heading(form, 6, "3.  Photo Evidence (optional)")

        # Row 1: Name | Contact
        self.name = self.field(
            self.cell(form, 1, 0, "Name"), self.v_name
        )
        self.contact = self.field(
            self.cell(form, 1, 1, "Contact Number"), self.v_contact
        )

        # Row 1: Barangay | Emergency type
        box = self.cell(form, 3, 0, "Barangay / Area")
        self.barangay = ttk.Combobox(
            box,
            values=BARANGAYS,
            font=("Arial", 14),
            state="readonly",
            height=10
        )
        self.barangay.set(BARANGAY_PLACEHOLDER)
        self.barangay.pack(fill="x", pady=(4, 0), ipady=3)

        box = self.cell(form, 3, 1, "Emergency Type")
        self.emergency = ttk.Combobox(
            box,
            values=EMERGENCY_TYPES,
            state="readonly",
            font=("Arial", 12)
        )
        self.emergency.set(TYPE_PLACEHOLDER)
        self.emergency.pack(fill="x", pady=(4, 0), ipady=3)

        # Row 2: Location (full width)
        self.location = self.field(
            self.cell(form, 4, 0, "Exact Location / Landmark", span=2),
            self.v_location
        )

        # Row 3: Description (full width)
        box = self.cell(form, 5, 0, "Description", span=2)
        self.description = tk.Text(
            box,
            height=5,
            font=("Arial", 12),
            wrap="word"
        )
        self.description.pack(fill="x", pady=(4, 0))

        # Row 4: Photo + buttons
        bottom = tk.Frame(form, bg=WHITE)
        bottom.grid(row=7, column=0, columnspan=2, sticky="ew", pady=(10, 0))

        make_button(
            bottom,
            "IMPORT PHOTO",
            self.import_photo,
            bg=BLUE
        ).pack(side="left")

        self.photo_label = tk.Label(
            bottom,
            text="No photo selected (optional)",
            font=("Arial", 11),
            bg=WHITE,
            fg=GRAY
        )
        self.photo_label.pack(side="left", padx=12)

        self.send_btn = make_button(
            bottom,
            "SEND REPORT",
            self.submit_report,
            bg=RED
        )
        self.send_btn.config(padx=34, pady=12, font=("Arial", 13, "bold"))
        self.send_btn.pack(side="right")

        make_button(
            bottom,
            "CLEAR FORM",
            self.clear_form,
            bg=GRAY
        ).pack(side="right", padx=10)

    # -----------------------------------------------------
    # Form helpers
    # -----------------------------------------------------

    def cell(self, form, row, col, label, span=1):
        box = tk.Frame(form, bg=WHITE)
        box.grid(
            row=row,
            column=col,
            columnspan=span,
            sticky="ew",
            padx=(0, 8) if (col == 0 and span == 1) else
                 (8, 0) if col == 1 else 0,
            pady=6
        )
        self.make_label(box, label)
        return box

    def form_heading(self, form, row, text):
        heading = tk.Frame(form, bg=WHITE)
        heading.grid(row=row, column=0, columnspan=2, sticky="ew",
                     pady=(10, 2))

        tk.Label(
            heading, text=text, font=("Arial", 14, "bold"),
            bg=WHITE, fg=BLUE
        ).pack(anchor="w")

        tk.Frame(heading, height=2, bg=LIGHT_BLUE).pack(fill="x")

    def make_label(self, parent, text, required=True):
        row = tk.Frame(parent, bg=WHITE)
        row.pack(anchor="w")

        tk.Label(
            row,
            text=text,
            font=("Arial", 12, "bold"),
            bg=WHITE,
            fg=TEXT
        ).pack(side="left")

        if required:
            tk.Label(
                row,
                text=" *",
                font=("Arial", 13, "bold"),
                bg=WHITE,
                fg=RED
            ).pack(side="left")

    def field(self, parent, validator):
        entry = tk.Entry(
            parent,
            font=("Arial", 12),
            validate="key",
            validatecommand=validator
        )
        entry.pack(fill="x", pady=(4, 0), ipady=4)

        return entry

    # -----------------------------------------------------
    # Input validators (called on every keystroke / paste)
    # -----------------------------------------------------

    def valid_name(self, value):
        return (
            len(value) <= 60 and
            re.fullmatch(NAME_RE, value) is not None
        )

    def valid_contact(self, value):
        return (
            len(value) <= CONTACT_LENGTH and
            (value == "" or value.isdigit())
        )

    def valid_location(self, value):
        return (
            len(value) <= 100 and
            re.fullmatch(LOCATION_RE, value) is not None
        )

    def valid_barangay(self, value):
        return (
            len(value) <= 40 and
            re.fullmatch(BARANGAY_RE, value) is not None
        )

    # -----------------------------------------------------
    # Photo
    # -----------------------------------------------------

    def import_photo(self):
        path = filedialog.askopenfilename(
            title="Select Emergency Photo",
            filetypes=[
                ("Image Files", "*.jpg *.jpeg *.png *.gif"),
                ("All Files", "*.*")
            ]
        )

        if path:
            self.photo_path = path
            self.photo_label.config(
                text=os.path.basename(path),
                fg=TEXT
            )

    # -----------------------------------------------------
    # Validation (returns a dict of clean values, or None)
    # -----------------------------------------------------

    def collect_and_validate(self):
        name = " ".join(self.name.get().split())
        contact = self.contact.get().strip()
        barangay = self.barangay.get().strip()
        location = " ".join(self.location.get().split())
        emergency = self.emergency.get()
        description = " ".join(self.description.get("1.0", "end").split())

        def warn(title, message, focus=None):
            messagebox.showwarning(title, message)
            if focus is not None:
                focus.focus_set()
            return None

        if not name:
            return warn("Missing Information",
                        "Please enter your name.", self.name)

        if not re.search(r"[A-Za-zÑñ]{2}", name):
            return warn("Invalid Name",
                        "Please enter your full name (letters only).",
                        self.name)

        if not contact:
            return warn("Missing Information",
                        "Please enter your contact number.", self.contact)

        if (
            len(contact) != CONTACT_LENGTH or
            not contact.isdigit() or
            not contact.startswith("09")
        ):
            return warn(
                "Invalid Contact",
                "Contact number must be 11 digits and start with 09.\n"
                "Example: 09123456789",
                self.contact
            )

        if not barangay or barangay == BARANGAY_PLACEHOLDER:
            return warn("Missing Information",
                        "Please select your Barangay / Area.",
                        self.barangay)

        for official in BARANGAYS:
            if official.lower() == barangay.lower():
                barangay = official
                break

        if not location:
            return warn("Missing Information",
                        "Please enter the exact location or landmark.",
                        self.location)

        if emergency == TYPE_PLACEHOLDER:
            return warn("Missing Information",
                        "Please select an emergency type.", self.emergency)

        if not description:
            return warn("Missing Information",
                        "Please enter a description.", self.description)

        if len(description) < 10:
            return warn(
                "Description Too Short",
                "Please describe the emergency in at least 10 characters.",
                self.description
            )

        return {
            "name": name,
            "contact": contact,
            "barangay": barangay,
            "location": location,
            "emergency": emergency,
            "description": description,
            "photo": self.photo_path
        }

    # -----------------------------------------------------
    # Send Report
    # -----------------------------------------------------

    def submit_report(self):
        if self._sending:          # ignore repeated clicks
            return

        data = self.collect_and_validate()

        if data is None:
            return

        self._sending = True
        self.send_btn.config(state="disabled", text="SENDING...")

        try:
            user_id = self.controller.current_user["id"]

            duplicate = database.find_duplicate(data, user_id)

            if duplicate:
                messagebox.showwarning(
                    "Duplicate Report",
                    "An identical report was already submitted and is "
                    f"still active (Report ID: {duplicate['report_id']}).\n\n"
                    "The duplicate was not saved."
                )
                return

            preview = data["description"]
            if len(preview) > 250:
                preview = preview[:250] + "..."

            confirmed = messagebox.askyesno(
                "Review Your Report",
                "Please review your report:\n\n"
                f"Name: {data['name']}\n"
                f"Contact: {data['contact']}\n"
                f"Barangay / Area: {data['barangay']}\n"
                f"Location: {data['location']}\n"
                f"Emergency Type: {data['emergency']}\n"
                f"Description: {preview}\n"
                "Photo: " + (
                    os.path.basename(data["photo"])
                    if data["photo"] else "None"
                ) + "\n\n"
                "This report will be SAVED LOCALLY in this system. It will "
                "not be sent to any organization automatically.\n\n"
                "Send this report?"
            )

            if not confirmed:
                return

            try:
                report = database.create_report(data, user_id)
            except PermissionError as error:
                messagebox.showerror("Cannot Send Report", str(error))
                return

            messagebox.showinfo(
                "Report Saved",
                f"Your report was saved locally.\n\n"
                f"Report ID: {report['report_id']}\n"
                f"Status: {report['status']}\n\n"
                "This is a local (simulated) submission. It has NOT been "
                "transmitted to any organization. For urgent emergencies, "
                "call 911 or the Emergency Hotlines."
            )

            self.clear_form()

        finally:
            self.after(800, self._unlock_send)

    def _unlock_send(self):
        self._sending = False
        self.send_btn.config(state="normal", text="SEND REPORT")

    def clear_form(self):
        self.name.delete(0, "end")
        self.contact.delete(0, "end")
        self.barangay.set(BARANGAY_PLACEHOLDER)
        self.barangay["values"] = BARANGAYS
        self.location.delete(0, "end")
        self.emergency.set(TYPE_PLACEHOLDER)
        self.description.delete("1.0", "end")

        self.photo_path = ""
        self.photo_label.config(
            text="No photo selected (optional)",
            fg=GRAY
        )


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":

    database.init_db()

    app = App()

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
