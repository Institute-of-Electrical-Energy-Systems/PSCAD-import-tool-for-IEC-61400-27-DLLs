"""ctypes mirror of the IEC 61400-27 (Ext-SimEnv) DLL C API structures.

These ``ctypes.Structure`` subclasses mirror the layout of the structs
defined in the vendor's ``ext_simenv_capi.h`` header. They let
``DllIntrospectionMixin`` read the static model description returned by
a DLL's ``Model_GetInfo()`` function directly into Python, without
generating or compiling any C/ctypes glue code.

Field order and types must stay in sync with the C header: ctypes maps
each ``_fields_`` entry positionally onto the DLL's binary struct
layout, so any mismatch here silently misreads memory instead of
raising an error.
"""

import ctypes


class StaticESEInputSignal(ctypes.Structure):
    """Static description of a single DLL input signal.

    One instance per input port, as exposed through
    ``StaticExtSimEnvCapi.InputPortsInfo``.
    """

    _fields_ = [
        ("Name", ctypes.c_char_p),       # Signal name (UTF-8, NUL-terminated)
        ("BlockPath", ctypes.c_char_p),  # Originating block path, if any
        ("Width", ctypes.c_int),         # Number of scalar elements
    ]


class StaticESEOutputSignal(ctypes.Structure):
    """Static description of a single DLL output signal.

    One instance per output port, as exposed through
    ``StaticExtSimEnvCapi.OutputPortsInfo``.
    """

    _fields_ = [
        ("Name", ctypes.c_char_p),       # Signal name (UTF-8, NUL-terminated)
        ("BlockPath", ctypes.c_char_p),  # Originating block path, if any
        ("Width", ctypes.c_int),         # Number of scalar elements
    ]


class StaticESEParameter(ctypes.Structure):
    """Static description of a single DLL model parameter.

    One instance per parameter, as exposed through
    ``StaticExtSimEnvCapi.ParametersInfo``. Only numeric (non-string)
    parameters carry meaningful Min/Max/Default values; string
    parameters are filtered out further up the pipeline (see
    ``DllIntrospectionMixin.fill_in_out_param_lists``).
    """

    _fields_ = [
        ("Name", ctypes.c_char_p),          # Parameter name
        ("Description", ctypes.c_char_p),   # Human-readable description
        ("Unit", ctypes.c_char_p),          # Engineering unit, e.g. "kV"
        ("DefaultValue", ctypes.c_double),  # Default numeric value
        ("MinValue", ctypes.c_double),      # Minimum allowed value
        ("MaxValue", ctypes.c_double),      # Maximum allowed value
    ]


class StaticExtSimEnvCapi(ctypes.Structure):
    """Top-level static model description returned by ``Model_GetInfo()``.

    A DLL exposes exactly one of these (as a pointer), describing the
    model as a whole: metadata (name, version, checksum, ...) plus the
    arrays of input/output signals and parameters that
    ``DllIntrospectionMixin`` walks to build the Fortran wrapper and
    the PSCAD component.
    """

    _fields_ = [
        # 4-byte API release, e.g. [0, 8, 1, 5]
        ("APIRelease", ctypes.c_ubyte * 4),
        ("ModelName", ctypes.c_char_p),
        ("ModelVersion", ctypes.c_char_p),
        ("ModelDescription", ctypes.c_char_p),
        ("VersionControlInformation", ctypes.c_char_p),
        ("GeneralInformation", ctypes.c_char_p),
        ("ModelCreated", ctypes.c_char_p),
        ("ModelCreator", ctypes.c_char_p),
        ("ModelLastModifiedDate", ctypes.c_char_p),
        ("ModelLastModifiedBy", ctypes.c_char_p),
        ("ModelModifiedComment", ctypes.c_char_p),
        ("ModelModifiedHistory", ctypes.c_char_p),
        ("CodeGeneratedOn", ctypes.c_char_p),
        ("IncludedSolver", ctypes.c_char_p),
        ("FixedStepBaseSampleTime", ctypes.c_double),
        # Input ports: count + pointer to the first element of the array
        ("NumInputPorts", ctypes.c_int),
        ("InputPortsInfo", ctypes.POINTER(StaticESEInputSignal)),
        # Output ports: count + pointer to the first element of the array
        ("NumOutputPorts", ctypes.c_int),
        ("OutputPortsInfo", ctypes.POINTER(StaticESEOutputSignal)),
        # Parameters: count + pointer to the first element of the array
        ("NumParameters", ctypes.c_int),
        ("ParametersInfo", ctypes.POINTER(StaticESEParameter)),
        ("NumContStates", ctypes.c_int),
        ("SizeofMiscStates", ctypes.c_int),
        ("ModelChecksum", ctypes.c_int * 4),
        ("LastErrorMessage", ctypes.c_char_p),
        ("EMT_RMS_Mode", ctypes.c_int),
        ("LoadflowFlag", ctypes.c_int),
    ]
