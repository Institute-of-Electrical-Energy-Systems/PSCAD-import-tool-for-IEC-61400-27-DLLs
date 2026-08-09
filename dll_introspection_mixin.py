"""Mixin for loading and introspecting the IEEE/CIGRE DLL.

Covers locating/loading the DLL (ctypes), reading its Model_GetInfo()
struct, checking the Ext-SimEnv API version, and turning that raw info
into the self.in_*/self.out_*/self.out_init_*/self.param_* lists consumed
by the Fortran code generator and the PSCAD component builder.
"""

import ctypes
import os

from IEC_DLLInterface import StaticExtSimEnvCapi


class DllIntrospectionMixin:
    """DLL loading and signal/parameter list building.

    Mixed into ``Application``.
    """

    def clean_list_attributes(self):
        """Reset all signal/parameter list attributes to empty lists.

        Called at the start of ``generate_pscad_model()`` so that a
        second run (e.g. after selecting a different DLL) starts from
        a clean state instead of appending to stale data from a
        previous run.
        """
        self.in_names = []
        self.in_fortran_types = []
        self.in_pscad_types = []
        self.in_width = []

        self.out_names = []
        self.out_units = []
        self.out_fortran_types = []
        self.out_pscad_types = []
        self.out_width = []

        self.out_init_names = []
        self.out_init_units = []
        self.out_init_fortran_types = []
        self.out_init_pscad_types = []
        self.out_init_width = []

        self.param_names = []
        self.param_fortran_types = []
        self.param_pscad_types = []
        self.param_group_names = []
        self.param_descriptions = []
        self.param_units = []
        self.param_default_values = []
        self.param_min_values = []
        self.param_max_values = []

        self.list_label_errors = []
        self.list_label_info = []

    @staticmethod
    def remove_forbidden_char(name: str) -> str:
        """Replace spaces in a signal/parameter name with underscores.

        :param name: Raw name as read from the DLL.
        :type name: str

        :return: **name** (str) – Sanitized name, safe to use as a \
            Fortran/PSCAD identifier.
        """
        name = name.replace(' ', '_')
        return name

    @staticmethod
    def shorten_if_limit_exceeded(
            name: str, counter_for_long_names: int
    ) -> tuple[str, int]:
        """Shorten ``name`` to fit PSCAD's 31-character signal name limit.

        Names within the limit are returned unchanged. Names that are
        too long are truncated and suffixed with a unique counter
        (``_1``, ``_2``, ..., ``_10``, ...) so that two overly-long
        names that share the same 28/29-character prefix don't collide
        after truncation.

        :param name: Candidate signal name (already space-sanitized).
        :type name: str
        :param counter_for_long_names: Number of names shortened so far
            in this run; incremented and returned so the caller can
            keep threading it through successive calls.
        :type counter_for_long_names: int

        :return: **(shortened_name, updated_counter)** (tuple[str, int]) – \
            shortened name and long names counter .
        """
        if len(name) <= 31:
            return name, counter_for_long_names

        counter_for_long_names += 1
        if counter_for_long_names < 10:
            base = name[:29]
        else:
            base = name[:28]

        return base + '_' + str(counter_for_long_names), counter_for_long_names

    def fill_in_out_param_lists(self):
        """Read self.Model_Info (from the DLL's Model_GetInfo()) and populate
        the self.in_*, self.out_*, self.out_init_*, and self.param_* lists
        used throughout code/component generation.

        Also computes self.nb_inputs_total / self.nb_outputs_total (sum of
        signal widths) and self.nb_params_numeric (count of non-string
        parameters), which size the DLL's flat ExtU/ExtY/P arrays.

        Long signal names (32+ chars) are shortened, since PSCAD limits
        signal names to 31 characters; parameter names are not limited.
        """
        counter_for_long_names = 0
        for i in range(0, self.Model_Info.NumInputPorts):
            signal = self.Model_Info.InputPortsInfo[i]
            if signal.Name is None:
                raise Exception(
                    'One of the inputs has no Name, it is forbidden')
            name = signal.Name.decode("utf-8")
            name = self.remove_forbidden_char(name)
            name, counter_for_long_names = self.shorten_if_limit_exceeded(
                name, counter_for_long_names)
            self.in_names.append(name)
            try:
                # signal.Width is absent for parameters, only for signals
                width = signal.Width
                if width is None:
                    width = 1
            except Exception:
                width = 1
            self.in_width.append(width)

            self.in_fortran_types.append('DOUBLE PRECISION')
            self.in_pscad_types.append('REAL')

        for i in range(0, self.Model_Info.NumOutputPorts):
            signal = self.Model_Info.OutputPortsInfo[i]
            if signal.Name is None:
                raise Exception(
                    'One of the outputs has no Name, it is forbidden')
            name = signal.Name.decode("utf-8")
            name = self.remove_forbidden_char(name)
            name, counter_for_long_names = self.shorten_if_limit_exceeded(
                name, counter_for_long_names)
            self.out_names.append(name)
            try:
                # signal.Width is absent for parameters, only for signals
                width = signal.Width
                if width is None:
                    width = 1
            except Exception:
                width = 1
            self.out_width.append(width)

            self.out_fortran_types.append('DOUBLE PRECISION')
            self.out_pscad_types.append('REAL')

        for i in range(0, self.Model_Info.NumParameters):
            parameter = self.Model_Info.ParametersInfo[i]
            if parameter.Name is None:
                raise Exception(
                    'One of the parameters has no Name, it is forbidden')
            name = parameter.Name.decode("utf-8")
            name = self.remove_forbidden_char(name)
            if parameter.Description is None:
                description = ''
            else:
                description = parameter.Description.decode("utf-8")
            if parameter.Unit is None:
                unit = ''
            else:
                unit = parameter.Unit.decode("utf-8")

            if parameter.DefaultValue is None:
                raise Exception(
                    'One of the parameters has no DefaultValue, it is '
                    'forbidden')
            if parameter.MinValue is None:
                raise Exception(
                    'One of the parameters has no MinValue, it is '
                    'forbidden')
            if parameter.MaxValue is None:
                raise Exception(
                    'One of the parameters has no MaxValue, it is '
                    'forbidden')
            default_value = parameter.DefaultValue
            # IEEE CIGRE DLL allows min max value for strings
            min_value = parameter.MinValue
            max_value = parameter.MaxValue

            self.param_names.append(name)
            self.param_fortran_types.append('DOUBLE PRECISION')
            self.param_pscad_types.append('REAL')
            self.param_descriptions.append(description)
            self.param_units.append(unit)
            self.param_default_values.append(default_value)
            self.param_min_values.append(min_value)
            self.param_max_values.append(max_value)

        # Fill out_init parameters
        for i in range(len(self.out_names)):

            ext = ''
            self.out_init_names.append(self.out_names[i] + ext + '_init')

            self.out_init_fortran_types.append(self.out_fortran_types[i])
            self.out_init_pscad_types.append(self.out_pscad_types[i])
            # out_init is flattened so width = 1 for each element
            self.out_init_width.append(1)

        if counter_for_long_names > 0:
            self.display_info(
                'Some input or output names have been shortened because '
                'the maximum number of signal characters is 31 in PSCAD')

        self.nb_inputs_total = sum(self.in_width)
        self.nb_outputs_total = sum(self.out_width)
        self.nb_params_total = self.Model_Info.NumParameters
        self.nb_params_numeric = sum(
            1 for t in self.param_pscad_types if t != 'CHARACTER(*)')
        if self.nb_params_numeric != self.nb_params_total:
            self.display_info(
                'Warning: this DLL has one or more CHARACTER(*) (string) '
                'parameters. The Ext-SimEnv C API only supports numeric '
                'parameters in its flat parameter array, so string '
                'parameters will NOT be passed to the DLL.')

    def get_and_check_dll_file_path(self):
        """Read and validate the DLL path entered/browsed in the GUI.

        Fills ``self.dll_file_path`` and ``self.dll_file_name``.

        :raises Exception: If no DLL path was entered.
        """
        self.dll_file_path = self.entry_dll_file_path.get()
        self.dll_file_name = os.path.basename(self.dll_file_path)
        if not self.dll_file_path:
            raise Exception("Please select a DLL")

    def get_dll_model_info(self):
        """Load the DLL and call its ``Model_GetInfo()`` entry point.

        Loads ``self.dll_file_path`` with ``ctypes.cdll.LoadLibrary``,
        declares ``Model_GetInfo``'s return type as a pointer to
        ``StaticExtSimEnvCapi``, calls it, and stores the dereferenced
        struct in ``self.Model_Info``.

        :raises RuntimeError: If ``Model_GetInfo()`` returns a NULL
            pointer.
        """
        dll_handle = ctypes.cdll.LoadLibrary(self.dll_file_path)

        # Tell ctypes what Model_GetInfo returns
        dll_handle.Model_GetInfo.restype = ctypes.POINTER(
            StaticExtSimEnvCapi)

        # Call the function
        result = dll_handle.Model_GetInfo()

        if not result:
            raise RuntimeError("Model_GetInfo() returned NULL")

        self.Model_Info = result.contents

    def get_and_check_dll_interface_version(self):
        """Check the DLL's Ext-SimEnv API release against the supported one.

        This import tool is only compatible with API release 0.8.1.5;
        fills ``self.APIRelease`` (e.g. ``[0, 8, 1, 5]``) regardless of
        whether it matches.

        :raises Exception: If the DLL's API release is not 0.8.1.5.
        """
        self.APIRelease = [int(x) for x in self.Model_Info.APIRelease]
        if self.APIRelease != [0, 8, 1, 5]:
            api_release_str = '.'.join(map(str, self.APIRelease))
            raise Exception(
                'DLLInterfaceVersion is not correct. This import tool is '
                'compatible with 1.1.0.0 but the DLL interface version is '
                + api_release_str)
