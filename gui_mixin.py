"""Mixin for the Tkinter widgets and their event handlers.

Covers building the widget tree (create_widgets), reacting to user
interaction (radio buttons, browse buttons, placeholders), and showing
inline error/info labels in the window.
"""

import tkinter as tk
from tkinter import filedialog, ttk


class GuiMixin:
    """Widget creation and interaction, mixed into Application."""

    def click_radio_button(self):
        """Enable/disable widgets to match the selected radio option.

        Bound to both radio buttons' ``command``. "Option 1" (create a
        new project) enables the destination-folder entry/browse
        button and disables the "use an existing project" widgets, and
        vice-versa for "Option 2". Selecting "Option 2" also attempts
        to connect to PSCAD (``init_pscad``) and refresh the list of
        open projects; if that fails, the selection is reverted back
        to "Option 1" and an error is shown instead of leaving the GUI
        in an inconsistent state.
        """
        selected_option = self.radio_option.get()

        if selected_option == "Option 1":
            # disable option 2 entries
            self.combobox_pscad_projects.config(state=tk.DISABLED)
            self.combobox_pscad_projects.config(foreground="gray")
            self.button_go_to_folder.config(state=tk.DISABLED)
            self.button_refresh.config(state=tk.DISABLED)
            # enable option 1 entries
            self.entry_des_folder.config(state=tk.NORMAL)
            self.button_browse_new_project.config(state=tk.NORMAL)

        elif selected_option == "Option 2":
            self.entry_des_folder.config(state=tk.DISABLED)
            self.button_browse_new_project.config(state=tk.DISABLED)
            self.combobox_pscad_projects.config(state=tk.NORMAL)
            self.button_go_to_folder.config(state=tk.NORMAL)
            self.button_refresh.config(state=tk.NORMAL)

            try:
                # Get self.pscad. Raises Exception if PSCAD is not
                # installed or unlicensed.
                self.init_pscad()
            except Exception as e:
                # exception to display error because does not stop algo
                self.display_error(
                    'Cannot select an available project. ' + str(e))
                self.radio_option.set("Option 1")
                self.click_radio_button()
            else:  # no error
                self.refresh_pscad_projects()
                # set black font only if selected value != placeholder_value
                self.set_combobox_black_foreground(
                    self.combobox_pscad_projects,
                    self.pscad_projects_selected_value,
                    self.combobox_pscad_projects_placeholder)

    def select_folder(self, entry: ttk.Entry):
        """Open a folder-picker dialog and write the result into ``entry``.

        Bound to the "Browse" button for the new-project destination
        folder. Uses the entry's current value as the dialog's starting
        directory. Leaves ``entry`` unchanged if the dialog is
        cancelled.

        :param entry: The ``ttk.Entry`` widget to fill in.
        :type entry: ttk.Entry
        """
        initial_dir = entry.get()  # Get the current folder in the entry
        folder = filedialog.askdirectory(initialdir=initial_dir)
        if folder:
            entry.delete(0, tk.END)
            entry.insert(0, folder)
            # because can be gray if placeholder value
            entry.config(foreground="black")

    def start(self):
        """Build the widget tree and display the GUI."""
        self.create_widgets()

    @staticmethod
    def remove_placeholder(entry: ttk.Entry, placeholder_value: str):
        """Clear ``entry`` if it currently shows its placeholder text.

        Bound to an entry's ``<FocusIn>`` event so the placeholder
        disappears as soon as the user starts typing.

        :param entry: The ``ttk.Entry`` widget to check/clear.
        :type entry: ttk.Entry
        :param placeholder_value: The placeholder text for this entry.
        :type placeholder_value: str
        """
        if entry.get() == placeholder_value:
            entry.delete(0, tk.END)
            entry.config(foreground="black")

    @staticmethod
    def display_placeholder(entry: ttk.Entry, placeholder_value: str):
        """Show ``placeholder_value`` in ``entry`` if it is left empty.

        Bound to an entry's ``<FocusOut>`` event.

        :param entry: The ``ttk.Entry`` widget to fill in.
        :type entry: ttk.Entry
        :param placeholder_value: The placeholder text for this entry.
        :type placeholder_value: str
        """
        if not entry.get():  # if entry empty
            entry.insert(0, placeholder_value)
            entry.config(foreground="gray")

    @staticmethod
    def display_combobox_placeholder(
            combobox: ttk.Combobox,
            combobox_selected_value: tk.StringVar,
            placeholder_value: str
    ):
        """Show ``placeholder_value`` in a combobox if nothing is selected.

        :param combobox: The ``ttk.Combobox`` widget.
        :type combobox: ttk.Combobox
        :param combobox_selected_value: The ``tk.StringVar`` bound to
            the combobox's selected value.
        :type combobox_selected_value: tk.StringVar
        :param placeholder_value: The placeholder text for this
            combobox.
        :type placeholder_value: str
        """
        if not combobox_selected_value.get():  # empty
            combobox_selected_value.set(placeholder_value)
            combobox.config(foreground="gray")

    @staticmethod
    def set_combobox_black_foreground(
            combobox: ttk.Combobox,
            combobox_selected_value: tk.StringVar,
            placeholder_value: str
    ):
        """Switch a combobox's text back to black once it has a real value.

        Bound to a combobox's ``<FocusIn>`` event, and also called
        directly after refreshing the list of PSCAD projects.

        :param combobox: The ``ttk.Combobox`` widget.
        :type combobox: ttk.Combobox
        :param combobox_selected_value: The ``tk.StringVar`` bound to
            the combobox's selected value. Should never actually be
            empty in practice.
        :type combobox_selected_value: tk.StringVar
        :param placeholder_value: The placeholder text for this
            combobox.
        :type placeholder_value: str
        """
        current_value = combobox_selected_value.get()
        if current_value != "" and current_value != placeholder_value:
            combobox.config(foreground="black")

    def create_widgets(self):
        """Build and lay out every widget of the main window.

        Called once, from ``start()``. Builds, in order:

        * the DLL file path row (label, entry, browse button);
        * the "Option 1" row (create a new project: radio button,
          destination-folder entry, browse button);
        * the "Option 2" row (use an open project: radio button,
          project combobox, "go to folder" and "refresh" icon
          buttons);
        * the "Generate PSCAD Model" button.

        Also wires up placeholder text and focus bindings for the
        destination-folder entry and project combobox, and calls
        ``click_radio_button()`` once at the end so the initial widget
        states match the default-selected radio option.
        """
        pady_value = (10, 0)  # 10 top, 0 bottom

        # Row for PSCX file
        self.label_dll_file_path = ttk.Label(self, text="DLL File Path")
        self.entry_dll_file_path = ttk.Entry(self, width=50)
        self.button_browse_pscx_file_path = ttk.Button(
            self, text="Browse", command=lambda: self.open_file(
                self.entry_dll_file_path, '.dll'))

        self.label_dll_file_path.grid(
            row=self.row_index,
            pady=pady_value)  # pady add spaces up and down
        self.entry_dll_file_path.grid(
            row=self.row_index, column=1, pady=pady_value)
        self.button_browse_pscx_file_path.grid(
            row=self.row_index, column=2, pady=pady_value)
        self.row_index += 1

        # Option 1:
        # variable to store the selected value. Default value is option 1
        self.radio_option = tk.StringVar(value="Option 1")
        radio_button1 = ttk.Radiobutton(
            self,
            text="Create New Project",
            variable=self.radio_option,
            value="Option 1",
            # To switch between radio buttons
            command=self.click_radio_button)
        radio_button1.grid(
            row=self.row_index,
            column=0,
            pady=pady_value,
            sticky="w",  # left align radio buttons
            padx=(10, 0))

        # The entry to select a folder as the destination for the new
        # project
        self.entry_des_folder = ttk.Entry(self, width=50)
        self.entry_des_folder.grid(
            row=self.row_index, column=1, pady=pady_value)
        self.entry_des_folder.bind(
            "<FocusIn>",
            lambda event, entry=self.entry_des_folder,
            placeholder=self.entry_des_folder_placeholder:
            self.remove_placeholder(entry, placeholder))
        self.entry_des_folder.bind(
            "<FocusOut>",
            lambda event, entry=self.entry_des_folder,
            placeholder=self.entry_des_folder_placeholder:
            self.display_placeholder(entry, placeholder))
        self.display_placeholder(
            self.entry_des_folder, self.entry_des_folder_placeholder)

        self.entry_des_folder.config(state=tk.DISABLED)

        self.button_browse_new_project = ttk.Button(
            self, text="Browse", command=lambda: self.select_folder(
                self.entry_des_folder))
        self.button_browse_new_project.grid(
            row=self.row_index, column=2, pady=pady_value)
        self.button_browse_new_project.config(state=tk.DISABLED)

        self.row_index += 1

        # Option 2:
        radio_button2 = ttk.Radiobutton(
            self,
            text="Use Available Project",
            variable=self.radio_option,
            value="Option 2",
            command=self.click_radio_button)  # Switching to option 2
        radio_button2.grid(
            row=self.row_index,
            column=0,
            pady=pady_value,
            sticky="w",  # left align
            padx=(10, 0))

        # Variable to store selected value
        self.pscad_projects_selected_value = tk.StringVar()
        self.combobox_pscad_projects = ttk.Combobox(
            self, width=47, textvariable=self.pscad_projects_selected_value)
        self.combobox_pscad_projects.grid(
            row=self.row_index, column=1, pady=pady_value)
        self.combobox_pscad_projects.config(state=tk.DISABLED)
        # to define a default selected value
        self.pscad_projects_selected_value.set("")
        self.display_combobox_placeholder(
            self.combobox_pscad_projects,
            self.pscad_projects_selected_value,
            self.combobox_pscad_projects_placeholder)
        self.combobox_pscad_projects.bind(
            "<FocusIn>",
            lambda event, combobox=self.combobox_pscad_projects,
            value=self.pscad_projects_selected_value,
            placeholder=self.combobox_pscad_projects_placeholder:
            self.set_combobox_black_foreground(
                combobox, value, placeholder))

        # 24x24px PNG icon (base64), refresh symbol
        icon_base64_refresh = (
            'iVBORw0KGgoAAAANSUhEUgAAABgAAAAYCAYAAADgdz34AAAAAXNSR0IArs4c6QAA'
            'AcZJREFUSEvN1cvLTWEUBvDfFyKKhEQGbgPkkhiIAUoiURgwUkwkBiYG/AMykJSJ'
            'xEARMsBAQkoxUC4pykTkVi4xYKLcWrU+bdnv3ufkfOUd7X3Oep9n3Z5n9xng0zfA'
            '+P4LgpXYgVmYiJ94hQc4jSv4XupEUwXTcBYLWtp4F2vwri6uRLAC5zEqLx7FRTxN'
            'kNlYha1Z1WvEnSc4h5mYE7F1BJPxGMNxFRvxpVBFJHAS6/ABe3Esn8eVCG5jMS5j'
            'LX40tOggXmAzFlXiDmN3HcFQvMdnzMtMSviR4dtCF6I9j0oVzMBXPOtAI5H1LmzC'
            '4Iy/h4X9d3ulg7HYloPfj2u9JigW26sKOiZYgn24iRMtQ+5gRH/r4CHm5s1vuIAD'
            'CLW2nRGY0r89dTOYj/s1KKGDGOKnBobxmcQExKr/9qbqDI5gZwXkFk4hPGlPA3is'
            'Zyh+ebZ2WTW2SvARo9M5D2FY+lH4TckqRuISlmZMOO7LEsGNVHGIZkOa1qC0guO4'
            'nh4Vv03FemzHmGxfvMdy/HGa1jRs+gymt0z3TnrR87q4Nh0MwWpsyQ/OpPSeN1lN'
            'zC0q71gHbavY9f9tFXQN2M0M/hk8AH4BquBSGZPuD3sAAAAASUVORK5CYII='
        )
        # 24x24px PNG icon (base64), folder symbol
        icon_base64_go_to_folder = (
            'iVBORw0KGgoAAAANSUhEUgAAABgAAAAYCAQAAABKfvVzAAAAIGNIUk0AAHomAACA'
            'hAAA+gAAAIDoAAB1MAAA6mAAADqYAAAXcJy6UTwAAAACYktHRAD/h4/MvwAAAAd0'
            'SU1FB+cKEQwjJO4wwxUAAAGHSURBVDjLjdM/a1NhFAbw331zo21KapqotBa7qHTR'
            'D2Bx1G/gn0XQzcFFUBA/gNTNRUGcOinYQVz8g4NUXARBXCwOVYMYTNralkZJNfE6'
            '9BprxXifM72H8zzv4Tnn0Atjph2UGUVTEjPGspXnTepIJO4o/U7HoGRCX5p576UE'
            'Z5wTwDE1F61tVDvinUceeuCFe3I4bkXSjY5LcuulORxyVsMJt90y56RBVXvNatsD'
            'Xrlp2VanJKpw3VNH079GXDZpGFxI9afAAU9cI1bQZ9p9Q4JI21VBzqgfKqlIybhI'
            'y4xRhchj45oW5IRuRIJIWVki8tWySFDQMht564o3qVvJJmv/fHfsdz624LVnGUfZ'
            'rxas2pl59rs1gkU7MhN2+Rg0bM9MGFEN6l37/oe8ig9BXVmUiTCguN5S0ZZMhG3y'
            '6sG8QndTe6OibSn4LDaQiTBsVTNYkRjMaOqitaDp+8aL6kn4RNDyxVDGlmrEvpk3'
            'Ye7XRf0DiYJ97hLhsBv6/9rUzYg9d9rSTyFpa7yLVQGQAAAAJXRFWHRkYXRlOmNy'
            'ZWF0ZQAyMDIzLTEwLTE3VDEyOjM1OjI1KzAwOjAwuFkSYAAAACV0RVh0ZGF0ZTpt'
            'b2RpZnkAMjAyMy0xMC0xN1QxMjozNToyNSswMDowMMkEqtwAAAAodEVYdGRhdGU6'
            'dGltZXN0YW1wADIwMjMtMTAtMTdUMTI6MzU6MzYrMDA6MDBjU5EAAAAAAElFTkSu'
            'QmCC'
        )
        self.go_to_folder_image = tk.PhotoImage(
            data=icon_base64_go_to_folder)
        self.refresh_image = tk.PhotoImage(data=icon_base64_refresh)

        self.button_refresh = ttk.Button(
            self,
            image=self.refresh_image,
            command=self.refresh_pscad_projects)

        self.button_go_to_folder = ttk.Button(
            self,
            image=self.go_to_folder_image,
            command=self.go_to_selected_project_folder)
        self.button_refresh.grid(
            row=self.row_index, column=2, pady=pady_value, padx=(0, 40))
        self.button_go_to_folder.grid(
            row=self.row_index, column=2, pady=pady_value, padx=(40, 0))
        self.button_refresh.config(state=tk.DISABLED)
        self.button_go_to_folder.config(state=tk.DISABLED)

        self.row_index += 1

        self.button_generate_pscad_model = ttk.Button(
            self,
            text="Generate PSCAD Model",
            command=self.generate_pscad_model)
        self.button_generate_pscad_model.grid(
            row=self.row_index, column=1, pady=10)

        self.row_index += 1

        self.click_radio_button()  # to change states of entries

        # min width for labels (column 0)
        self.grid_columnconfigure(0, minsize=160)
        # min width for Browse (column 2)
        self.grid_columnconfigure(2, minsize=100)

    def clean_errors_and_info(self):
        """Remove every error/info label currently shown in the window.

        Destroys each label in ``self.list_label_errors`` and
        ``self.list_label_info`` and decrements ``self.row_index``
        accordingly so the next widgets added reuse those grid rows.
        Called at the start of ``generate_pscad_model()``.
        """
        for label_error in self.list_label_errors:
            label_error.destroy()
            self.row_index -= 1
        for label_info in self.list_label_info:
            label_info.destroy()
            self.row_index -= 1

    def display_error(self, message: str):
        """Show ``message`` as a red, bold, dismissible error label.

        A no-op if ``message`` is empty/``None``. The label is
        appended to ``self.list_label_errors`` and removed the next
        time ``clean_errors_and_info()`` runs.

        :param message: Error text to display (without the "Error : "
            prefix, which is added here).
        :type message: str
        """
        if message is None or message == '':
            return

        message = 'Error : ' + message

        label_message = ttk.Label(
            self,
            text=message,
            foreground='#D63C27',
            font='Helvetica 10 bold')
        label_message.grid(row=self.row_index, column=1, pady=5)
        self.list_label_errors.append(label_message)
        self.row_index += 1

    def display_info(self, message: str):
        """Show ``message`` as a green, bold, dismissible info label.

        A no-op if ``message`` is empty/``None``. The label is
        appended to ``self.list_label_info`` and removed the next time
        ``clean_errors_and_info()`` runs.

        :param message: Info text to display.
        :type message: str
        """
        if message is None or message == '':
            return

        label_message = ttk.Label(
            self,
            text=message,
            foreground='#007934',
            font='Helvetica 10 bold')
        label_message.grid(row=self.row_index, column=1, pady=5)
        self.list_label_info.append(label_message)
        self.row_index += 1

    def open_file(self, entry: ttk.Entry, ext: str):
        """Prompt for a file with extension ``ext`` and fill ``entry``.

        Bound to the DLL "Browse" button. Leaves ``entry`` unchanged
        if the dialog is cancelled.

        :param entry: The ``ttk.Entry`` widget to fill in with the
            chosen file's path.
        :type entry: ttk.Entry
        :param ext: File extension to filter on, including the dot
            (e.g. ``'.dll'``).
        :type ext: str
        """
        file = filedialog.askopenfile(
            mode='r', filetypes=[('IEC 61400-27 DLL', '*' + ext)])
        if file:
            file_path = file.name
            entry.delete(0, 'end')  # clear text first
            entry.insert(0, file_path)
