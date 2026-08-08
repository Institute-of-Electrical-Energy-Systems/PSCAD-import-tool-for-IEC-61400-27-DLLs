"""PSCAD import tool for IEC 61400-27 (Ext-SimEnv) DLL models.

This module implements the Tkinter GUI application that turns a compiled
IEC 61400-27-style DLL (matching the ext_simenv_capi.h C API) into:
  * a Fortran "FINTERFACE" wrapper source file that PSCAD compiles and links
    against the DLL, and
  * a PSCAD component/project (created via the mhi.pscad automation API)
    with one input/output/parameter per DLL signal.

The generated Fortran wrapper persists a DLL-owned model instance (obtained
via Model_Instance()) across simulation time steps using PSCAD's per-instance
STORF/STORI storage, and reads/writes the DLL's flat ExtU/ExtY/P signal
arrays directly -- see FortranCodegenMixin.create_fortran_code() (and the
finterface_pscad.f90.tmpl template it fills in) for the code-generation
logic.

The Application class itself is now just the composition root: it owns the
Tkinter window and the shared state (self.in_names, self.out_names, ... --
see __init__), and it is assembled from the mixins below, one per concern:

  * GuiMixin                  -- widgets and their event handlers
  * PscadConnectionMixin      -- talking to a running PSCAD application
  * DllIntrospectionMixin     -- loading the DLL and reading its signal/
                                  parameter lists
  * FortranCodegenMixin       -- generating the *_FINTERFACE_PSCAD.f90 text
  * PscadProjectMixin         -- creating the PSCAD project/component

generate_pscad_model() below is the orchestrator that ties them together
when the user clicks "Generate PSCAD Model".
"""

# --- Standard library ---
import os
import shutil  # to copy files
import tkinter as tk

# --- Local: one mixin per concern (see module docstring above) ---
from gui_mixin import GuiMixin
from pscad_connection_mixin import PscadConnectionMixin
from dll_introspection_mixin import DllIntrospectionMixin
from fortran_codegen_mixin import FortranCodegenMixin
from pscad_project_mixin import PscadProjectMixin


class Application(tk.Tk, GuiMixin, PscadConnectionMixin, DllIntrospectionMixin,
                  FortranCodegenMixin, PscadProjectMixin):
    """Main GUI application window.

    Holds both the Tkinter widgets (buttons, entries, comboboxes) used to
    pick a DLL and a destination PSCAD project, and the DLL-introspection
    state (self.in_names, self.out_names, self.param_names, etc.) that is
    filled in by fill_in_out_param_lists() (DllIntrospectionMixin) and
    consumed by create_fortran_code() (FortranCodegenMixin) and
    generate_pscad_project() (PscadProjectMixin).
    """

    def __init__(self, num_version):
        tk.Tk.__init__(self)

        # GUI widgets: all 'self' attributes must be declared in init
        self.button_generate_pscad_model = None
        self.button_go_to_folder = None
        self.button_refresh = None
        self.refresh_image = None
        self.go_to_folder_image = None
        self.combobox_pscad_projects = None
        self.button_browse_new_project = None
        self.entry_des_folder = None
        self.radio_option = None
        self.label_dll_file_path = None
        self.button_browse_pscx_file_path = None
        self.entry_dll_file_path = None
        self.entry_des_folder_placeholder = "Destination folder"
        self.combobox_pscad_projects_placeholder = (
            "Select an open PSCAD project"
        )

        # Other attributes
        self.pscad = None
        self.pscad_projects_selected_value = None
        self.des_folder = None
        self.pscad_project_name = None
        self.num_version = num_version
        self.dll_file_path = None
        self.dll_file_name = None
        self.fortran_interface_file_path = None
        self.fortran_interface_file_name = None
        self.row_index = 0  # for GUI grid
        self.list_label_errors = []
        self.list_label_info = []
        self.Model_Info = None
        self.Model_Name = None
        self.Model_Name_Shortened = None
        self.APIRelease = None
        self.in_names = []
        self.in_fortran_types = []
        self.in_pscad_types = []
        self.in_width = []
        self.out_names = []
        self.out_units = []
        self.out_fortran_types = []
        self.out_pscad_types = []
        self.out_width = []

        # vectors are flattened for output init parameters
        # ex if out2 width is 2: ['out1_init', 'out2_1_init', 'out2_2_init',
        # etc.]
        self.out_init_names = []
        self.out_init_units = []
        self.out_init_pscad_types = []
        self.out_init_width = []

        self.param_names = []
        self.param_fortran_types = []
        self.param_pscad_types = []
        self.param_group_names = []
        self.param_descriptions = []
        self.param_units = []
        # int, kept in case Model_CheckParameters should only be called when
        # a parameter value has actually changed (not implemented yet)
        self.param_fixedValue = []
        self.param_default_values = []
        self.param_min_values = []
        self.param_max_values = []

        self.nb_inputs_total = 0
        self.nb_outputs_total = 0
        self.nb_params_total = 0
        self.nb_params_numeric = 0  # nb of non-string parameters -- these are
        # the only ones that fit in the DLL's flat P_DISCON_Empty_T real64
        # array

    # ------------------------------------------------------------------
    # Main workflow, called when clicking on the "Generate PSCAD Model"
    # button. Orchestrates the mixins above: DllIntrospectionMixin to read
    # the DLL, FortranCodegenMixin to write the wrapper source, and
    # PscadProjectMixin to build the PSCAD project/component.
    # ------------------------------------------------------------------
    def generate_pscad_model(self):
        """Read the selected DLL and (re)generate the PSCAD model for it.

        Bound to the "Generate PSCAD Model" button. Runs the full
        pipeline in order:

        1. Clear previously displayed error/info labels and reset the
           introspection lists (``clean_errors_and_info`` /
           ``clean_list_attributes``).
        2. Validate the selected DLL path and load its
           ``Model_GetInfo()`` metadata (``DllIntrospectionMixin``).
        3. Resolve the target PSCAD project name and destination folder
           depending on the chosen radio option (``PscadProjectMixin``).
        4. Generate the ``*_FINTERFACE_PSCAD.f90`` wrapper source
           (``FortranCodegenMixin``) and write it next to the project.
        5. Copy the DLL into the destination folder if not already
           there.
        6. Create/update the PSCAD project and component
           (``PscadProjectMixin``).

        Any exception raised along the way is caught and shown as an
        inline error label instead of propagating and crashing the GUI.
        """
        try:
            # Remove displayed errors
            self.clean_errors_and_info()

            self.clean_list_attributes()

            # fill dll_file_path attribute
            self.get_and_check_dll_file_path()

            # get self.Model_Info
            self.get_dll_model_info()

            self.get_and_check_dll_interface_version()

            self.Model_Name = self.Model_Info.ModelName.decode("utf-8")
            self.Model_Name_Shortened = self.Model_Name[:50]

            self.get_and_check_pscad_project_name()

            self.get_destination_folder()

            self.fortran_interface_file_name = (
                self.dll_file_name[:-4] + '_FINTERFACE_PSCAD.f90'
            )

            self.fortran_interface_file_path = (
                self.des_folder + '\\' + self.fortran_interface_file_name
            )

            # Create wrapper code and write it to the Fortran file
            self.fill_in_out_param_lists()

            buffer = self.create_fortran_code()

            with open(self.fortran_interface_file_path, 'w') as f:
                f.write(buffer)  # allow rewrite on existing file

            # Copy the DLL into the destination folder
            destination_dll_path = self.des_folder + '\\' + self.dll_file_name
            if not os.path.exists(destination_dll_path):
                shutil.copy(self.dll_file_path, destination_dll_path)

            # Generate PSCAD project and component
            self.generate_pscad_project()

        except Exception as e:
            # self.display_error(e.args[0])  # for old version of python
            # self.display_error(repr(e))  # contains Exception in the
            # message...
            self.display_error(str(e))
