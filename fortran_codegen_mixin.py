"""Mixin that generates the <dll_name>_FINTERFACE_PSCAD.f90 wrapper source.

Pure text/string generation: no Tkinter, ctypes or mhi.pscad calls here.
create_fortran_code() is the entry point and relies on the self.in_*/
self.out_*/self.out_init_*/self.param_* lists already having been filled
in by DllIntrospectionMixin.fill_in_out_param_lists().

The static Fortran boilerplate lives in finterface_pscad.f90.tmpl, next to
this file, and is combined with the dynamically generated fragments below
via string.Template.

NOTE (simplification pass): two legacy module-level functions,
generate_conversion() and generate_flat_array_to_pscad(), were removed.
Neither was referenced from create_fortran_code() or anywhere else in
this file -- a comment in the original source confirmed
generate_conversion() had already been superseded by
generate_pscad_to_flat_array(). If some other module in the codebase
still imports either of them, restore from version control; a repo-wide
search turned up nothing here, but this file only sees itself.
"""

import os
from string import Template


class FortranCodegenMixin:
    """Fortran wrapper source generation, mixed into Application.

    This mixin has no state of its own -- it is never constructed on
    its own, only ever as part of an ``Application`` instance. By the
    time ``create_fortran_code()`` is called, the following must
    already be present on ``self`` (set by ``Application.__init__``
    and filled in by ``DllIntrospectionMixin.fill_in_out_param_lists()``):
    ``dll_file_name``, ``in_names``, ``param_names``, ``out_names``,
    ``out_init_names``, ``in_width``, ``out_width``, ``out_init_width``,
    ``in_pscad_types``, ``out_pscad_types``, ``out_init_pscad_types``,
    ``param_pscad_types``, ``in_fortran_types``, ``out_fortran_types``,
    ``param_fortran_types``, ``num_version``, ``nb_inputs_total``,
    ``nb_outputs_total``, ``nb_params_numeric``, ``APIRelease``,
    ``Model_Info``.
    """

    @staticmethod
    def _indexed_pscad_name(name: str, suffix: str, j: int, width: int) -> str:
        """
            Build the PSCAD-side variable name for element ``j`` of a signal.

            Shared by every generator below that walks a (possibly vector)
            signal and needs the name of its j-th element on the PSCAD side.
            Scalar signals (``width == 1``) get no index; vector signals get
            either ``name(j)`` or, for the special ``_init_pscad`` suffix,
            ``name_j_init_pscad`` (PSCAD declares those as separate scalar
            arguments rather than as an array).

            :param name: Base variable name.
            :type name: str
            :param suffix: PSCAD suffix (e.g. '_pscad', '_pscad_prev', \
                '_init_pscad').
            :type suffix: str
            :param j: 1-based element index.
            :type j: int
            :param width: Total width of the signal.
            :type width: int

            :return: - **-** (str) – The element's PSCAD-side name.
        """
        if width == 1:
            return name + suffix
        if suffix == '_init_pscad':
            return f'{name}_{j}{suffix}'
        return f'{name}{suffix}({j})'

    @staticmethod
    def generate_type(type_name: str, names: list, fortran_types: list,
                      widths=None) -> str:
        """
            Generate a Fortran TYPE definition.

            Creates a Fortran derived type containing one member for each
            variable in ``names``. If a variable width greater than one is
            specified, the corresponding member is declared as an array.

            :param type_name: Name of the generated Fortran type.
            :type type_name: str
            :param names: Member names.
            :type names: list
            :param fortran_types: Fortran data types of the members.
            :type fortran_types: list
            :param widths: Optional widths of the members.
            :type widths: list

            :return: - **buffer** (str) - Generated Fortran TYPE definition.
        """
        members = []
        for i, name in enumerate(names):
            width = widths[i] if widths is not None else 1
            member = f'{fortran_types[i]} :: {name}'
            if width > 1:
                member += f'({width})'
            members.append(member)

        body = '\n\t\t'.join(members)
        return f'\tTYPE {type_name}\n\t\t{body}\n\tEND TYPE'

    @staticmethod
    def generate_variables_declaration(
            intent_value: str, var_names: list, var_suffix: str,
            var_types: list, var_width: list = None):
        """
            Generate a block of Fortran variable declarations.

            :param intent_value: INTENT qualifier (IN, OUT or '').
            :type intent_value: str
            :param var_names: Variable names.
            :type var_names: list
            :param var_suffix: Suffix appended to each variable name.
            :type var_suffix: str
            :param var_types: Fortran type of each variable.
            :type var_types: list
            :param var_width: Optional array widths.
            :type var_width: list

            :return: - **buffer** (str) – Fortran declaration block.
        """
        intent_str = f', INTENT({intent_value})' if intent_value else ''

        buffer = ''
        for i, name in enumerate(var_names):
            width = var_width[i] if var_width is not None else 1
            decl = f'\t{var_types[i]}{intent_str} :: {name}{var_suffix}'
            if width > 1:
                decl += f'({width})'
            buffer += decl + '\n'
        return buffer

    @staticmethod
    def generate_flat_array_to_storf_outputs(widths: list,
                                             pscad_types: list,
                                             array_name: str = 'ExtY',
                                             indent: str = '\t') -> str:
        """
            Generate assignments from a flat output array to STORF.

            Stores the current output values in STORF so they remain
            available between PSCAD time steps.

            :param widths: Output widths.
            :type widths: list
            :param pscad_types: PSCAD types.
            :type pscad_types: list
            :param array_name: Source flat array.
            :type array_name: str
            :param indent: Indentation used in the generated code.
            :type indent: str

            :return: - **buffer** (str) – Generated Fortran assignment code.
        """
        buffer = ''
        idx = 0
        for width, pscad_type in zip(widths, pscad_types):
            if pscad_type == 'CHARACTER(*)':
                continue
            for _ in range(width):
                buffer += (f'{indent}STORF(idx_start_outputs + {idx}) = '
                           f'REAL({array_name}({idx + 1}), 8)\n')
                idx += 1
        return buffer

    @staticmethod
    def generate_storf_outputs_to_pscad(
            names: list, widths: list, pscad_suffix: str, indent: str = '\t'
    ) -> str:
        """
            Generate assignments from STORF back to PSCAD output variables.

            :param names: Variable names.
            :type names: list
            :param widths: Variable widths.
            :type widths: list
            :param pscad_suffix: PSCAD variable suffix.
            :type pscad_suffix: str
            :param indent: Indentation used in the generated code.
            :type indent: str

            :return: - **buffer** (str) – Generated Fortran assignment code.
        """
        buffer = ''
        idx = 0
        for name, width in zip(names, widths):
            for j in range(1, width + 1):
                part1 = _indexed_pscad_name(name, pscad_suffix, j, width)
                buffer += f'{indent}{part1} = STORF(idx_start_outputs + {idx})\n'
                idx += 1
        return buffer

    def generate_finterface_function_prototype(self) -> str:
        """
            Generate the Fortran wrapper subroutine prototype.

            Builds the SUBROUTINE declaration for
            ``<dll_name>_FINTERFACE_PSCAD(...)`` with one dummy argument
            for each PSCAD input, parameter, output and output
            initialization signal, followed by the runtime arguments
            ``TRelease``, ``DLL_Path`` and ``Use_Interpolation``.
            The argument list is wrapped after every five arguments for
            readability.

            :return: **-** (str) – Generated Fortran subroutine prototype.
        """
        dll_stem = self.dll_file_name[:-4]

        args = (
            [f'{n}_pscad' for n in self.in_names]
            + [f'{n}_pscad' for n in self.param_names]
            + [f'{n}_pscad' for n in self.out_names]
            + [f'{n}_pscad' for n in self.out_init_names]
            + ['TRelease', 'DLL_Path', 'Use_Interpolation']
        )

        max_per_line = 5
        lines = [
            ', '.join(args[i:i + max_per_line])
            for i in range(0, len(args), max_per_line)
        ]
        body = ', &\n\t    '.join(lines)

        return f'\tSUBROUTINE {dll_stem}_FINTERFACE_PSCAD(&\n\t    {body})\n'

    def generate_variables_from_pscad(self) -> str:
        """
            Generate the declarations for all PSCAD interface variables.

            Creates the Fortran declarations for input, parameter, output
            initialization and output variables by combining the individual
            declaration blocks produced by generate_variables_declaration().

            :return: **-** (str) – Fortran declaration block.
        """
        blocks = [
            generate_variables_declaration(
                intent_value='IN',
                var_names=self.in_names,
                var_suffix='_pscad',
                var_types=self.in_pscad_types,
                var_width=self.in_width),
            generate_variables_declaration(
                intent_value='IN',
                var_names=self.param_names,
                var_suffix='_pscad',
                var_types=self.param_pscad_types,
                var_width=None),
            generate_variables_declaration(
                intent_value='IN',
                var_names=self.out_init_names,
                var_suffix='_pscad',
                var_types=self.out_init_pscad_types,
                var_width=self.out_init_width),
            generate_variables_declaration(
                intent_value='OUT',
                var_names=self.out_names,
                var_suffix='_pscad',
                var_types=self.out_pscad_types,
                var_width=self.out_width),
        ]
        return '\n'.join(blocks)

    def generate_storf_to_prev_inputs(self) -> str:
        """
            Generate assignments from STORF to previous PSCAD input variables.

            Restores the cached input values stored in STORF into the
            *_pscad_prev variables used for interpolation.

            :return: **buffer** (str) – Generated Fortran assignment code.
        """
        buffer = ''
        i_storf = 0
        for i in range(self.Model_Info.NumInputPorts):
            width = self.in_width[i]
            name = self.in_names[i]
            for j in range(1, width + 1):
                part1 = _indexed_pscad_name(
                    name=name,
                    suffix='_pscad_prev',
                    j=j,
                    width=width)
                buffer += (f'\t\t{part1} = STORF(idx_start_inputs + '
                           f'{i_storf})\n')
                i_storf += 1
        return buffer

    def generate_inputs_to_storf(self) -> str:
        """
            Generate assignments from PSCAD inputs to STORF.

            Stores the current PSCAD input values in STORF so they can
            be reused during interpolation and subsequent simulation
            steps.

            :return: **buffer** (str) – Generated Fortran assignment code.
        """
        buffer = ''
        i_storf = 0
        for i in range(self.Model_Info.NumInputPorts):
            width = self.in_width[i]
            name = self.in_names[i]
            for j in range(1, width + 1):
                part2 = _indexed_pscad_name(
                    name=name,
                    suffix='_pscad',
                    j=j,
                    width=width)
                buffer += (f'\t\tSTORF(idx_start_inputs + {i_storf}) '
                           f'= {part2}\n')
                i_storf += 1
        return buffer

    # ------------------------------------------------------------------
    # Flat-array (ExtU_DISCON_Empty_T / ExtY_DISCON_Empty_T / P_DISCON_Empty_T)
    # conversion helper.
    #
    # The real ext_simenv_capi.h defines the instance's ExtU/ExtY/P members as
    # flat real64_T* arrays owned by the DLL (not a named Fortran struct that
    # PSCAD allocates), so we index into them positionally instead of by field
    # name. Only scalar (non-string) signals/parameters can live in these
    # arrays -- CHARACTER(*) parameters are skipped (see nb_params_numeric).
    # names/widths/pscad_types follow the same convention throughout this
    # file: names is self.in_names / self.out_names / self.param_names
    # (widths=None for parameters, since only scalar parameters are allowed).
    # ------------------------------------------------------------------
    def generate_pscad_to_flat_array(self, names: list, widths: list,
                                     array_name: str, pscad_suffix: str,
                                     indent: str = '\t') -> str:
        """
            Generate assignments from PSCAD variables to a flat DLL array.

            :param names: Variable names.
            :type names: list
            :param widths: Variable widths.
            :type widths: list
            :param array_name: Target flat array (e.g. ExtU, ExtY or P).
            :type array_name: str
            :param pscad_suffix: PSCAD variable suffix.
            :type pscad_suffix: str
            :param indent: Indentation used in the generated code.
            :type indent: str

            :return: - **buffer** (str) – Generated Fortran assignment code.
        """
        buffer = ''
        idx = 0
        for i, name in enumerate(names):
            width = widths[i] if widths is not None else 1
            for j in range(1, width + 1):
                part2 = _indexed_pscad_name(
                    name=name,
                    suffix=pscad_suffix,
                    j=j,
                    width=width)
                buffer += f'{indent}{array_name}({idx + 1}) = {part2}\n'
                idx += 1
        return buffer

    def generate_interpolated_extu(self):
        """
            Generate interpolated-input assignments directly into ExtU.

            NOTE: like the historical generate_interpolated_inputs(), this
            only indexes correctly for width == 1 inputs (the common case
            for this model). Vector (width > 1) inputs are not split into
            per-element interpolation here.

            :return: **buffer** (str) – Generated Fortran assignment code.
        """
        buffer = ''
        idx = 0
        for i in range(self.Model_Info.NumInputPorts):
            width = self.in_width[i]
            name = self.in_names[i]
            buffer += (
                f'\t\t\tExtU({idx + 1}) = {name}_pscad_prev + '
                f'({name}_pscad - {name}_pscad_prev) * delta_t2 / delta_t1\n'
            )
            idx += width
        return buffer

    def create_fortran_code(self) -> str:
        """
            Generate the full <dll_name>_FINTERFACE_PSCAD.f90 source text.

            Produces two parts:
              1. A MODULE <dll_name>_MOD defining the
                 ext_simenv_capi.h-compatible types (StaticExtSimEnvCapi,
                 InstanceExtSimEnvCapi, ESEExtension), the DLL function
                 INTERFACE block, the runtime function-pointer loading
                 helpers (Get_DLL_Handle, Get_Pointer_To_DLL_Function),
                 and small utilities (Handle_Message, Get_Fortran_String,
                 CPtr_To_Ints / Ints_To_CPtr for persisting a c_ptr in STORI).
              2. A SUBROUTINE <dll_name>_FINTERFACE_PSCAD(...) called by PSCAD
                 every simulation time step, which: creates the DLL-owned model
                 instance once (Model_Instance), persists its handle across
                 steps via STORI, maps the instance's flat ExtU/ExtY/P arrays
                 with c_f_pointer, writes inputs/parameters, calls
                 Model_CheckParameters / Model_Initialize / Model_Outputs /
                 Model_Update as appropriate, and caches outputs in STORF so
                 they can be returned to PSCAD every time step (not just on
                 model sample-time steps).

            The static Fortran boilerplate (module/type/interface definitions,
            runtime helpers) lives in finterface_pscad.f90.tmpl next to this
            file and is filled in with string.Template; only the pieces that
            actually depend on the DLL's signal/parameter lists are generated
            in Python (see the generate_* helpers above).

            Relies on self.in_names / self.out_names / self.param_names (and
            their *_width / *_pscad_types / *_fortran_types companions) having
            already been filled in by fill_in_out_param_lists().

            :return: **-** (str) – Generated fortran code.
        """
        # strip the '.dll' extension
        model_name = self.dll_file_name[:-4]

        template_path = os.path.join(
            os.path.dirname(
                os.path.abspath(__file__)),
            'finterface_pscad.f90.tmpl')
        with open(template_path, 'r', encoding='utf-8') as f:
            template = Template(f.read())

        in_pscad_prev_declaration = generate_variables_declaration(
            intent_value='',
            var_names=self.in_names,
            var_suffix='_pscad_prev',
            var_types=self.in_pscad_types,
            var_width=self.in_width
        )

        params_pscad_to_flat = self.generate_pscad_to_flat_array(
            names=self.param_names,
            widths=None,
            array_name='P',
            pscad_suffix='_pscad',
            indent='\t\t'
        )

        inputs_pscad_to_extu = self.generate_pscad_to_flat_array(
            names=self.in_names,
            widths=self.in_width,
            array_name='ExtU',
            pscad_suffix='_pscad',
            indent='\t\t\t'
        )

        outputs_init_pscad_to_exty = self.generate_pscad_to_flat_array(
            names=self.out_names,
            widths=self.out_width,
            array_name='ExtY',
            pscad_suffix='_init_pscad',
            indent='\t\t\t'
        )

        exty_to_storf = generate_flat_array_to_storf_outputs(
            widths=self.out_width,
            pscad_types=self.out_pscad_types,
            array_name='ExtY',
            indent='\t\t'
        )

        storf_outputs_to_pscad = generate_storf_outputs_to_pscad(
            names=self.out_names,
            widths=self.out_width,
            pscad_suffix='_pscad',
            indent='\t'
        )

        return template.substitute(
            model_name=model_name,
            model_name_len=str(len(model_name)),
            num_version=str(self.num_version),
            n_inputs=str(self.nb_inputs_total),
            n_outputs=str(self.nb_outputs_total),
            n_parameters=str(self.nb_params_numeric),
            finterface_function_prototype=(
                self.generate_finterface_function_prototype()),
            variables_from_pscad=self.generate_variables_from_pscad(),
            orig_dll_interface_version=str(self.APIRelease),
            in_pscad_prev_declaration=in_pscad_prev_declaration,
            params_pscad_to_flat=params_pscad_to_flat,
            interpolated_extu=self.generate_interpolated_extu(),
            inputs_pscad_to_extu=inputs_pscad_to_extu,
            outputs_init_pscad_to_exty=outputs_init_pscad_to_exty,
            exty_to_storf=exty_to_storf,
            storf_to_prev_inputs=self.generate_storf_to_prev_inputs(),
            inputs_to_storf=self.generate_inputs_to_storf(),
            storf_outputs_to_pscad=storf_outputs_to_pscad,
        )
