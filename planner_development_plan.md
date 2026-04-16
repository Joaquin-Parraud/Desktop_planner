# Desktop Planner for Linux: Development Roadmap

This document outlines the strategy, architecture, and implementation phases for building a native Linux desktop planner with support for titles, dates, and task groupings.

## 1. Project Vision
A lightweight, keyboard-friendly desktop application that allows users to organize tasks with metadata (titles/dates) and logical buckets (groupings).

## 2. Recommended Technical Stack
* **Language:** Python 3 (High developer productivity and extensive library support).
* **GUI Framework:** GTK4 with `PyGObject` (Native Linux look and feel, standard for GNOME/Cinnamon environments).
* **Styling:** CSS (via GTK Style Providers).
* **Storage:** SQLite (Relational database for efficient querying of dates and groupings).
* **Build System:** Meson/Ninja (Standard for modern Linux desktop apps).

## 3. Core Features & Requirements
* **Titles:** Clear, editable headings for every entry.
* **Dates:** Integration with a calendar picker; support for relative dates (e.g., "Today", "Tomorrow").
* **Groupings:** A sidebar-based navigation system to filter tasks by category or project.
* **Linux Integration:** * `.desktop` file for system-wide application launching.
    * System notifications for upcoming deadlines using `libnotify`.

## 4. Implementation Phases

### Phase 1: Environment & Project Setup
* Initialize a Python virtual environment.
* Configure the Meson build system to handle UI files and dependencies.
* Create the main application entry point and a basic window.
#### Success: The window can be opened.

### Phase 2: Data Persistence Layer
* Design the SQLite schema for `tasks` and `groups`.
* Develop a Python module to handle database connections and CRUD operations.
* It has to remain unchanged even if turning off the computer (has to be saved)
* Ensure data is saved automatically on task modification.
#### Success: The tables exist and has data persistance

### Phase 3: UI Architecture
* **Main View:** Use a `Gtk.ColumnView` or `Gtk.ListBox` to display tasks.
* **Sidebar:** Implement a `Gtk.ListBox` for group selection.
* **Task Editor:** Create a modal dialog to input task titles, select dates, and assign groups.
#### The UI can be opened and can create tasks with titles, dates and groups.

### Phase 4: Logic & Features
* Implement filtering logic based on the selected group in the sidebar.
* Add a "Sort by Date" feature to the main view.
* Integrate desktop notifications for tasks marked for the current day.
#### Can sort tasks by date and notifications are functional

### Phase 5: Distribution
* Package the application as a Flatpak or AppImage.
* Add a custom icon and desktop entry file for proper menu integration.
#### The app can be run from "planner" in the application menu.
