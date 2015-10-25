from pypy.interpreter.error import OperationError
from rpython.rtyper.lltypesystem import rffi, lltype
from pypy.module.unicodedata import unicodedb
from pypy.module.cpyext.api import (
    CANNOT_FAIL, Py_ssize_t, build_type_checkers3, cpython_api,
    bootstrap_function, PyVarObjectFields, cpython_struct, CONST_STRING,
    CONST_WSTRING)
from pypy.module.cpyext.pyerrors import PyErr_BadArgument
from pypy.module.cpyext.pyobject import (
    PyObject, PyObjectP, Py_DecRef, track_reference, get_pyobj_and_incref,
    setup_class_for_cpyext, RRC_PERMANENT_LIGHT, from_pyobj, new_pyobj)
from pypy.module.cpyext.stringobject import PyString_Check
from pypy.module.sys.interp_encoding import setdefaultencoding
from pypy.module._codecs.interp_codecs import CodecState
from pypy.objspace.std import unicodeobject
from rpython.rlib import rstring, runicode
from rpython.tool.sourcetools import func_renamer
import sys

## See comment in stringobject.py.

PyUnicodeObjectStruct = lltype.ForwardReference()
PyUnicodeObject = lltype.Ptr(PyUnicodeObjectStruct)
PyUnicodeObjectFields = PyVarObjectFields + \
    (("ob_uval_pypy", rffi.CArray(lltype.UniChar)),)
cpython_struct("PyUnicodeObject", PyUnicodeObjectFields, PyUnicodeObjectStruct)

PyUnicode_Check, PyUnicode_CheckExact, _PyUnicode_Type = (
    build_type_checkers3("Unicode", "w_unicode"))

@bootstrap_function
def init_unicodeobject(space):
    setup_class_for_cpyext(
        unicodeobject.W_UnicodeObject,
        basestruct=PyUnicodeObjectStruct,

        # --from a W_UnicodeObject, we call this function to allocate
        #   a PyUnicodeObject, initially without any data--
        alloc_pyobj=unicode_alloc_pyobj,

        # --reverse direction: from a PyUnicodeObject, we make a W_UnicodeObject
        #   by instantiating a custom subclass of W_UnicodeObject--
        realize_subclass_of=unicodeobject.W_UnicodeObject,

        # --and then we call this function to initialize the W_UnicodeObject--
        fill_pypy=unicode_fill_pypy,

        # --in this case, and if PyUnicode_CheckExact() returns True, then
        #   the link can be light, i.e. the original PyUnicodeObject might
        #   be freed with free() by the GC--
        alloc_pypy_light_if=PyUnicode_CheckExact,
        )
    unicodeobject.W_UnicodeObject.typedef.cpyext_basicsize += (
        rffi.sizeof(lltype.UniChar))   # includes the final NULL

def _unicode_fill_pyobj(u, ob):
    rffi.unicode2wchararray(u, ob.c_ob_uval_pypy, len(u))
    ob.c_ob_uval_pypy[len(u)] = u'\x00'

def unicode_alloc_pyobj(space, w_obj):
    """
    Makes a PyUnicodeObject from a W_UnicodeObject.
    """
    assert isinstance(w_obj, unicodeobject.W_UnicodeObject)
    size = w_obj.unicode_length()    # 'size' in Py_UNICODEs, not in bytes
    ob = lltype.malloc(PyUnicodeObjectStruct, size + 1, flavor='raw',
                       track_allocation=False)
    ob.c_ob_size = size
    if size > 8:
        ob.c_ob_uval_pypy[size] = u'*'    # not filled yet
    else:
        _unicode_fill_pyobj(w_obj.unicode_w(space), ob)
    return ob, RRC_PERMANENT_LIGHT

def unicode_fill_pypy(space, w_obj, py_obj):
    """
    Creates the unicode in the interpreter. The PyUnicodeObject buffer must not
    be modified after this call.
    """
    py_uni = rffi.cast(PyUnicodeObject, py_obj)
    u = rffi.wcharpsize2unicode(rffi.cast(rffi.CWCHARP, py_uni.c_ob_uval_pypy),
                                py_uni.c_ob_size)
    unicodeobject.W_UnicodeObject.__init__(w_obj, u)

#_______________________________________________________________________

# Buffer for the default encoding (used by PyUnicde_GetDefaultEncoding)
DEFAULT_ENCODING_SIZE = 100
default_encoding = lltype.malloc(rffi.CCHARP.TO, DEFAULT_ENCODING_SIZE,
                                 flavor='raw', zero=True)

Py_UNICODE = lltype.UniChar

def new_empty_unicode(space, length):
    """
    Allocates an uninitialized PyUnicodeObject.  The unicode may be mutated
    as long as it has a refcount of 1; notably, until unicode_fill_pypy() is
    called.
    """
    py_uni = new_pyobj(PyUnicodeObjectStruct, _PyUnicode_Type(space),
                       length + 1)
    py_uni.c_ob_size = length
    py_uni.c_ob_uval_pypy[length] = u'\x00'
    return py_uni

@cpython_api([Py_UNICODE], rffi.INT_real, error=CANNOT_FAIL)
def Py_UNICODE_ISSPACE(space, ch):
    """Return 1 or 0 depending on whether ch is a whitespace character."""
    return unicodedb.isspace(ord(ch))

@cpython_api([Py_UNICODE], rffi.INT_real, error=CANNOT_FAIL)
def Py_UNICODE_ISALPHA(space, ch):
    """Return 1 or 0 depending on whether ch is an alphabetic character."""
    return unicodedb.isalpha(ord(ch))

@cpython_api([Py_UNICODE], rffi.INT_real, error=CANNOT_FAIL)
def Py_UNICODE_ISALNUM(space, ch):
    """Return 1 or 0 depending on whether ch is an alphanumeric character."""
    return unicodedb.isalnum(ord(ch))

@cpython_api([Py_UNICODE], rffi.INT_real, error=CANNOT_FAIL)
def Py_UNICODE_ISLINEBREAK(space, ch):
    """Return 1 or 0 depending on whether ch is a linebreak character."""
    return unicodedb.islinebreak(ord(ch))

@cpython_api([Py_UNICODE], rffi.INT_real, error=CANNOT_FAIL)
def Py_UNICODE_ISDECIMAL(space, ch):
    """Return 1 or 0 depending on whether ch is a decimal character."""
    return unicodedb.isdecimal(ord(ch))

@cpython_api([Py_UNICODE], rffi.INT_real, error=CANNOT_FAIL)
def Py_UNICODE_ISDIGIT(space, ch):
    """Return 1 or 0 depending on whether ch is a digit character."""
    return unicodedb.isdigit(ord(ch))

@cpython_api([Py_UNICODE], rffi.INT_real, error=CANNOT_FAIL)
def Py_UNICODE_ISNUMERIC(space, ch):
    """Return 1 or 0 depending on whether ch is a numeric character."""
    return unicodedb.isnumeric(ord(ch))

@cpython_api([Py_UNICODE], rffi.INT_real, error=CANNOT_FAIL)
def Py_UNICODE_ISLOWER(space, ch):
    """Return 1 or 0 depending on whether ch is a lowercase character."""
    return unicodedb.islower(ord(ch))

@cpython_api([Py_UNICODE], rffi.INT_real, error=CANNOT_FAIL)
def Py_UNICODE_ISUPPER(space, ch):
    """Return 1 or 0 depending on whether ch is an uppercase character."""
    return unicodedb.isupper(ord(ch))

@cpython_api([Py_UNICODE], rffi.INT_real, error=CANNOT_FAIL)
def Py_UNICODE_ISTITLE(space, ch):
    """Return 1 or 0 depending on whether ch is a titlecase character."""
    return unicodedb.istitle(ord(ch))

@cpython_api([Py_UNICODE], Py_UNICODE, error=CANNOT_FAIL)
def Py_UNICODE_TOLOWER(space, ch):
    """Return the character ch converted to lower case."""
    return unichr(unicodedb.tolower(ord(ch)))

@cpython_api([Py_UNICODE], Py_UNICODE, error=CANNOT_FAIL)
def Py_UNICODE_TOUPPER(space, ch):
    """Return the character ch converted to upper case."""
    return unichr(unicodedb.toupper(ord(ch)))

@cpython_api([Py_UNICODE], Py_UNICODE, error=CANNOT_FAIL)
def Py_UNICODE_TOTITLE(space, ch):
    """Return the character ch converted to title case."""
    return unichr(unicodedb.totitle(ord(ch)))

@cpython_api([Py_UNICODE], rffi.INT_real, error=CANNOT_FAIL)
def Py_UNICODE_TODECIMAL(space, ch):
    """Return the character ch converted to a decimal positive integer.  Return
    -1 if this is not possible.  This macro does not raise exceptions."""
    try:
        return unicodedb.decimal(ord(ch))
    except KeyError:
        return -1

@cpython_api([Py_UNICODE], rffi.INT_real, error=CANNOT_FAIL)
def Py_UNICODE_TODIGIT(space, ch):
    """Return the character ch converted to a single digit integer. Return -1 if
    this is not possible.  This macro does not raise exceptions."""
    try:
        return unicodedb.digit(ord(ch))
    except KeyError:
        return -1

@cpython_api([Py_UNICODE], rffi.DOUBLE, error=CANNOT_FAIL)
def Py_UNICODE_TONUMERIC(space, ch):
    """Return the character ch converted to a double. Return -1.0 if this is not
    possible.  This macro does not raise exceptions."""
    try:
        return unicodedb.numeric(ord(ch))
    except KeyError:
        return -1.0

@cpython_api([], Py_UNICODE, error=CANNOT_FAIL)
def PyUnicode_GetMax(space):
    """Get the maximum ordinal for a Unicode character."""
    return runicode.UNICHR(runicode.MAXUNICODE)

@cpython_api([PyObject], rffi.CWCHARP)
def PyUnicode_AsUnicode(space, ref):
    """Return a read-only pointer to the Unicode object's internal Py_UNICODE
    buffer, NULL if unicode is not a Unicode object."""
    if not PyUnicode_Check(space, ref):
        raise OperationError(space.w_TypeError, space.wrap(
            "PyUnicode_AsUnicode only supports unicode strings"))
    ref_uni = rffi.cast(PyUnicodeObject, ref)
    last_char = ref_uni.c_ob_uval_pypy[ref_uni.c_ob_size]
    if last_char != u'\x00':
        assert last_char == u'*'
        # copy unicode buffer
        w_uni = from_pyobj(space, ref)
        _unicode_fill_pyobj(w_uni.unicode_w(space), ref_uni)
        ref_uni.c_ob_uval_pypy[ref_uni.c_ob_size] = u'\x00'
    return rffi.cast(rffi.CWCHARP, ref_uni.c_ob_uval_pypy)

@cpython_api([PyObject], Py_ssize_t, error=-1)
def PyUnicode_GetSize(space, ref):
    if PyUnicode_Check(space, ref):
        ref = rffi.cast(PyUnicodeObject, ref)
        return ref.c_ob_size
    else:
        w_obj = from_pyobj(space, ref)
        return space.len_w(w_obj)

@cpython_api([PyUnicodeObject, rffi.CWCHARP, Py_ssize_t], Py_ssize_t, error=-1)
def PyUnicode_AsWideChar(space, ref, buf, size):
    """Copy the Unicode object contents into the wchar_t buffer w.  At most
    size wchar_t characters are copied (excluding a possibly trailing
    0-termination character).  Return the number of wchar_t characters
    copied or -1 in case of an error.  Note that the resulting wchar_t
    string may or may not be 0-terminated.  It is the responsibility of the caller
    to make sure that the wchar_t string is 0-terminated in case this is
    required by the application."""
    c_buffer = PyUnicode_AsUnicode(space, rffi.cast(PyObject, ref))
    c_size = ref.c_ob_size

    # If possible, try to copy the 0-termination as well
    if size > c_size:
        size = c_size + 1


    i = 0
    while i < size:
        buf[i] = c_buffer[i]
        i += 1

    if size > c_size:
        return c_size
    else:
        return size

@cpython_api([], rffi.CCHARP, error=CANNOT_FAIL)
def PyUnicode_GetDefaultEncoding(space):
    """Returns the currently active default encoding."""
    if default_encoding[0] == '\x00':
        encoding = unicodeobject.getdefaultencoding(space)
        i = 0
        while i < len(encoding) and i < DEFAULT_ENCODING_SIZE:
            default_encoding[i] = encoding[i]
            i += 1
    return default_encoding

@cpython_api([CONST_STRING], rffi.INT_real, error=-1)
def PyUnicode_SetDefaultEncoding(space, encoding):
    """Sets the currently active default encoding. Returns 0 on
    success, -1 in case of an error."""
    if not encoding:
        PyErr_BadArgument(space)
    w_encoding = space.wrap(rffi.charp2str(encoding))
    setdefaultencoding(space, w_encoding)
    default_encoding[0] = '\x00'
    return 0

@cpython_api([PyObject, CONST_STRING, CONST_STRING], PyObject)
def PyUnicode_AsEncodedObject(space, w_unicode, llencoding, llerrors):
    """Encode a Unicode object and return the result as Python object.
    encoding and errors have the same meaning as the parameters of the same name
    in the Unicode encode() method. The codec to be used is looked up using
    the Python codec registry. Return NULL if an exception was raised by the
    codec."""
    if not PyUnicode_Check(space, w_unicode):
        PyErr_BadArgument(space)

    encoding = errors = None
    if llencoding:
        encoding = rffi.charp2str(llencoding)
    if llerrors:
        errors = rffi.charp2str(llerrors)
    return unicodeobject.encode_object(space, w_unicode, encoding, errors)

@cpython_api([PyObject, CONST_STRING, CONST_STRING], PyObject)
def PyUnicode_AsEncodedString(space, w_unicode, llencoding, llerrors):
    """Encode a Unicode object and return the result as Python string object.
    encoding and errors have the same meaning as the parameters of the same name
    in the Unicode encode() method. The codec to be used is looked up using
    the Python codec registry. Return NULL if an exception was raised by the
    codec."""
    w_str = PyUnicode_AsEncodedObject(space, w_unicode, llencoding, llerrors)
    if not PyString_Check(space, w_str):
        raise OperationError(space.w_TypeError, space.wrap(
            "encoder did not return a string object"))
    return w_str

@cpython_api([PyObject], PyObject)
def PyUnicode_AsUnicodeEscapeString(space, w_unicode):
    """Encode a Unicode object using Unicode-Escape and return the result as Python
    string object.  Error handling is "strict". Return NULL if an exception was
    raised by the codec."""
    if not PyUnicode_Check(space, w_unicode):
        PyErr_BadArgument(space)

    return unicodeobject.encode_object(space, w_unicode, 'unicode-escape', 'strict')

@cpython_api([CONST_WSTRING, Py_ssize_t], PyObject)
def PyUnicode_FromUnicode(space, wchar_p, length):
    """Create a Unicode Object from the Py_UNICODE buffer u of the given size. u
    may be NULL which causes the contents to be undefined. It is the user's
    responsibility to fill in the needed data.  The buffer is copied into the new
    object. If the buffer is not NULL, the return value might be a shared object.
    Therefore, modification of the resulting Unicode object is only allowed when u
    is NULL."""
    if wchar_p:
        s = rffi.wcharpsize2unicode(wchar_p, length)
        return get_pyobj_and_incref(space, space.wrap(s))
    else:
        return rffi.cast(PyObject, new_empty_unicode(space, length))

@cpython_api([CONST_WSTRING, Py_ssize_t], PyObject)
def PyUnicode_FromWideChar(space, wchar_p, length):
    """Create a Unicode object from the wchar_t buffer w of the given size.
    Return NULL on failure."""
    # PyPy supposes Py_UNICODE == wchar_t
    return PyUnicode_FromUnicode(space, wchar_p, length)

@cpython_api([PyObject, CONST_STRING], PyObject)
def _PyUnicode_AsDefaultEncodedString(space, w_unicode, errors):
    return PyUnicode_AsEncodedString(space, w_unicode, lltype.nullptr(rffi.CCHARP.TO), errors)

@cpython_api([CONST_STRING, Py_ssize_t, CONST_STRING, CONST_STRING], PyObject)
def PyUnicode_Decode(space, s, size, encoding, errors):
    """Create a Unicode object by decoding size bytes of the encoded string s.
    encoding and errors have the same meaning as the parameters of the same name
    in the unicode() built-in function.  The codec to be used is looked up
    using the Python codec registry.  Return NULL if an exception was raised by
    the codec."""
    if not encoding:
        # This tracks CPython 2.7, in CPython 3.4 'utf-8' is hardcoded instead
        encoding = PyUnicode_GetDefaultEncoding(space)
    w_encoding = space.wrap(rffi.charp2str(encoding))
    w_str = space.wrap(rffi.charpsize2str(s, size))
    if errors:
        w_errors = space.wrap(rffi.charp2str(errors))
    else:
        w_errors = space.w_None
    return space.call_method(w_str, 'decode', w_encoding, w_errors)

@cpython_api([PyObject], PyObject)
def PyUnicode_FromObject(space, w_obj):
    """Shortcut for PyUnicode_FromEncodedObject(obj, NULL, "strict") which is used
    throughout the interpreter whenever coercion to Unicode is needed."""
    if space.is_w(space.type(w_obj), space.w_unicode):
        return w_obj
    else:
        return space.call_function(space.w_unicode, w_obj)

@cpython_api([PyObject, CONST_STRING, CONST_STRING], PyObject)
def PyUnicode_FromEncodedObject(space, w_obj, encoding, errors):
    """Coerce an encoded object obj to an Unicode object and return a reference with
    incremented refcount.

    String and other char buffer compatible objects are decoded according to the
    given encoding and using the error handling defined by errors.  Both can be
    NULL to have the interface use the default values (see the next section for
    details).

    All other objects, including Unicode objects, cause a TypeError to be
    set."""
    if not encoding:
        raise OperationError(space.w_TypeError,
                             space.wrap("decoding Unicode is not supported"))
    w_encoding = space.wrap(rffi.charp2str(encoding))
    if errors:
        w_errors = space.wrap(rffi.charp2str(errors))
    else:
        w_errors = space.w_None

    # - unicode is disallowed
    # - raise TypeError for non-string types
    if space.isinstance_w(w_obj, space.w_unicode):
        w_meth = None
    else:
        try:
            w_meth = space.getattr(w_obj, space.wrap('decode'))
        except OperationError, e:
            if not e.match(space, space.w_AttributeError):
                raise
            w_meth = None
    if w_meth is None:
        raise OperationError(space.w_TypeError,
                             space.wrap("decoding Unicode is not supported"))
    return space.call_function(w_meth, w_encoding, w_errors)

@cpython_api([CONST_STRING], PyObject)
def PyUnicode_FromString(space, s):
    """Create a Unicode object from an UTF-8 encoded null-terminated char buffer"""
    w_str = space.wrap(rffi.charp2str(s))
    return space.call_method(w_str, 'decode', space.wrap("utf-8"))

@cpython_api([CONST_STRING, Py_ssize_t], PyObject)
def PyUnicode_FromStringAndSize(space, s, size):
    """Create a Unicode Object from the char buffer u. The bytes will be
    interpreted as being UTF-8 encoded. u may also be NULL which causes the
    contents to be undefined. It is the user's responsibility to fill in the
    needed data. The buffer is copied into the new object. If the buffer is not
    NULL, the return value might be a shared object. Therefore, modification of
    the resulting Unicode object is only allowed when u is NULL."""
    if s:
        return get_pyobj_and_incref(space, PyUnicode_DecodeUTF8(
            space, s, size, lltype.nullptr(rffi.CCHARP.TO)))
    else:
        return rffi.cast(PyObject, new_empty_unicode(space, size))

@cpython_api([rffi.INT_real], PyObject)
def PyUnicode_FromOrdinal(space, ordinal):
    """Create a Unicode Object from the given Unicode code point ordinal.

    The ordinal must be in range(0x10000) on narrow Python builds
    (UCS2), and range(0x110000) on wide builds (UCS4). A ValueError is
    raised in case it is not."""
    w_ordinal = space.wrap(rffi.cast(lltype.Signed, ordinal))
    return space.call_function(space.builtin.get('unichr'), w_ordinal)

@cpython_api([PyObjectP, Py_ssize_t], rffi.INT_real, error=-1)
def PyUnicode_Resize(space, ref, newsize):
    # XXX always create a new string so far
    py_uni = rffi.cast(PyUnicodeObject, ref[0])
    if py_uni.c_ob_refcnt > 1:
        raise OperationError(space.w_SystemError, space.wrap(
            "PyUnicode_Resize called on already created string"))
    try:
        py_newuni = new_empty_unicode(space, newsize)
    except MemoryError:
        Py_DecRef(space, ref[0])
        ref[0] = lltype.nullptr(PyObject.TO)
        raise
    to_cp = newsize
    oldsize = py_uni.c_ob_size
    if oldsize < newsize:
        to_cp = oldsize
    for i in range(to_cp):
        py_newuni.c_ob_uval_pypy[i] = py_uni.c_ob_uval_pypy[i]
    Py_DecRef(space, ref[0])
    ref[0] = rffi.cast(PyObject, py_newuni)
    return 0

def make_conversion_functions(suffix, encoding):
    @cpython_api([PyObject], PyObject)
    @func_renamer('PyUnicode_As%sString' % suffix)
    def PyUnicode_AsXXXString(space, w_unicode):
        """Encode a Unicode object and return the result as Python
        string object.  Error handling is "strict".  Return NULL if an
        exception was raised by the codec."""
        if not PyUnicode_Check(space, w_unicode):
            PyErr_BadArgument(space)
        return unicodeobject.encode_object(space, w_unicode, encoding, "strict")

    @cpython_api([CONST_STRING, Py_ssize_t, CONST_STRING], PyObject)
    @func_renamer('PyUnicode_Decode%s' % suffix)
    def PyUnicode_DecodeXXX(space, s, size, errors):
        """Create a Unicode object by decoding size bytes of the
        encoded string s. Return NULL if an exception was raised by
        the codec.
        """
        w_s = space.wrap(rffi.charpsize2str(s, size))
        if errors:
            w_errors = space.wrap(rffi.charp2str(errors))
        else:
            w_errors = space.w_None
        return space.call_method(w_s, 'decode', space.wrap(encoding), w_errors)
    globals()['PyUnicode_Decode%s' % suffix] = PyUnicode_DecodeXXX

    @cpython_api([CONST_WSTRING, Py_ssize_t, CONST_STRING], PyObject)
    @func_renamer('PyUnicode_Encode%s' % suffix)
    def PyUnicode_EncodeXXX(space, s, size, errors):
        """Encode the Py_UNICODE buffer of the given size and return a
        Python string object.  Return NULL if an exception was raised
        by the codec."""
        w_u = space.wrap(rffi.wcharpsize2unicode(s, size))
        if errors:
            w_errors = space.wrap(rffi.charp2str(errors))
        else:
            w_errors = space.w_None
        return space.call_method(w_u, 'encode', space.wrap(encoding), w_errors)
    globals()['PyUnicode_Encode%s' % suffix] = PyUnicode_EncodeXXX

make_conversion_functions('UTF8', 'utf-8')
make_conversion_functions('ASCII', 'ascii')
make_conversion_functions('Latin1', 'latin-1')
if sys.platform == 'win32':
    make_conversion_functions('MBCS', 'mbcs')

@cpython_api([rffi.CCHARP, Py_ssize_t, rffi.CCHARP, rffi.INTP], PyObject)
def PyUnicode_DecodeUTF16(space, s, size, llerrors, pbyteorder):
    """Decode length bytes from a UTF-16 encoded buffer string and return the
    corresponding Unicode object.  errors (if non-NULL) defines the error
    handling. It defaults to "strict".

    If byteorder is non-NULL, the decoder starts decoding using the given byte
    order:

    *byteorder == -1: little endian
    *byteorder == 0:  native order
    *byteorder == 1:  big endian

    If *byteorder is zero, and the first two bytes of the input data are a
    byte order mark (BOM), the decoder switches to this byte order and the BOM is
    not copied into the resulting Unicode string.  If *byteorder is -1 or
    1, any byte order mark is copied to the output (where it will result in
    either a \ufeff or a \ufffe character).

    After completion, *byteorder is set to the current byte order at the end
    of input data.

    If byteorder is NULL, the codec starts in native order mode.

    Return NULL if an exception was raised by the codec."""

    string = rffi.charpsize2str(s, size)

    if pbyteorder is not None:
        llbyteorder = rffi.cast(lltype.Signed, pbyteorder[0])
        if llbyteorder < 0:
            byteorder = "little"
        elif llbyteorder > 0:
            byteorder = "big"
        else:
            byteorder = "native"
    else:
        byteorder = "native"

    if llerrors:
        errors = rffi.charp2str(llerrors)
    else:
        errors = None

    result, length, byteorder = runicode.str_decode_utf_16_helper(
        string, size, errors,
        True, # final ? false for multiple passes?
        None, # errorhandler
        byteorder)
    if pbyteorder is not None:
        pbyteorder[0] = rffi.cast(rffi.INT, byteorder)

    return space.wrap(result)

@cpython_api([rffi.CCHARP, Py_ssize_t, rffi.CCHARP, rffi.INTP], PyObject)
def PyUnicode_DecodeUTF32(space, s, size, llerrors, pbyteorder):
    """Decode length bytes from a UTF-32 encoded buffer string and
    return the corresponding Unicode object.  errors (if non-NULL)
    defines the error handling. It defaults to "strict".

    If byteorder is non-NULL, the decoder starts decoding using the
    given byte order:
    *byteorder == -1: little endian
    *byteorder == 0:  native order
    *byteorder == 1:  big endian

    If *byteorder is zero, and the first four bytes of the input data
    are a byte order mark (BOM), the decoder switches to this byte
    order and the BOM is not copied into the resulting Unicode string.
    If *byteorder is -1 or 1, any byte order mark is copied to the
    output.

    After completion, *byteorder is set to the current byte order at
    the end of input data.

    In a narrow build codepoints outside the BMP will be decoded as
    surrogate pairs.

    If byteorder is NULL, the codec starts in native order mode.

    Return NULL if an exception was raised by the codec.
    """
    string = rffi.charpsize2str(s, size)

    if pbyteorder:
        llbyteorder = rffi.cast(lltype.Signed, pbyteorder[0])
        if llbyteorder < 0:
            byteorder = "little"
        elif llbyteorder > 0:
            byteorder = "big"
        else:
            byteorder = "native"
    else:
        byteorder = "native"

    if llerrors:
        errors = rffi.charp2str(llerrors)
    else:
        errors = None

    result, length, byteorder = runicode.str_decode_utf_32_helper(
        string, size, errors,
        True, # final ? false for multiple passes?
        None, # errorhandler
        byteorder)
    if pbyteorder is not None:
        pbyteorder[0] = rffi.cast(rffi.INT, byteorder)

    return space.wrap(result)

@cpython_api([rffi.CWCHARP, Py_ssize_t, rffi.CCHARP, rffi.CCHARP],
             rffi.INT_real, error=-1)
def PyUnicode_EncodeDecimal(space, s, length, output, llerrors):
    """Takes a Unicode string holding a decimal value and writes it
    into an output buffer using standard ASCII digit codes.

    The output buffer has to provide at least length+1 bytes of
    storage area. The output string is 0-terminated.

    The encoder converts whitespace to ' ', decimal characters to
    their corresponding ASCII digit and all other Latin-1 characters
    except \0 as-is. Characters outside this range (Unicode ordinals
    1-256) are treated as errors. This includes embedded NULL bytes.

    Returns 0 on success, -1 on failure.
    """
    u = rffi.wcharpsize2unicode(s, length)
    if llerrors:
        errors = rffi.charp2str(llerrors)
    else:
        errors = None
    state = space.fromcache(CodecState)
    result = runicode.unicode_encode_decimal(u, length, errors,
                                             state.encode_error_handler)
    i = len(result)
    output[i] = '\0'
    i -= 1
    while i >= 0:
        output[i] = result[i]
        i -= 1
    return 0

@cpython_api([PyObject, PyObject], rffi.INT_real, error=-2)
def PyUnicode_Compare(space, w_left, w_right):
    """Compare two strings and return -1, 0, 1 for less than, equal, and greater
    than, respectively."""
    return space.int_w(space.cmp(w_left, w_right))

@cpython_api([rffi.CWCHARP, rffi.CWCHARP, Py_ssize_t], lltype.Void)
def Py_UNICODE_COPY(space, target, source, length):
    """Roughly equivalent to memcpy() only the base size is Py_UNICODE
    copies sizeof(Py_UNICODE) * length bytes from source to target"""
    for i in range(0, length):
        target[i] = source[i]

@cpython_api([PyObject, PyObject], PyObject)
def PyUnicode_Format(space, w_format, w_args):
    """Return a new string object from format and args; this is analogous to
    format % args.  The args argument must be a tuple."""
    return space.mod(w_format, w_args)

@cpython_api([PyObject, PyObject], PyObject)
def PyUnicode_Join(space, w_sep, w_seq):
    """Join a sequence of strings using the given separator and return
    the resulting Unicode string."""
    return space.call_method(w_sep, 'join', w_seq)

@cpython_api([PyObject, PyObject, PyObject, Py_ssize_t], PyObject)
def PyUnicode_Replace(space, w_str, w_substr, w_replstr, maxcount):
    """Replace at most maxcount occurrences of substr in str with replstr and
    return the resulting Unicode object. maxcount == -1 means replace all
    occurrences."""
    return space.call_method(w_str, "replace", w_substr, w_replstr,
                             space.wrap(maxcount))

@cpython_api([PyObject, PyObject, Py_ssize_t, Py_ssize_t, rffi.INT_real],
             rffi.INT_real, error=-1)
def PyUnicode_Tailmatch(space, w_str, w_substr, start, end, direction):
    """Return 1 if substr matches str[start:end] at the given tail end
    (direction == -1 means to do a prefix match, direction == 1 a
    suffix match), 0 otherwise. Return -1 if an error occurred."""
    str = space.unicode_w(w_str)
    substr = space.unicode_w(w_substr)
    if rffi.cast(lltype.Signed, direction) <= 0:
        return rstring.startswith(str, substr, start, end)
    else:
        return rstring.endswith(str, substr, start, end)

@cpython_api([PyObject, PyObject, Py_ssize_t, Py_ssize_t], Py_ssize_t, error=-1)
def PyUnicode_Count(space, w_str, w_substr, start, end):
    """Return the number of non-overlapping occurrences of substr in
    str[start:end].  Return -1 if an error occurred."""
    w_count = space.call_method(w_str, "count", w_substr,
                                space.wrap(start), space.wrap(end))
    return space.int_w(w_count)

@cpython_api([PyObject, PyObject, Py_ssize_t, Py_ssize_t, rffi.INT_real],
             Py_ssize_t, error=-2)
def PyUnicode_Find(space, w_str, w_substr, start, end, direction):
    """Return the first position of substr in str*[*start:end] using
    the given direction (direction == 1 means to do a forward search,
    direction == -1 a backward search).  The return value is the index
    of the first match; a value of -1 indicates that no match was
    found, and -2 indicates that an error occurred and an exception
    has been set."""
    if rffi.cast(lltype.Signed, direction) > 0:
        w_pos = space.call_method(w_str, "find", w_substr,
                                  space.wrap(start), space.wrap(end))
    else:
        w_pos = space.call_method(w_str, "rfind", w_substr,
                                  space.wrap(start), space.wrap(end))
    return space.int_w(w_pos)

@cpython_api([PyObject, PyObject, Py_ssize_t], PyObject)
def PyUnicode_Split(space, w_str, w_sep, maxsplit):
    """Split a string giving a list of Unicode strings.  If sep is
    NULL, splitting will be done at all whitespace substrings.
    Otherwise, splits occur at the given separator.  At most maxsplit
    splits will be done.  If negative, no limit is set.  Separators
    are not included in the resulting list."""
    if w_sep is None:
        w_sep = space.w_None
    return space.call_method(w_str, "split", w_sep, space.wrap(maxsplit))

@cpython_api([PyObject, rffi.INT_real], PyObject)
def PyUnicode_Splitlines(space, w_str, keepend):
    """Split a Unicode string at line breaks, returning a list of
    Unicode strings.  CRLF is considered to be one line break.  If
    keepend is 0, the Line break characters are not included in the
    resulting strings."""
    return space.call_method(w_str, "splitlines", space.wrap(keepend))
