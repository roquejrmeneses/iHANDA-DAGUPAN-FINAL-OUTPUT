"""
iHANDA Dagupan - shared code used by BOTH the user app and the admin app.
(colors, disaster/hotline/first-aid data, UI helpers, login/register layout)
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime
import os
import re

import database
from database import (
    REPORT_STATUSES, UNASSIGNED, RESPONSE_ORGANIZATIONS, DISPATCH_RECIPIENTS
)


# =========================================================
# COLORS
# =========================================================

BLUE = "#0D47A1"
DARK_BLUE = "#08306B"
RED = "#C62828"
LIGHT_RED = "#E53935"
LIGHT_BLUE = "#EAF3FA"
BACKGROUND = "#F5F6FA"
WHITE = "#FFFFFF"
TEXT = "#222222"
GRAY = "#666666"
BORDER = "#D9DEE7"
GREEN = "#2E7D32"
ORANGE = "#E65100"


# =========================================================
# WELCOME TEXT (login + register)
# =========================================================

WELCOME_TITLE = "WELCOME TO iHANDA DAGUPAN"
WELCOME_TEXT = (
    "Disaster preparedness, safety guides, evacuation information, and "
    "emergency reporting for Dagupan City."
)


# =========================================================
# INPUT RULES (Emergency Report)
# =========================================================

BARANGAY_PLACEHOLDER = "Select Barangay / Area"
TYPE_PLACEHOLDER = "Select Emergency Type"

NAME_RE = r"[A-Za-zÑñ .'\-]*"
LOCATION_RE = r"[A-Za-z0-9Ññ .,#'&()/\-]*"
BARANGAY_RE = r"[A-Za-z0-9Ññ .,&'\-]*"

CONTACT_LENGTH = 11

EMERGENCY_TYPES = ["Flood", "Earthquake", "Fire", "Tsunami", "Other"]


# =========================================================
# DISASTER INFORMATION
# =========================================================

DISASTERS = {
    "Flood": {
        "description": (
            "A flood is the overflowing or accumulation of water that "
            "covers areas that are normally not submerged. Flooding can "
            "be caused by excessive rainfall, overflowing rivers and "
            "other bodies of water, and drainage problems."
        ),
        "before": [
            "Know if your location is prone to flooding.",
            "Monitor weather conditions and flood warnings.",
            "Know your family's evacuation area and route.",
            "Prepare food and drinking water.",
            "Prepare a flashlight, radio, extra batteries, and first aid kit.",
            "Store important belongings above the expected flood level."
        ],
        "during": [
            "Move to a safe area when evacuation is necessary.",
            "Avoid areas subject to sudden flooding.",
            "Do not cross dangerous rivers or flowing streams.",
            "Be careful around flooded roads and bridges.",
            "Listen to emergency instructions.",
            "Drink clean or preferably boiled water."
        ],
        "after": [
            "Re-enter buildings with caution.",
            "Watch for broken electrical wires.",
            "Do not eat contaminated food or drink contaminated water.",
            "Report broken utility lines.",
            "Do not use electrical appliances until checked.",
            "Continue following official instructions."
        ],
        "source": "DOST-PAGASA - Flood Safety Guidelines"
    },

    "Earthquake": {
        "description": (
            "An earthquake is the shaking of the ground caused by sudden "
            "movement beneath the Earth's surface. Strong earthquakes "
            "can damage buildings and other structures."
        ),
        "before": [
            "Prepare an emergency kit.",
            "Secure heavy furniture and appliances.",
            "Fasten hanging objects.",
            "Know safe places inside your home, school, or workplace.",
            "Prepare a family communication and meeting plan."
        ],
        "during": [
            "DROP to the ground.",
            "COVER your head and body under a sturdy table or protect your head and neck.",
            "HOLD until the shaking stops.",
            "Stay away from windows and objects that may fall."
        ],
        "after": [
            "Be prepared for possible aftershocks.",
            "Stay away from damaged buildings.",
            "Do not re-enter damaged buildings unless declared safe.",
            "Watch for cracks and possible landslides.",
            "Follow official announcements and instructions."
        ],
        "source": "DOST-PHIVOLCS – Earthquake Safety Guidelines"
    },

    "Fire": {
        "description": (
            "Fire is a rapid chemical reaction that produces heat and light. "
            "An uncontrolled fire can spread quickly and cause damage to "
            "people and property."
        ),
        "before": [
            "Know the emergency exits.",
            "Keep exits clear.",
            "Know the location of fire extinguishers.",
            "Prepare an evacuation plan.",
            "Know the designated assembly area."
        ],
        "during": [
            "Stay calm.",
            "Follow the emergency evacuation route.",
            "Do not block exits.",
            "Do not use elevators during evacuation.",
            "Do not return for personal belongings.",
            "Follow instructions from firefighters and emergency responders."
        ],
        "after": [
            "Do not immediately return to the building.",
            "Wait for authorities to determine if it is safe.",
            "Stay away from damaged structures.",
            "Follow emergency responder instructions."
        ],
        "source": "Bureau of Fire Protection – Fire Safety Guidelines"
    },

    "Tsunami": {
        "description": (
            "A tsunami is a series of sea waves commonly generated by "
            "undersea earthquakes. It can affect coastal areas and "
            "cause dangerous flooding."
        ),
        "before": [
            "Know if your community is near a tsunami-prone coastal area.",
            "Know your evacuation route.",
            "Identify higher ground or safer areas.",
            "Prepare an emergency kit.",
            "Learn the natural warning signs."
        ],
        "during": [
            "SHAKE – A strong earthquake is felt.",
            "DROP – The sea level suddenly rises or falls.",
            "ROAR – An unusual roaring sound from the sea may be heard.",
            "If you feel a strong earthquake near the coast, move inland or to higher ground.",
            "Follow official tsunami warnings."
        ],
        "after": [
            "Stay away from beaches and coastal areas.",
            "Do not go to the shoreline to watch the waves.",
            "Do not return until authorities say it is safe.",
            "Continue following official tsunami warnings."
        ],
        "source": "DOST-PHIVOLCS – Tsunami Safety and Preparedness"
    }
}


# =========================================================
# READY KIT
# =========================================================

KIT_ITEMS = {
    "General Emergency Kit": [
        "Drinking water",
        "Ready-to-eat food",
        "Flashlight",
        "Extra batteries",
        "First aid kit",
        "Battery-powered radio",
        "Power bank",
        "Whistle",
        "Important documents",
        "Emergency contact list",
        "Medicines",
        "Extra clothes",
        "Hygiene supplies",
        "Cash",
        "Face masks"
    ],

    "Flood Kit": [
        "Drinking water",
        "Ready-to-eat food",
        "Waterproof bag",
        "Flashlight",
        "Extra batteries",
        "Whistle",
        "First aid kit",
        "Power bank",
        "Emergency contact list",
        "Extra clothes",
        "Rubber boots if available"
    ],

    "Earthquake Kit": [
        "First aid kit",
        "Flashlight",
        "Extra batteries",
        "Whistle",
        "Battery-powered radio",
        "Power bank",
        "Water",
        "Ready-to-eat food",
        "Emergency contact list",
        "Sturdy shoes"
    ],

    "Fire Emergency Kit": [
        "Flashlight",
        "Whistle",
        "First aid kit",
        "Face masks",
        "Emergency contact list",
        "Important documents",
        "Water",
        "Power bank"
    ],

    "Tsunami Kit": [
        "Drinking water",
        "Ready-to-eat food",
        "Flashlight",
        "Extra batteries",
        "Whistle",
        "First aid kit",
        "Battery-powered radio",
        "Power bank",
        "Emergency contact list",
        "Extra clothes"
    ]
}


# =========================================================
# EMERGENCY HOTLINES
# =========================================================

HOTLINES = [
    ("NATIONAL EMERGENCY HOTLINE", "911"),
    ("CDRRMO", "0968-444-9598 / (075) 540-0363"),
    ("DAGUPAN CITY POLICE STATION", "0933-502-4899 / (075) 529-5604"),
    ("DAGUPAN CITY FIRE STATION", "0917-184-2611"),
    ("PANDA VOLUNTEER FIRE BRIGADE", "0932-548-1545"),
    ("PHILIPPINE RED CROSS", "0928-559-2701 / (075) 632-3296"),
    ("PNP MARITIME GROUP", "0967-008-0092"),
    ("PHILIPPINE COAST GUARD", "0966-415-1949"),
    ("PUBLIC ALERT AND RESPONSE MANAGEMENT CENTER (PARMC)", "0985-187-3333"),
    ("CITY HEALTH OFFICE", "0997-840-1377"),
    ("POSO", "0998-173-9525")
]


# =========================================================
# FIRST AID
# =========================================================

FIRST_AID = [
    (
        "Stay Safe",
        "Make sure the area is safe before helping the injured person. "
        "Avoid fire, electrical wires, unstable structures, or other hazards."
    ),
    (
        "Check the Person",
        "Check if the person is conscious and breathing normally. Look for "
        "severe bleeding, difficulty breathing, or other serious injuries."
    ),
    (
        "Control Severe Bleeding",
        "Apply firm, direct pressure to a bleeding wound using a clean cloth "
        "or dressing. Seek emergency medical assistance if the bleeding is "
        "severe or does not stop."
    ),
    (
        "Handle Injuries Carefully",
        "Keep serious injuries and suspected fractures still. Avoid "
        "unnecessary movement and do not attempt to straighten a broken bone."
    ),
    (
        "Respond to Breathing Problems",
        "If the person is having difficulty breathing or is not breathing "
        "normally, call emergency medical assistance immediately. If trained, "
        "provide appropriate first aid or CPR."
    ),
    (
        "Treat Burns",
        "If the person has a burn, stop the source of the injury when safe "
        "and cool the affected area with clean, cool running water. Seek "
        "medical attention for serious burns."
    ),
    (
        "Get Professional Help",
        "Contact emergency responders and provide information about the "
        "person's condition. Continue monitoring the person until professional "
        "help arrives."
    )
]


# =========================================================
# BARANGAYS
# =========================================================

BARANGAYS = [
    "Bacayao Norte",
    "Bacayao Sur",
    "Barangay I",
    "Barangay II & III",
    "Barangay IV",
    "Bolosan",
    "Bonuan Binloc",
    "Bonuan Boquig",
    "Bonuan Gueset",
    "Calmay",
    "Carael",
    "Caranglaan",
    "Herrero-Perez",
    "Lasip Chico",
    "Lasip Grande",
    "Lomboy",
    "Lucao",
    "Malued",
    "Mamalingling",
    "Mangin",
    "Mayombo",
    "Pantal",
    "Poblacion Oeste",
    "Pogo Chico",
    "Pogo Grande",
    "Pugaro",
    "Salapingao",
    "Salisay",
    "Tambac",
    "Tapuac",
    "Tebeng"
]


# =========================================================
# ORGANIZATION CONTACTS / DISPATCH SUGGESTIONS / STATUSES
# (organization lists themselves live in database.py)
# =========================================================

# organization -> name used in the HOTLINES list
ORG_HOTLINE_NAME = {
    "Dagupan City Disaster Risk Reduction and Management Office (CDRRMO)":
        "CDRRMO",
    "Bureau of Fire Protection (BFP)": "DAGUPAN CITY FIRE STATION",
    "Philippine National Police (PNP)": "DAGUPAN CITY POLICE STATION",
    "Philippine Red Cross": "PHILIPPINE RED CROSS",
    "Philippine Coast Guard": "PHILIPPINE COAST GUARD"
}

DISPATCH_SUGGESTIONS = {
    "flood": [
        "CDRRMO",
        "Barangay Officials / Barangay DRRM Committee",
        "City Health Office / Medical Responders"
    ],
    "earthquake": [
        "CDRRMO",
        "Barangay Officials / Barangay DRRM Committee",
        "City Health Office / Medical Responders"
    ],
    "fire": [
        "Bureau of Fire Protection (BFP)",
        "CDRRMO",
        "Barangay Officials / Barangay DRRM Committee"
    ],
    "tsunami": [
        "CDRRMO",
        "Philippine Coast Guard",
        "Barangay Officials / Barangay DRRM Committee"
    ],
    "other": [
        "CDRRMO",
        "Barangay Officials / Barangay DRRM Committee"
    ]
}

ACTIVE_STATUSES = ["Pending", "Verified", "In Progress"]

STATUS_COLORS = {
    "Pending": RED,
    "Verified": BLUE,
    "In Progress": ORANGE,
    "Resolved": GREEN
}


def org_contact(org):
    """Contact number from the existing HOTLINES list only (never invented)."""
    if org == UNASSIGNED:
        return "-"

    name = ORG_HOTLINE_NAME.get(org)

    for hotline_name, number in HOTLINES:
        if hotline_name == name:
            return number

    return "No contact listed"


# =========================================================
# HELPER FUNCTIONS
# =========================================================

def clear_frame(frame):
    for widget in frame.winfo_children():
        widget.destroy()


BUTTON_HOVER = {
    BLUE: DARK_BLUE,
    RED: LIGHT_RED,
    GREEN: "#1B5E20",
    GRAY: "#444444"
}


def make_button(parent, text, command, bg=BLUE, fg=WHITE):
    return tk.Button(
        parent,
        text=text,
        command=command,
        font=("Arial", 11, "bold"),
        bg=bg,
        fg=fg,
        activebackground=BUTTON_HOVER.get(bg, DARK_BLUE),
        activeforeground=WHITE,
        relief="flat",
        bd=0,
        padx=14,
        pady=8,
        cursor="hand2"
    )


# Typography system (sizes taken from the existing screens)
FONT_PAGE_TITLE = ("Arial", 25, "bold")
FONT_SECTION = ("Arial", 17, "bold")
FONT_CARD_TITLE = ("Arial", 14, "bold")
FONT_BODY = ("Arial", 12)
FONT_SMALL = ("Arial", 10)

PHASE_COLORS = {
    "BEFORE": BLUE,
    "DURING": RED,
    "AFTER": GREEN
}


def disaster_label(name, opened=False):
    return "  " + name


def status_badge(parent, status):
    """Small coloured label showing a report status."""
    return tk.Label(
        parent,
        text=status.upper(),
        font=("Arial", 9, "bold"),
        bg=STATUS_COLORS.get(status, GRAY),
        fg=WHITE,
        padx=8,
        pady=2
    )


def make_card(parent, bg=WHITE, padx=16, pady=14):
    return tk.Frame(
        parent,
        bg=bg,
        padx=padx,
        pady=pady,
        highlightbackground=BORDER,
        highlightthickness=1
    )


def section_heading(parent, text, color=BLUE, bg=BACKGROUND):
    row = tk.Frame(parent, bg=bg)

    tk.Label(
        row, text=text, font=FONT_SECTION, bg=bg, fg=color
    ).pack(side="left")

    tk.Frame(row, height=2, bg=BORDER).pack(
        side="left", fill="x", expand=True, padx=(12, 0), pady=(8, 0)
    )

    return row


def icon_tile(parent, symbol, color, bg=WHITE, size=46):
    """Round coloured icon (Unicode symbol drawn on a Canvas)."""
    canvas = tk.Canvas(
        parent, width=size, height=size, bg=bg, highlightthickness=0
    )
    canvas.create_oval(2, 2, size - 2, size - 2, fill=color, outline=color)
    canvas.create_text(
        size / 2, size / 2, text=symbol, fill=WHITE,
        font=("Arial", int(size * 0.4), "bold")
    )
    return canvas


def walk_widgets(widget):
    yield widget
    for child in widget.winfo_children():
        yield from walk_widgets(child)


def format_capacity(value):
    """Capacity is a number of persons; older text values are shown as-is."""
    value = str(value).strip()
    return f"{value} persons" if value.isdigit() else (value or "-")


def make_clickable(card, command, normal=WHITE, hover=LIGHT_BLUE):
    """Make a whole card (and everything inside it) clickable with hover."""
    def paint(color):
        for widget in walk_widgets(card):
            try:
                widget.config(bg=color)
            except tk.TclError:
                pass

    def on_leave(event):
        x, y = card.winfo_pointerxy()
        inside = card.winfo_containing(x, y)

        if inside is None or inside not in set(walk_widgets(card)):
            paint(normal)

    for widget in walk_widgets(card):
        widget.config(cursor="hand2")
        widget.bind("<Button-1>", lambda e: command())
        widget.bind("<Enter>", lambda e: paint(hover))
        widget.bind("<Leave>", on_leave)


def wrap_to_width(label, max_width=1100, padding=6):
    """Wrap text to the label's width, but never wider than max_width."""
    label.bind(
        "<Configure>",
        lambda e: label.config(
            wraplength=max(min(e.width - padding, max_width), 80)
        )
    )


def make_grid(parent, columns=2):
    """Frame whose columns share the width equally (card layout)."""
    grid = tk.Frame(parent, bg=BACKGROUND)
    grid.pack(fill="x")

    for c in range(columns):
        grid.grid_columnconfigure(c, weight=1, uniform="cards")

    return grid


def place_card(widget, index, columns=2):
    row, col = divmod(index, columns)
    widget.grid(
        row=row,
        column=col,
        sticky="nsew",
        padx=(0 if col == 0 else 6, 0 if col == columns - 1 else 6),
        pady=6
    )


def page_title(parent, title, subtitle, color=BLUE):
    tk.Label(
        parent,
        text=title,
        font=("Arial", 25, "bold"),
        bg=BACKGROUND,
        fg=color
    ).pack(anchor="w")

    if subtitle:
        label = tk.Label(
            parent,
            text=subtitle,
            font=("Arial", 11),
            bg=BACKGROUND,
            fg=GRAY,
            justify="left",
            anchor="w"
        )
        label.pack(fill="x", pady=(2, 12))
        wrap_to_width(label, 1000)


def create_footer(parent):
    footer = tk.Frame(parent, bg=DARK_BLUE, height=34)
    footer.pack(side="bottom", fill="x")
    footer.pack_propagate(False)

    tk.Label(
        footer,
        text="© 2026 iHANDA Dagupan | Disaster Preparedness for Dagupan City",
        font=("Arial", 8),
        bg=DARK_BLUE,
        fg=WHITE
    ).pack(pady=8)


def load_photo_preview(path, max_w=260, max_h=150):
    """Return a PhotoImage for the preview, or None if it can't be shown.
    Uses Pillow when installed (JPG/PNG/GIF); otherwise Tkinter's own
    PNG/GIF support."""
    try:
        from PIL import Image, ImageTk
        image = Image.open(path)
        image.thumbnail((max_w, max_h))
        return ImageTk.PhotoImage(image)
    except Exception:
        pass

    try:
        image = tk.PhotoImage(file=path)
        factor = max(
            1,
            -(-image.width() // max_w),
            -(-image.height() // max_h)
        )
        return image.subsample(factor, factor) if factor > 1 else image
    except Exception:
        return None


# =========================================================
# BASE SCROLLABLE FRAME
# (scrollbar only appears when the content doesn't fit)
# =========================================================

class ScrollPage(tk.Frame):

    def setup_scroll(self, parent=None):
        area = tk.Frame(parent or self, bg=BACKGROUND)
        area.pack(fill="both", expand=True, padx=30, pady=16)

        self.scroll_needed = True

        self.canvas = tk.Canvas(
            area,
            bg=BACKGROUND,
            highlightthickness=0
        )

        self.scrollbar = ttk.Scrollbar(
            area,
            orient="vertical",
            command=self.canvas.yview
        )

        self.content = tk.Frame(
            self.canvas,
            bg=BACKGROUND
        )

        self.window_id = self.canvas.create_window(
            (0, 0),
            window=self.content,
            anchor="nw"
        )

        self.content.bind("<Configure>", self.update_scroll_region)
        self.canvas.bind("<Configure>", self.on_canvas_configure)

        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

    def on_canvas_configure(self, event):
        self.canvas.itemconfig(self.window_id, width=event.width)
        self.update_scroll_region()

    def update_scroll_region(self, event=None):
        bbox = self.canvas.bbox("all")

        if not bbox:
            return

        self.canvas.configure(scrollregion=bbox)

        needed = (bbox[3] - bbox[1]) > self.canvas.winfo_height()

        if needed != self.scroll_needed:
            self.scroll_needed = needed

            if needed:
                self.scrollbar.pack(side="right", fill="y")
            else:
                self.scrollbar.pack_forget()
                self.canvas.yview_moveto(0)

    def mouse_scroll(self, event):
        if not self.scroll_needed:
            return

        self.canvas.yview_scroll(
            int(-event.delta / 120),
            "units"
        )

    def reset_scroll(self):
        self.canvas.yview_moveto(0)
        # re-check whether the scrollbar is needed once the page is shown
        self.after(40, self.update_scroll_region)


# =========================================================
# LOGIN / REGISTER LAYOUT (blue + red, split screen)
# Used by the user Login, Register and the Admin Login.
# Left: blue welcome panel.  Right: white form that fills the space.
# =========================================================

def build_auth_shell(parent, heading, description, bullets,
                     badge="DAGUPAN CITY DISASTER PREPAREDNESS"):
    """Create the split layout and return the (right-hand) form frame."""
    create_footer(parent)

    shell = tk.Frame(parent, bg=WHITE)
    shell.pack(fill="both", expand=True)

    shell.grid_rowconfigure(0, weight=1)
    shell.grid_columnconfigure(0, weight=6, uniform="auth")
    shell.grid_columnconfigure(1, weight=0)
    shell.grid_columnconfigure(2, weight=5, uniform="auth")

    # ---------- left: blue welcome panel ----------
    left = tk.Frame(shell, bg=BLUE)
    left.grid(row=0, column=0, sticky="nsew")

    sos = tk.Frame(left, bg=RED, padx=20, pady=10)
    sos.pack(side="bottom", fill="x", padx=48, pady=(0, 28))

    tk.Label(
        sos, text="IN AN EMERGENCY CALL", font=("Arial", 11, "bold"),
        bg=RED, fg=WHITE
    ).pack(side="left")

    tk.Label(
        sos, text="911", font=("Arial", 26, "bold"), bg=RED, fg=WHITE
    ).pack(side="right")

    inner = tk.Frame(left, bg=BLUE)
    inner.pack(expand=True, fill="x", padx=48, pady=(24, 0))

    tk.Label(
        inner, text=badge, font=("Arial", 10, "bold"),
        bg=BLUE, fg=LIGHT_BLUE
    ).pack(anchor="w")

    title = tk.Label(
        inner, text=heading, font=("Arial", 30, "bold"), bg=BLUE, fg=WHITE,
        justify="left", anchor="w", wraplength=520
    )
    title.pack(fill="x", pady=(8, 10))
    wrap_to_width(title, 640)

    tk.Frame(inner, height=4, width=90, bg=RED).pack(anchor="w", pady=(0, 14))

    text = tk.Label(
        inner, text=description, font=("Arial", 14), bg=BLUE, fg=WHITE,
        justify="left", anchor="w", wraplength=520
    )
    text.pack(fill="x")
    wrap_to_width(text, 640)

    for bullet in bullets:
        tk.Label(
            inner, text="✔  " + bullet, font=("Arial", 12),
            bg=BLUE, fg=LIGHT_BLUE, anchor="w"
        ).pack(fill="x", pady=(10, 0))

    # ---------- middle: red divider with the header's diagonal ----------
    divider = tk.Canvas(shell, width=34, bg=RED, highlightthickness=0)
    divider.grid(row=0, column=1, sticky="ns")

    def draw_divider(event):
        divider.delete("all")
        divider.create_polygon(
            0, 0, 34, 0, 0, event.height, fill=BLUE, outline=BLUE
        )

    divider.bind("<Configure>", draw_divider)

    # ---------- right: white form area ----------
    right = tk.Frame(shell, bg=WHITE)
    right.grid(row=0, column=2, sticky="nsew")

    form = tk.Frame(right, bg=WHITE)
    form.pack(expand=True, fill="x", padx=52, pady=18)

    brand = tk.Frame(form, bg=WHITE)
    brand.pack(fill="x", pady=(0, 10))

    tk.Label(
        brand, text="iHANDA", font=("Arial", 16, "bold"), bg=WHITE, fg=BLUE
    ).pack(side="left")
    tk.Label(
        brand, text=" Dagupan", font=("Arial", 16, "bold"), bg=WHITE, fg=RED
    ).pack(side="left")

    return form


class MessageBar(tk.Frame):
    """Inline message under the form title (hidden when empty)."""

    COLORS = {
        "error": ("#FDECEA", RED),
        "success": ("#E8F5E9", GREEN),
        "info": (LIGHT_BLUE, BLUE)
    }

    def __init__(self, parent):
        super().__init__(parent, bg=WHITE)

        self.label = tk.Label(
            self, font=("Arial", 10, "bold"), justify="left", anchor="w",
            padx=12, pady=8, wraplength=420
        )
        wrap_to_width(self.label, 700, padding=26)
        self.pack(fill="x")

    def show(self, text, kind="error"):
        bg, fg = self.COLORS[kind]
        self.label.config(text=text, bg=bg, fg=fg)
        self.label.pack(fill="x", pady=(0, 10))

    def clear(self):
        self.label.pack_forget()


def auth_field(parent, label, show=None, hint=None):
    """Labelled entry with a border that turns blue on focus.
    Returns (container_frame, entry)."""
    box = tk.Frame(parent, bg=WHITE)

    tk.Label(
        box, text=label, font=("Arial", 10, "bold"), bg=WHITE, fg=TEXT
    ).pack(anchor="w")

    border = tk.Frame(box, bg=BORDER, padx=1, pady=1)
    border.pack(fill="x", pady=(4, 0))

    entry = tk.Entry(
        border, font=("Arial", 12), relief="flat", bd=0,
        highlightthickness=0, show=show or ""
    )
    entry.pack(fill="x", ipady=7, padx=2)

    entry.bind("<FocusIn>", lambda e: border.config(bg=BLUE))
    entry.bind("<FocusOut>", lambda e: border.config(bg=BORDER))

    if hint:
        tk.Label(
            box, text=hint, font=("Arial", 9), bg=WHITE, fg=GRAY,
            anchor="w", justify="left", wraplength=400
        ).pack(fill="x", pady=(3, 0))

    return box, entry


def password_toggle(parent, entries):
    """'Show password' checkbox for one or more password entries."""
    var = tk.BooleanVar(value=False)

    def toggle():
        for entry in entries:
            entry.config(show="" if var.get() else "•")

    return tk.Checkbutton(
        parent, text="Show password", variable=var, command=toggle,
        font=("Arial", 10), bg=WHITE, fg=GRAY, activebackground=WHITE,
        selectcolor=WHITE, cursor="hand2", anchor="w"
    )


def link_button(parent, text, command, fg=BLUE):
    return tk.Button(
        parent, text=text, command=command, font=("Arial", 10, "bold"),
        bg=WHITE, fg=fg, activebackground=WHITE, activeforeground=RED,
        relief="flat", bd=0, cursor="hand2", padx=2, pady=0
    )


def primary_button(parent, text, command, bg=RED):
    button = make_button(parent, text, command, bg=bg)
    button.config(font=("Arial", 12, "bold"), pady=11)
    return button
