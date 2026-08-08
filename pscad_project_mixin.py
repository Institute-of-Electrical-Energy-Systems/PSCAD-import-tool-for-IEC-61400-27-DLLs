"""Mixin that creates/updates the PSCAD project and component via mhi.pscad.

Covers resolving the target project name and destination folder (either
"create new project" or "use an existing open project"), and building the
PSCAD component (ports, mask/parameter form, graphics, Fortran script,
resource) with the mhi.pscad.wizard automation API.
"""

import os

from mhi.pscad.wizard import UserDefnWizard, Signal


def _signal_data_type(pscad_type: str):
    """Map a PSCAD scalar type string to the wizard's Signal enum."""
    return Signal.REAL if pscad_type == 'REAL' else Signal.INTEGER


class PscadProjectMixin:
    """PSCAD project/component generation, mixed into Application.

    This mixin has no state of its own -- it is never constructed on
    its own, only ever as part of an ``Application`` instance -- and
    reads a number of attributes it does not set. By the time
    ``get_and_check_pscad_project_name()``, ``get_destination_folder()``
    or ``generate_pscad_project()`` are called, the following must
    already be present on ``self``:

    * From ``Application.__init__`` / ``DllIntrospectionMixin``:
      ``dll_file_name``, ``dll_file_path``, ``Model_Name_Shortened``,
      ``fortran_interface_file_name``, ``in_names``, ``in_width``,
      ``in_pscad_types``, ``out_names``, ``out_width``,
      ``out_pscad_types``, ``param_names``, ``param_descriptions``,
      ``param_units``, ``param_default_values``, ``param_min_values``,
      ``param_max_values``, ``out_init_names``,
      ``out_init_pscad_types``.
    * From ``GuiMixin``: ``radio_option``,
      ``pscad_projects_selected_value``,
      ``combobox_pscad_projects_placeholder``, ``entry_des_folder``,
      ``entry_des_folder_placeholder``, ``display_error``,
      ``display_info``.
    * From ``PscadConnectionMixin`` (and whatever creates the
      mhi.pscad Automation link): ``pscad``, ``init_pscad``.
    """

    def _is_new_project_option(self) -> bool:
        """True if the user chose "create a new project" (radio Option 1)."""
        return self.radio_option.get() == "Option 1"

    def get_and_check_pscad_project_name(self):
        """Resolve and validate ``self.pscad_project_name``.

        For "create new project" (Option 1), the project name is the
        shortened model name. For "use an existing project" (Option
        2), the project name is read from the combobox selection.

        :raises Exception: If Option 2 is selected but no real project
            (i.e. an empty value or the placeholder text) is chosen.
        """
        if self._is_new_project_option():
            self.pscad_project_name = self.Model_Name_Shortened
        else:
            self.pscad_project_name = (
                self.pscad_projects_selected_value.get())
            is_placeholder = (
                self.pscad_project_name
                == self.combobox_pscad_projects_placeholder)
            if not self.pscad_project_name or is_placeholder:  # means ""
                raise Exception("No PSCAD project selected")

    def get_destination_folder(self):
        """Resolve ``self.des_folder``, the target folder on disk.

        For "create new project" (Option 1): the folder typed/browsed
        in the destination-folder entry, falling back to the DLL's own
        folder if the entry is empty or still shows its placeholder.
        For "use an existing project" (Option 2): the folder the
        selected PSCAD project's file lives in (reconnecting to PSCAD
        first if needed, via ``init_pscad()``).
        """
        if self._is_new_project_option():
            self.destination_folder = self.entry_des_folder.get()
            is_empty_or_placeholder = (
                not self.destination_folder
                or self.destination_folder
                == self.entry_des_folder_placeholder)
            if is_empty_or_placeholder:
                # get folder path of the DLL
                self.des_folder = os.path.dirname(self.dll_file_path)
        else:
            # Reload PSCAD if it has been closed; cannot fail because
            # this was already tested in click_radio_button()
            self.init_pscad()
            project_filename = self.pscad.project(
                self.pscad_project_name).filename
            self.des_folder = os.path.dirname(project_filename)

    def generate_pscad_project(self):
        """Create/update the PSCAD project and its generated component.

        Connects to PSCAD (``init_pscad()``); if that fails, shows an
        error and returns early -- the Fortran wrapper file has
        already been written by this point, so the user still gets a
        usable, if incomplete, result. Otherwise: creates a new
        project or selects the existing one (depending on the radio
        option), builds the component via ``UserDefnWizard`` (ports,
        parameter form, graphics, Fortran script), places it on the
        "Main" canvas, attaches the Fortran wrapper as a project
        resource, and saves the project.
        """
        try:
            # depending on the radio option, PSCAD may not be
            # initialized yet
            self.init_pscad()
        except Exception as e:
            # exception to display error because does not stop algo
            self.display_error(
                str(e) + ' Only the wrapper file is generated.')
            return

        # Get workspace. For info, works also if no license
        workspace = self.pscad.workspace()
        if self._is_new_project_option():
            # Fails if there is no license
            project = workspace.create_project(
                1, self.pscad_project_name, self.destination_folder)
        else:
            project = self.pscad.project(self.pscad_project_name)

        canvas = project.canvas("Main")

        # Init Component Wizard
        wizard = UserDefnWizard(self.dll_file_name[:-4])
        # Description of the definition (is not read only)
        wizard.description = "IEC 61400-27 DLL - " + self.dll_file_name[:-4]

        self._add_ports(wizard)
        self._add_parameters_form(wizard)
        self._add_graphics(wizard)
        self._add_fortran_script(wizard)

        # Creating the definition
        defn = wizard.create_definition(project)
        canvas.create_component(defn, 20, 2)  # will be on top of the canvas

        self._add_resource(project)

        self.display_info(
            'The ' + self.Model_Name_Shortened
            + ' component has been created in project '
            + self.pscad_project_name + ' located in\n' + self.des_folder)

        # Save the project because No dialog box if PSCAD is closed and
        # project not saved...
        project.save()

    def _add_ports(self, wizard):
        """
            Add the control inputs and outputs to the created component.

            :param wizard: The UserDefnWizard being built.
        """
        y_offset = 1

        x_coord = -7
        y_coord = 0
        for name, width, pscad_type in zip(
                self.in_names, self.in_width, self.in_pscad_types):
            wizard.port.input(
                x_coord,
                y_coord,
                name,
                _signal_data_type(pscad_type),
                width)
            y_coord += y_offset

        x_coord = +17
        y_coord = 0
        for name, width, pscad_type in zip(
                self.out_names, self.out_width, self.out_pscad_types):
            wizard.port.output(
                x_coord,
                y_coord,
                name,
                _signal_data_type(pscad_type),
                width)
            y_coord += y_offset

    def _add_parameters_form(self, wizard):
        """
            Build the mask menu: Configuration, Model Parameters and
            Initial Conditions tabs.

            :param wizard: The UserDefnWizard being built.
        """
        category = wizard.category

        # Configuration tab
        # Fill the parameter name, automatically created by PSCAD
        wizard.parameter["Name"].value = self.dll_file_name[:-4]
        wizard.parameter["Name"].visible = False
        category["Configuration"].text(
            "DLL_Path",
            description='DLL Path',
            value='..\\' +
            self.dll_file_name)
        p = category["Configuration"].logical(
            "Use_Interpolation",
            description='Use linear interpolation of inputs',
            value='.FALSE.'
        )
        p._set_attr('.', 'content_type', 'Constant', str)

        model_parameters = category.add("Model Parameters")
        param_iter = zip(
            self.param_names, self.param_descriptions, self.param_units,
            self.param_default_values, self.param_min_values,
            self.param_max_values)
        for name, description, unit, default_value, min_value, max_value \
                in param_iter:
            full_description = name + ' - ' + description
            if unit != '':
                default_value = str(default_value) + ' [' + unit + ']'
            model_parameters.real(
                name,
                description=full_description,
                value=default_value,
                minimum=min_value,
                maximum=max_value,
                units=unit)

        initial_conditions = category.add('Initial Conditions')
        p = initial_conditions.real(
            "TRelease",
            description='TRelease - Time to release initial conditions (sec)',
            value='0 [sec]',
            minimum=0,
            maximum=1E+308,
            units='sec')
        p._set_attr('.', 'content_type', 'Constant', str)

        for name, pscad_type in zip(
                self.out_init_names, self.out_init_pscad_types):
            if pscad_type != 'REAL':
                raise Exception('Unknown PSCAD type for output init: ' + name)
            p = initial_conditions.real(
                name, description=name + ' - Initial output value')
            p._set_attr('.', 'content_type', 'Constant', str)

        # is not read only
        wizard.form_width = 600
        # space between symbol name and value in PSCAD form
        wizard.form_splitter = 40

    def _add_graphics(self, wizard):
        """
            Add the component's title text to the graphics canvas.

            :param wizard: The UserDefnWizard being built.
        """
        label_height = 18
        total_width = 200
        y_offset = 1
        name = self.Model_Name_Shortened

        if len(name) <= 25:
            wizard.graphics.text(
                name,
                total_width // 2 - 10,
                y_offset * label_height)
        else:
            wizard.graphics.text(name[:25],
                                 total_width // 2 - 10,
                                 y_offset * label_height)
            y_offset += 1
            wizard.graphics.text(name[25:],
                                 total_width // 2 - 10,
                                 y_offset * label_height)

        y_offset += 1
        wizard.graphics.text(
            "IEC DLL", total_width // 2 - 10, y_offset * label_height)
        y_offset += 1
        # empty text placed at total_width to set the component's width
        wizard.graphics.text("", total_width, y_offset * label_height)

    def _add_fortran_script(self, wizard):
        """
            Add the CALL to the generated <dll_name>_FINTERFACE_PSCAD
            subroutine as the component's Fortran script.

            :param wizard: The UserDefnWizard being built.
        """
        arg_names = self.in_names + self.param_names + \
            self.out_names + self.out_init_names
        args = ''.join('$' + name + ', ' for name in arg_names)
        args += '$TRelease, "$DLL_Path", $Use_Interpolation'

        # Do not split args into several lines for the script part.
        # This will be done automatically by PSCAD when it generates Main.f
        wizard.script['Fortran'] = '\tCALL ' + \
            self.dll_file_name[:-4] + '_FINTERFACE_PSCAD(' + args + ')'

    def _add_resource(self, project):
        """
            Attach the <dll_name>_FINTERFACE_PSCAD.f90 file as a project
            resource, if it isn't already there.

            See the PSCAD V5 help topic "Resources Branch" under
            The Application Environment > The Workspace > The Primary
            Window > Projects Branch. Introduced in PSCAD V5, the
            resources branch replaces the prior Additional Source
            Files (*.f, *.for, *.f90, *.c, *.cpp), the Additional
            Library/Object Files project settings, and the older File
            Reference component, as a single entry point for
            attaching, linking and displaying external, dependent
            files.

            :param project: The PSCAD project to attach the resource to.
        """
        already_added = any(
            r.name == self.fortran_interface_file_name
            for r in project.resources())
        if not already_added:
            project.create_resource(self.fortran_interface_file_name)
