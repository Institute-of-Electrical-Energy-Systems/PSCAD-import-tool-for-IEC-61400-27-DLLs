"""Mixin handling the connection to a running PSCAD 5.X application instance.

Covers launching/reusing a PSCAD application object (self.pscad), listing
its open projects, refreshing that list in the GUI, and opening a selected
project's folder in Explorer.
"""

import os

import mhi.pscad


class PscadConnectionMixin:
    """PSCAD application/session handling, mixed into Application."""

    def get_available_pscad_project_names(self):
        """Return the names of the currently open PSCAD "Case" projects.

        Libraries (project type other than ``'Case'``) are excluded,
        since they cannot be selected as a destination for the
        generated component.

        :return: Names of the open projects, as they appear in PSCAD.
        :rtype: list[str]
        """
        projects_list = self.pscad.projects()
        project_names = []
        for project in projects_list:
            # The project with type "case" is a real project, not a library
            if project['type'] == 'Case':
                project_names.append(project['name'])
        return project_names

    def go_to_selected_project_folder(self):
        """Open the folder of the project selected in the combobox.

        Uses ``os.startfile`` (Windows Explorer). Silently does nothing
        if no project is selected, the project no longer exists in
        PSCAD, or its folder is not found on disk.
        """
        project_name = self.pscad_projects_selected_value.get()

        try:
            pscad_project = self.pscad.project(project_name)
        except Exception:
            return

        project_filename = pscad_project.filename
        folder_path = os.path.dirname(project_filename)  # project folder
        if os.path.exists(folder_path):
            os.startfile(folder_path)

    def init_pscad(self):
        """Ensure ``self.pscad`` holds a live, licensed PSCAD application.

        If PSCAD has never been connected to (``self.pscad is None``),
        attaches to an already-running PSCAD instance or launches a new
        one via ``mhi.pscad.application()``, showing a transient
        "Loading PSCAD" info label while doing so. Idempotent: if
        ``self.pscad`` is already set, this only re-checks the license.

        :raises Exception: If PSCAD 5.X is not installed, cannot be
            reached, or is unlicensed.
        """
        label_loading_pscad = None
        try:
            if self.pscad is None:  # Means PSCAD never init
                # Display Loading message only if self.pscad is None
                self.display_info('Loading PSCAD')
                self.update_idletasks()  # force GUI refresh

                # use PSCAD instance already open or launch a new instance
                self.pscad = mhi.pscad.application()

                # remove the "Loading PSCAD" info label now that we're done
                self.list_label_info[-1].destroy()
                self.list_label_info.pop()  # remove last element from list
                self.row_index -= 1

            if not self.pscad.licensed():
                raise Exception
        except Exception:
            if label_loading_pscad is not None:
                label_loading_pscad.destroy()
            error_message = (
                "PSCAD V5.X is not installed on this computer or is "
                "unlicensed."
            )
            raise Exception(error_message)

    def refresh_pscad_projects(self):
        """Refresh the project combobox with the currently open projects."""
        pscad_project_names = self.get_available_pscad_project_names()
        self.combobox_pscad_projects["values"] = pscad_project_names
